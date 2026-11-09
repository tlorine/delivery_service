import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import BusinessRuleViolation, NotFound
from app.core.security import hash_token, new_token
from app.modules.cart.models import Cart, CartItem
from app.modules.catalog.service import CatalogService
from app.modules.pricing.calculator import (
    LineProblem,
    LineResult,
    ModifierChoice,
    price_line,
    validate_and_price_modifiers,
)
from app.modules.tenancy.context import TenantContext

MAX_LINE_QUANTITY = 99
MAX_LINES = 50


@dataclass(slots=True)
class CartLine:
    item_id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str
    variant_name: str
    choices: list[ModifierChoice]
    priced: LineResult | None
    problems: list[LineProblem]

    @property
    def ok(self) -> bool:
        return not self.problems and self.priced is not None


@dataclass(slots=True)
class PricedCart:
    cart: Cart
    lines: list[CartLine] = field(default_factory=list)

    @property
    def subtotal_minor(self) -> int:
        return sum(line.priced.line_total_minor for line in self.lines if line.ok and line.priced)

    @property
    def problems(self) -> list[tuple[uuid.UUID, LineProblem]]:
        return [(line.item_id, p) for line in self.lines for p in line.problems]


def line_key(variant_id: uuid.UUID, choices: Sequence[ModifierChoice]) -> str:
    raw = (
        str(variant_id)
        + "|"
        + ",".join(f"{c.modifier_id}:{c.quantity}" for c in sorted(choices, key=lambda c: str(c.modifier_id)))
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _choices(raw: list[dict[str, object]]) -> list[ModifierChoice]:
    return [ModifierChoice(uuid.UUID(str(m["modifier_id"])), int(str(m["quantity"]))) for m in raw]


class CartService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        catalog: CatalogService,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.catalog = catalog
        self.clock = clock
        self.settings = settings

    async def create(self) -> tuple[str, Cart]:
        token = new_token()
        cart = Cart(
            tenant_id=self.tenant.id,
            token_hash=hash_token(token),
            expires_at=self.clock.now() + timedelta(days=self.settings.cart_ttl_days),
        )
        self.session.add(cart)
        await self.session.commit()
        return token, cart

    async def get(self, token: str | None, *, for_update: bool = False) -> Cart:
        if not token:
            raise NotFound("cart not found", code="cart_not_found")
        stmt = select(Cart).where(Cart.tenant_id == self.tenant.id, Cart.token_hash == hash_token(token))
        if for_update:
            stmt = stmt.with_for_update()
        cart = await self.session.scalar(stmt)
        if cart is None or cart.expires_at < self.clock.now():
            raise NotFound("cart not found", code="cart_not_found")
        return cart

    async def get_active(self, token: str | None) -> Cart:
        cart = await self.get(token, for_update=True)
        if cart.status != "active":
            raise NotFound("cart was already checked out", code="cart_not_found")
        return cart

    async def items(self, cart: Cart) -> Sequence[CartItem]:
        rows = await self.session.scalars(
            select(CartItem)
            .where(CartItem.tenant_id == self.tenant.id, CartItem.cart_id == cart.id)
            .order_by(CartItem.created_at, CartItem.id)
        )
        return rows.all()

    async def price(self, cart: Cart, branch_id: uuid.UUID | None) -> PricedCart:
        items = await self.items(cart)
        rules = await self.catalog.variant_rules((i.variant_id for i in items), branch_id)
        result = PricedCart(cart)
        for item in items:
            choices = _choices(item.modifiers)
            rule = rules.get(item.variant_id)
            if rule is None:
                result.lines.append(
                    CartLine(
                        item.id,
                        item.variant_id,
                        None,
                        "",
                        "",
                        choices,
                        None,
                        [LineProblem("item_unavailable", "item no longer exists")],
                    )
                )
                continue
            modifiers, problems = validate_and_price_modifiers(rule.groups, choices)
            if not rule.available:
                problems.insert(0, LineProblem("item_unavailable", f"'{rule.product_name}' is unavailable"))
            result.lines.append(
                CartLine(
                    item.id,
                    item.variant_id,
                    rule.product_id,
                    rule.product_name,
                    rule.variant_name,
                    choices,
                    price_line(rule.price_minor, modifiers, item.quantity),
                    problems,
                )
            )
        return result

    async def add_item(
        self, token: str | None, variant_id: uuid.UUID, quantity: int, choices: list[ModifierChoice]
    ) -> Cart:
        cart = await self.get_active(token)
        rule = (await self.catalog.variant_rules([variant_id], None)).get(variant_id)
        if rule is None:
            raise NotFound("product not found", code="product_not_found")
        if not rule.available:
            raise BusinessRuleViolation(f"'{rule.product_name}' is unavailable", code="item_unavailable")
        _, problems = validate_and_price_modifiers(rule.groups, choices)
        if problems:
            raise BusinessRuleViolation("; ".join(p.detail for p in problems), code=problems[0].code)

        key = line_key(variant_id, choices)
        items = await self.items(cart)
        existing = next((i for i in items if i.line_key == key), None)
        if existing:
            existing.quantity = min(existing.quantity + quantity, MAX_LINE_QUANTITY)
        else:
            if len(items) >= MAX_LINES:
                raise BusinessRuleViolation("too many items in the cart", code="cart_too_large")
            self.session.add(
                CartItem(
                    tenant_id=self.tenant.id,
                    cart_id=cart.id,
                    variant_id=variant_id,
                    quantity=min(quantity, MAX_LINE_QUANTITY),
                    line_key=key,
                    modifiers=[
                        {"modifier_id": str(c.modifier_id), "quantity": c.quantity}
                        for c in sorted(choices, key=lambda c: str(c.modifier_id))
                    ],
                )
            )
        cart.updated_at = self.clock.now()
        await self.session.commit()
        return cart

    async def _item(self, cart: Cart, item_id: uuid.UUID) -> CartItem:
        item = await self.session.scalar(
            select(CartItem).where(
                CartItem.tenant_id == self.tenant.id, CartItem.cart_id == cart.id, CartItem.id == item_id
            )
        )
        if item is None:
            raise NotFound("cart item not found", code="cart_item_not_found")
        return item

    async def set_quantity(self, token: str | None, item_id: uuid.UUID, quantity: int) -> Cart:
        cart = await self.get_active(token)
        item = await self._item(cart, item_id)
        if quantity <= 0:
            await self.session.delete(item)
        else:
            item.quantity = min(quantity, MAX_LINE_QUANTITY)
        cart.updated_at = self.clock.now()
        await self.session.commit()
        return cart

    async def remove_item(self, token: str | None, item_id: uuid.UUID) -> Cart:
        return await self.set_quantity(token, item_id, 0)
