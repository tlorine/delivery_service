import uuid

from sqlalchemy import CheckConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantMixin, TimestampMixin, tenant_fk


class Category(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    sort: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "slug"))


class Product(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "products"

    category_id: Mapped[uuid.UUID]
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    sort: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "slug"),
        tenant_fk("category_id", "categories", ondelete="RESTRICT"),
        Index("ix_products_category", "category_id"),
    )


class ProductVariant(IdMixin, TenantMixin, TimestampMixin, Base):
    """Purchasable unit (size/weight). Price lives here; a product has at least one variant."""

    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID]
    name: Mapped[str] = mapped_column(String(200))
    price_minor: Mapped[int]
    weight_value: Mapped[int | None]
    weight_unit: Mapped[str | None] = mapped_column(String(4))
    sort: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("product_id", "products"),
        CheckConstraint("price_minor >= 0", name="price"),
        Index("ix_product_variants_product", "product_id"),
    )


class ModifierGroup(IdMixin, TenantMixin, TimestampMixin, Base):
    """E.g. 'Sauce' (choose 1) or 'Extras' (0..5). Counts are total modifier quantities in the group."""

    __tablename__ = "modifier_groups"

    name: Mapped[str] = mapped_column(String(200))
    min_selected: Mapped[int] = mapped_column(default=0)
    max_selected: Mapped[int] = mapped_column(default=1)
    sort: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("min_selected >= 0 and max_selected >= 1 and min_selected <= max_selected", name="bounds"),
    )


class Modifier(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "modifiers"

    group_id: Mapped[uuid.UUID]
    name: Mapped[str] = mapped_column(String(200))
    price_minor: Mapped[int] = mapped_column(default=0)
    max_quantity: Mapped[int] = mapped_column(default=1)
    sort: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_fk("group_id", "modifier_groups"),
        CheckConstraint("price_minor >= 0 and max_quantity >= 1", name="values"),
        Index("ix_modifiers_group", "group_id"),
    )


class ProductModifierGroup(TenantMixin, Base):
    __tablename__ = "product_modifier_groups"

    product_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    group_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    sort: Mapped[int] = mapped_column(default=0)

    __table_args__ = (tenant_fk("product_id", "products"), tenant_fk("group_id", "modifier_groups"))


class StoplistEntry(IdMixin, TenantMixin, TimestampMixin, Base):
    """Temporarily unavailable at a branch ('ran out of buns'). Exactly one target is set."""

    __tablename__ = "stoplist_entries"

    branch_id: Mapped[uuid.UUID]
    variant_id: Mapped[uuid.UUID | None]
    modifier_id: Mapped[uuid.UUID | None]

    __table_args__ = (
        tenant_fk("branch_id", "branches"),
        tenant_fk("variant_id", "product_variants"),
        tenant_fk("modifier_id", "modifiers"),
        CheckConstraint("(variant_id is null) <> (modifier_id is null)", name="one_target"),
        UniqueConstraint("branch_id", "variant_id", "modifier_id"),
    )
