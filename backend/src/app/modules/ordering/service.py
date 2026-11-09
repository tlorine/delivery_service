"""Checkout and order lifecycle. The only place where an order is created or changes status."""

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import BusinessRuleViolation, Conflict, NotFound
from app.core.phone import normalize_phone
from app.core.security import hash_token, order_access_token
from app.modules.audit.service import AuditService
from app.modules.cart.service import CartService, PricedCart
from app.modules.customers.service import CustomerService
from app.modules.delivery.provider import DeliveryProvider, DeliveryQuote, GeoPoint
from app.modules.notifications.outbox import OutboxEventType, emit, wake_worker
from app.modules.ordering.models import Order, OrderItem, OrderItemModifier, OrderStatusChange
from app.modules.ordering.read import load_order_views
from app.modules.ordering.schemas import (
    CheckoutIn,
    OrderIn,
    OrderOut,
    Problem,
    QuoteOut,
)
from app.modules.ordering.state_machine import (
    Actor,
    Fulfillment,
    OrderStatus,
    check_transition,
)
from app.modules.payments.provider import PaymentMethod, enabled_methods, initial_status
from app.modules.tenancy.context import TenantContext
from app.modules.tenancy.models import Branch
from app.modules.tenancy.schedule import is_open_at, open_windows
from app.modules.tenancy.service import BranchService

MAX_SCHEDULE_AHEAD = timedelta(days=7)


@dataclass(slots=True)
class Evaluation:
    """Result of checking a cart against checkout conditions. Shared by quote and checkout."""

    priced: PricedCart | None = None
    branch: Branch | None = None
    quote: DeliveryQuote | None = None
    problems: list[Problem] = field(default_factory=list)
    delivery_fee_minor: int = 0
    ready_at: datetime | None = None

    @property
    def subtotal_minor(self) -> int:
        return self.priced.subtotal_minor if self.priced else 0

    @property
    def total_minor(self) -> int:
        return self.subtotal_minor + self.delivery_fee_minor

    def fail(self, code: str, detail: str, item_id: uuid.UUID | None = None) -> None:
        self.problems.append(Problem(code=code, detail=detail, item_id=item_id))


def _request_hash(cart_id: uuid.UUID, body: OrderIn) -> bytes:
    canonical = json.dumps([str(cart_id), body.model_dump(mode="json")], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).digest()


