import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantMixin, TimestampMixin, tenant_fk


class Order(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    number: Mapped[int] = mapped_column(Integer)
    branch_id: Mapped[uuid.UUID]
    cart_id: Mapped[uuid.UUID | None] = mapped_column(unique=True)
    customer_id: Mapped[uuid.UUID | None]
    channel: Mapped[str] = mapped_column(String(20))  # web | telegram | mobile

    status: Mapped[str] = mapped_column(String(20))
    fulfillment: Mapped[str] = mapped_column(String(20))  # delivery | pickup
    payment_method: Mapped[str] = mapped_column(String(32))
    payment_status: Mapped[str] = mapped_column(String(20), default="not_required")

    # Snapshot of contact data at checkout (personal data, see security.md §5).
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_phone: Mapped[str] = mapped_column(String(16))
    address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    comment: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime | None]
    promised_at: Mapped[datetime | None]
    change_from_minor: Mapped[int | None]

    currency: Mapped[str] = mapped_column(String(3))
    subtotal_minor: Mapped[int]
    delivery_fee_minor: Mapped[int]
    total_minor: Mapped[int]
    delivery_zone_id: Mapped[uuid.UUID | None]

    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    public_token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    pd_consent_at: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "number"),
        UniqueConstraint("tenant_id", "idempotency_key"),
        tenant_fk("branch_id", "branches", ondelete="RESTRICT"),
        tenant_fk("customer_id", "customers", ondelete="RESTRICT"),
        CheckConstraint(
            "status in ('pending','confirmed','preparing','ready','delivering','completed','cancelled','rejected')",
            name="status",
        ),
        CheckConstraint("fulfillment in ('delivery','pickup')", name="fulfillment"),
        CheckConstraint("channel in ('web','telegram','mobile')", name="channel"),
        CheckConstraint(
            "subtotal_minor >= 0 and delivery_fee_minor >= 0 and total_minor = subtotal_minor + delivery_fee_minor",
            name="totals",
        ),
        Index("ix_orders_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_orders_tenant_created", "tenant_id", "created_at"),
    )


class OrderItem(IdMixin, TenantMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID]
    product_id: Mapped[uuid.UUID]
    variant_id: Mapped[uuid.UUID]
    product_name: Mapped[str] = mapped_column(String(200))
    variant_name: Mapped[str] = mapped_column(String(200))
    unit_price_minor: Mapped[int]
    quantity: Mapped[int] = mapped_column(Integer)
    line_total_minor: Mapped[int]
    position: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("order_id", "orders"),
        tenant_fk("product_id", "products", ondelete="RESTRICT"),
        tenant_fk("variant_id", "product_variants", ondelete="RESTRICT"),
        CheckConstraint("quantity > 0 and unit_price_minor >= 0 and line_total_minor >= 0", name="values"),
        Index("ix_order_items_order", "order_id"),
    )


class OrderItemModifier(IdMixin, TenantMixin, Base):
    __tablename__ = "order_item_modifiers"

    order_item_id: Mapped[uuid.UUID]
    modifier_id: Mapped[uuid.UUID]
    group_name: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    unit_price_minor: Mapped[int]
    quantity: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        tenant_fk("order_item_id", "order_items"),
        tenant_fk("modifier_id", "modifiers", ondelete="RESTRICT"),
        Index("ix_order_item_modifiers_item", "order_item_id"),
    )


class OrderStatusChange(IdMixin, TenantMixin, Base):
    __tablename__ = "order_status_changes"

    order_id: Mapped[uuid.UUID]
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_type: Mapped[str] = mapped_column(String(20))  # customer | staff | system
    actor_id: Mapped[uuid.UUID | None]
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]

    __table_args__ = (tenant_fk("order_id", "orders"), Index("ix_order_status_changes_order", "order_id"))
