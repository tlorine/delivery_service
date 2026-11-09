"""Read model for orders, shared by the storefront, admin and notifications."""

import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ordering.models import Order, OrderItem, OrderItemModifier, OrderStatusChange
from app.modules.ordering.schemas import (
    AddressIn,
    OrderItemModifierOut,
    OrderItemOut,
    OrderOut,
    StatusChangeOut,
)
from app.modules.ordering.state_machine import Fulfillment, OrderStatus
from app.modules.payments.provider import PaymentMethod


async def load_order_views(session: AsyncSession, tenant_id: uuid.UUID, orders: Sequence[Order]) -> list[OrderOut]:
    ids = [o.id for o in orders]
    if not ids:
        return []
    t = tenant_id
    items = (
        await session.scalars(
            select(OrderItem).where(OrderItem.tenant_id == t, OrderItem.order_id.in_(ids)).order_by(OrderItem.position)
        )
    ).all()
    mods = (
        (
            await session.scalars(
                select(OrderItemModifier).where(
                    OrderItemModifier.tenant_id == t,
                    OrderItemModifier.order_item_id.in_([i.id for i in items]),
                )
            )
        ).all()
        if items
        else []
    )
    history = (
        await session.scalars(
            select(OrderStatusChange)
            .where(OrderStatusChange.tenant_id == t, OrderStatusChange.order_id.in_(ids))
            .order_by(OrderStatusChange.created_at, OrderStatusChange.id)
        )
    ).all()

    mods_by_item: dict[uuid.UUID, list[OrderItemModifierOut]] = defaultdict(list)
    for m in mods:
        mods_by_item[m.order_item_id].append(
            OrderItemModifierOut(
                modifier_id=m.modifier_id,
                group_name=m.group_name,
                name=m.name,
                unit_price_minor=m.unit_price_minor,
                quantity=m.quantity,
            )
        )
    items_by_order: dict[uuid.UUID, list[OrderItemOut]] = defaultdict(list)
    for i in items:
        items_by_order[i.order_id].append(
            OrderItemOut(
                id=i.id,
                product_id=i.product_id,
                variant_id=i.variant_id,
                product_name=i.product_name,
                variant_name=i.variant_name,
                unit_price_minor=i.unit_price_minor,
                quantity=i.quantity,
                line_total_minor=i.line_total_minor,
                modifiers=mods_by_item[i.id],
            )
        )
    history_by_order: dict[uuid.UUID, list[StatusChangeOut]] = defaultdict(list)
    for h in history:
        history_by_order[h.order_id].append(
            StatusChangeOut(
                from_status=OrderStatus(h.from_status) if h.from_status else None,
                to_status=OrderStatus(h.to_status),
                actor_type=h.actor_type,
                reason=h.reason,
                created_at=h.created_at,
            )
        )
    return [
        OrderOut(
            id=o.id,
            number=o.number,
            status=OrderStatus(o.status),
            fulfillment=Fulfillment(o.fulfillment),
            channel=o.channel,
            branch_id=o.branch_id,
            payment_method=PaymentMethod(o.payment_method),
            payment_status=o.payment_status,
            currency=o.currency,
            subtotal_minor=o.subtotal_minor,
            delivery_fee_minor=o.delivery_fee_minor,
            total_minor=o.total_minor,
            change_from_minor=o.change_from_minor,
            customer_name=o.customer_name,
            customer_phone=o.customer_phone,
            address=AddressIn.model_validate(o.address) if o.address else None,
            comment=o.comment,
            requested_at=o.requested_at,
            promised_at=o.promised_at,
            created_at=o.created_at,
            items=items_by_order[o.id],
            history=history_by_order[o.id],
            can_cancel=o.status == OrderStatus.PENDING,
        )
        for o in orders
    ]