class OrderService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        carts: CartService,
        branches: BranchService,
        delivery: DeliveryProvider,
        customers: CustomerService,
        audit: AuditService,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.carts = carts
        self.branches = branches
        self.delivery = delivery
        self.customers = customers
        self.audit = audit
        self.clock = clock
        self.settings = settings

    # ---------------------------------------------------------------- evaluation (quote + checkout)

    async def _pick_branch(self, req: CheckoutIn, ev: Evaluation) -> None:
        if req.fulfillment == Fulfillment.PICKUP:
            if req.branch_id is None:
                ev.fail("branch_required", "choose a pickup point")
                return
            try:
                branch = await self.branches.get(req.branch_id)
            except NotFound:
                ev.fail("branch_not_found", "pickup point not found")
                return
            if not branch.pickup_enabled:
                ev.fail("fulfillment_unavailable", "pickup is not available at this point")
            ev.branch = branch
            return

        if req.address is None:
            ev.fail("address_required", "delivery address is required")
            return
        if req.branch_id is not None:
            try:
                candidates = [await self.branches.get(req.branch_id)]
            except NotFound:
                ev.fail("branch_not_found", "branch not found")
                return
        else:
            candidates = list(await self.branches.list_active())
        candidates = [b for b in candidates if b.delivery_enabled]
        if not candidates:
            ev.fail("fulfillment_unavailable", "delivery is not available")
            return
        quote = await self.delivery.quote(GeoPoint(req.address.lat, req.address.lon), [b.id for b in candidates])
        if quote is None:
            ev.fail("outside_delivery_zone", "the address is outside the delivery area")
            return
        ev.quote = quote
        ev.branch = next(b for b in candidates if b.id == quote.branch_id)

    async def _check_time(self, req: CheckoutIn, ev: Evaluation, now: datetime) -> None:
        branch = ev.branch
        assert branch is not None
        hours = (await self.branches.hours([branch.id])).get(branch.id, [])
        lead = timedelta(minutes=branch.prep_time_min)
        if req.fulfillment == Fulfillment.DELIVERY:
            lead += timedelta(minutes=branch.delivery_time_min)
        if req.requested_at is None:
            if not is_open_at(hours, branch.timezone, now):
                ev.fail("branch_closed", "the place is closed now; choose a time")
            ev.ready_at = now + lead
            return
        requested = req.requested_at
        if requested.tzinfo is None:
            ev.fail("invalid_requested_time", "time must include a time zone offset")
            return
        if requested < now + lead or requested > now + MAX_SCHEDULE_AHEAD:
            ev.fail("invalid_requested_time", "this time is not available")
            return
        # The kitchen must be open when the order is prepared and when it is handed over.
        start_cooking = requested - lead
        windows = open_windows(hours, branch.timezone, now, days=8)
        if not any(s <= start_cooking and requested <= e for s, e in windows):
            ev.fail("invalid_requested_time", "the place is closed at this time")
            return
        ev.ready_at = requested

    async def evaluate(self, priced: PricedCart, req: CheckoutIn, now: datetime) -> Evaluation:
        ev = Evaluation(priced=priced)
        if not priced.lines:
            ev.fail("cart_empty", "the cart is empty")
        await self._pick_branch(req, ev)
        if ev.branch is None:
            return ev

        # Re-price against the chosen branch: its stop-list applies.
        ev.priced = priced = await self.carts.price(priced.cart, ev.branch.id)
        for item_id, p in priced.problems:
            ev.fail(p.code, p.detail, item_id)

        await self._check_time(req, ev, now)

        if req.payment_method not in enabled_methods() or req.payment_method not in ev.branch.payment_methods:
            ev.fail("payment_method_unavailable", "this payment method is not available")

        if ev.quote:
            if ev.subtotal_minor < ev.quote.min_order_minor:
                ev.fail("below_min_order", "the order total is below the minimum for delivery")
            fee = ev.quote.fee_minor
            if ev.quote.free_from_minor is not None and ev.subtotal_minor >= ev.quote.free_from_minor:
                fee = 0
            ev.delivery_fee_minor = fee

        if req.change_from_minor is not None:
            if req.payment_method != PaymentMethod.CASH:
                ev.fail("invalid_change", "change is only for cash payments")
            elif req.change_from_minor < ev.total_minor:
                ev.fail("invalid_change", "the amount must not be less than the total")
        return ev

    def _quote_out(self, ev: Evaluation) -> QuoteOut:
        return QuoteOut(
            ok=not ev.problems,
            problems=ev.problems,
            branch_id=ev.branch.id if ev.branch else None,
            currency=self.tenant.currency,
            subtotal_minor=ev.subtotal_minor,
            delivery_fee_minor=ev.delivery_fee_minor,
            total_minor=ev.total_minor,
            min_order_minor=ev.quote.min_order_minor if ev.quote else None,
            delivery_zone_name=ev.quote.zone_name if ev.quote else None,
            estimated_ready_at=ev.ready_at,
        )

    async def quote(self, cart_token: str | None, req: CheckoutIn) -> QuoteOut:
        cart = await self.carts.get_active(cart_token)
        priced = await self.carts.price(cart, req.branch_id)
        return self._quote_out(await self.evaluate(priced, req, self.clock.now()))

    # ---------------------------------------------------------------- checkout

    async def _replay(self, idempotency_key: str, request_hash: bytes) -> Order | None:
        existing = await self.session.scalar(
            select(Order).where(Order.tenant_id == self.tenant.id, Order.idempotency_key == idempotency_key)
        )
        if existing is None:
            return None
        if existing.request_hash != request_hash:
            raise BusinessRuleViolation(
                "Idempotency-Key was already used for a different request", code="idempotency_key_reused"
            )
        return existing

    async def _next_number(self) -> int:
        # Row lock on the counter serializes numbering per tenant only.
        number: int = (
            await self.session.execute(
                text(
                    "INSERT INTO tenant_counters (tenant_id, name, value) VALUES (:t, 'order', 1) "
                    "ON CONFLICT (tenant_id, name) DO UPDATE SET value = tenant_counters.value + 1 "
                    "RETURNING value"
                ),
                {"t": self.tenant.id},
            )
        ).scalar_one()
        return number

    async def checkout(
        self,
        cart_token: str | None,
        idempotency_key: str,
        req: OrderIn,
        channel: str,
        telegram_user_id: int | None = None,
    ) -> tuple[Order, bool]:
        """Returns (order, created). A retry with the same key and body returns the same order."""
        # Lock the cart first: concurrent checkouts of one cart are serialized here.
        cart = await self.carts.get(cart_token, for_update=True)
        request_hash = _request_hash(cart.id, req)
        if (existing := await self._replay(idempotency_key, request_hash)) is not None:
            return existing, False
        if cart.status != "active":
            raise Conflict("this cart has already been checked out", code="cart_already_checked_out")

        phone = normalize_phone(req.customer.phone, self.tenant.country)
        if phone is None:
            raise BusinessRuleViolation("invalid phone number", code="invalid_phone")

        now = self.clock.now()
        priced = await self.carts.price(cart, req.branch_id)
        ev = await self.evaluate(priced, req, now)
        if ev.problems:
            first = ev.problems[0]
            raise BusinessRuleViolation(
                first.detail,
                code=first.code,
                extra={"problems": [p.model_dump(mode="json") for p in ev.problems]},
            )
        if req.expected_total_minor is not None and req.expected_total_minor != ev.total_minor:
            raise Conflict(
                "prices have changed",
                code="price_changed",
                extra={"quote": self._quote_out(ev).model_dump(mode="json")},
            )
        assert ev.branch is not None and ev.priced is not None

        customer_id = await self.customers.upsert_by_phone(phone, req.customer.name, telegram_user_id)
        order = Order(
            tenant_id=self.tenant.id,
            number=await self._next_number(),
            branch_id=ev.branch.id,
            cart_id=cart.id,
            customer_id=customer_id,
            channel=channel,
            status=OrderStatus.PENDING,
            fulfillment=req.fulfillment,
            payment_method=req.payment_method,
            payment_status=initial_status(req.payment_method),
            customer_name=req.customer.name,
            customer_phone=phone,
            address=req.address.model_dump(mode="json")
            if req.fulfillment == Fulfillment.DELIVERY and req.address
            else None,
            comment=req.comment,
            requested_at=req.requested_at,
            promised_at=ev.ready_at,
            change_from_minor=req.change_from_minor,
            currency=self.tenant.currency,
            subtotal_minor=ev.subtotal_minor,
            delivery_fee_minor=ev.delivery_fee_minor,
            total_minor=ev.total_minor,
            delivery_zone_id=ev.quote.zone_id if ev.quote else None,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            public_token_hash=b"",  # set below, needs the id
            pd_consent_at=now,
            created_at=now,  # one clock for business time (schedule, analytics), not the DB's now()
        )
        self.session.add(order)
        await self.session.flush()
        order.public_token_hash = hash_token(self.access_token(order))

        for position, line in enumerate(ev.priced.lines):
            assert line.priced is not None and line.product_id is not None
            item = OrderItem(
                tenant_id=self.tenant.id,
                order_id=order.id,
                product_id=line.product_id,
                variant_id=line.variant_id,
                product_name=line.product_name,
                variant_name=line.variant_name,
                unit_price_minor=line.priced.unit_price_minor,
                quantity=line.priced.quantity,
                line_total_minor=line.priced.line_total_minor,
                position=position,
            )
            self.session.add(item)
            await self.session.flush()
            for m in line.priced.modifiers:
                self.session.add(
                    OrderItemModifier(
                        tenant_id=self.tenant.id,
                        order_item_id=item.id,
                        modifier_id=m.modifier_id,
                        group_name=m.group_name,
                        name=m.name,
                        unit_price_minor=m.unit_price_minor,
                        quantity=m.quantity,
                    )
                )

        self.session.add(
            OrderStatusChange(
                tenant_id=self.tenant.id,
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.PENDING,
                actor_type=Actor.CUSTOMER,
                actor_id=customer_id,
                reason=None,
                created_at=now,
            )
        )
        cart.status = "checked_out"
        self.audit.record(
            "order.created",
            "order",
            order.id,
            actor_type=Actor.CUSTOMER,
            actor_id=customer_id,
            data={"total_minor": order.total_minor, "channel": channel},
        )
        emit(self.session, self.tenant.id, OutboxEventType.ORDER_CREATED, {"order_id": str(order.id)})
        await wake_worker(self.session)
        try:
            await self.session.commit()
        except IntegrityError:
            # Same Idempotency-Key raced in from another cart: report it like a replay would.
            await self.session.rollback()
            if (existing := await self._replay(idempotency_key, request_hash)) is not None:
                return existing, False
            raise
        return order, True

    # ---------------------------------------------------------------- reading

    def access_token(self, order: Order) -> str:
        return order_access_token(self.settings.session_secret.get_secret_value(), order.id)

    async def get_by_token(self, token: str, *, for_update: bool = False) -> Order:
        stmt = select(Order).where(Order.tenant_id == self.tenant.id, Order.public_token_hash == hash_token(token))
        if for_update:
            stmt = stmt.with_for_update()
        order = await self.session.scalar(stmt)
        if order is None:
            raise NotFound("order not found", code="order_not_found")
        return order

    async def get(self, order_id: uuid.UUID, *, for_update: bool = False) -> Order:
        stmt = select(Order).where(Order.tenant_id == self.tenant.id, Order.id == order_id)
        if for_update:
            stmt = stmt.with_for_update()
        order = await self.session.scalar(stmt)
        if order is None:
            raise NotFound("order not found", code="order_not_found")
        return order

    async def list_orders(
        self,
        statuses: Sequence[OrderStatus] | None,
        branch_id: uuid.UUID | None,
        before: datetime | None,
        limit: int,
    ) -> Sequence[Order]:
        stmt = select(Order).where(Order.tenant_id == self.tenant.id)
        if statuses:
            stmt = stmt.where(Order.status.in_(list(statuses)))
        if branch_id:
            stmt = stmt.where(Order.branch_id == branch_id)
        if before:
            stmt = stmt.where(Order.created_at < before)
        return (await self.session.scalars(stmt.order_by(Order.created_at.desc()).limit(limit))).all()

    async def views(self, orders: Sequence[Order]) -> list[OrderOut]:
        return await load_order_views(self.session, self.tenant.id, orders)

    async def view(self, order: Order) -> OrderOut:
        return (await self.views([order]))[0]

    # ---------------------------------------------------------------- lifecycle

    async def _apply_transition(
        self, order: Order, target: OrderStatus, actor: Actor, actor_id: uuid.UUID | None, reason: str | None
    ) -> Order:
        current = OrderStatus(order.status)
        check_transition(current, target, Fulfillment(order.fulfillment), actor, reason)
        now = self.clock.now()
        order.status = target
        order.updated_at = now
        self.session.add(
            OrderStatusChange(
                tenant_id=self.tenant.id,
                order_id=order.id,
                from_status=current,
                to_status=target,
                actor_type=actor,
                actor_id=actor_id,
                reason=reason,
                created_at=now,
            )
        )
        self.audit.record(
            "order.status_changed",
            "order",
            order.id,
            actor_type=actor,
            actor_id=actor_id,
            data={"from": current, "to": target},
        )
        emit(
            self.session,
            self.tenant.id,
            OutboxEventType.ORDER_STATUS_CHANGED,
            {"order_id": str(order.id), "from": current, "to": target},
        )
        await wake_worker(self.session)
        await self.session.commit()
        return order

    async def cancel_by_customer(self, token: str) -> Order:
        order = await self.get_by_token(token, for_update=True)
        return await self._apply_transition(order, OrderStatus.CANCELLED, Actor.CUSTOMER, order.customer_id, None)

    async def transition_by_staff(
        self, order_id: uuid.UUID, target: OrderStatus, staff_id: uuid.UUID, reason: str | None
    ) -> Order:
        # FOR UPDATE: concurrent "confirm" and "cancel" cannot both succeed.
        order = await self.get(order_id, for_update=True)
        return await self._apply_transition(order, target, Actor.STAFF, staff_id, reason)
