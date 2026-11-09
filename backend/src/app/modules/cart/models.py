import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantMixin, TimestampMixin, tenant_fk


class Cart(IdMixin, TenantMixin, TimestampMixin, Base):
    """Server-side cart without prices: totals are recomputed from the catalog on every read."""

    __tablename__ = "carts"

    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("status in ('active','checked_out')", name="status"),
    )


class CartItem(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID]
    variant_id: Mapped[uuid.UUID]
    quantity: Mapped[int]
    # [{"modifier_id": "...", "quantity": 1}], sorted by modifier_id; validated on every pricing pass.
    modifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Identity of the configuration (variant + modifiers): the same configuration is merged.
    line_key: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        tenant_fk("cart_id", "carts"),
        tenant_fk("variant_id", "product_variants"),
        CheckConstraint("quantity between 1 and 99", name="quantity"),
        UniqueConstraint("cart_id", "line_key"),
        Index("ix_cart_items_cart", "cart_id"),
    )
