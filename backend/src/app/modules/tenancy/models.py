import uuid
from datetime import time
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantMixin, TimestampMixin, tenant_fk


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Tenant(IdMixin, TimestampMixin, Base):
    """An independent food business. Routing table: read before the tenant is known (no RLS)."""

    __tablename__ = "tenants"

    slug: Mapped[str] = mapped_column(String(63), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=TenantStatus.ACTIVE)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    country: Mapped[str] = mapped_column(String(2), default="RU")
    locale: Mapped[str] = mapped_column(String(10), default="ru")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    # Storefront look: colors, logo, links. Free-form for the frontend, validated by schemas.
    branding: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")

    __table_args__ = (CheckConstraint("status in ('active','suspended')", name="status"),)


class TenantDomain(IdMixin, TimestampMixin, Base):
    __tablename__ = "tenant_domains"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    host: Mapped[str] = mapped_column(String(253), unique=True)
    is_primary: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (CheckConstraint("host = lower(host)", name="host_lowercase"),)


class TenantCounter(Base):
    """Per-tenant sequences (human-friendly order numbers)."""

    __tablename__ = "tenant_counters"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[int] = mapped_column(default=0)


class Branch(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "branches"

    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    phone: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(default=True)
    delivery_enabled: Mapped[bool] = mapped_column(default=True)
    pickup_enabled: Mapped[bool] = mapped_column(default=True)
    prep_time_min: Mapped[int] = mapped_column(default=30)
    delivery_time_min: Mapped[int] = mapped_column(default=45)
    payment_methods: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=lambda: ["cash", "card_on_delivery"], server_default="{cash}"
    )
    sort: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("prep_time_min >= 0 and delivery_time_min >= 0", name="times"),
    )


class BranchHours(IdMixin, TenantMixin, Base):
    """Opening interval in branch local time. closes_at <= opens_at means the interval ends next day."""

    __tablename__ = "branch_hours"

    branch_id: Mapped[uuid.UUID]
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0 = Monday (ISO weekday - 1)
    opens_at: Mapped[time]
    closes_at: Mapped[time]

    __table_args__ = (
        tenant_fk("branch_id", "branches"),
        CheckConstraint("weekday between 0 and 6", name="weekday"),
        Index("ix_branch_hours_branch", "branch_id", "weekday"),
    )
