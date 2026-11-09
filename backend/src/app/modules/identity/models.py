import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    OPERATOR = "operator"


ROLE_RANK = {Role.OPERATOR: 1, Role.MANAGER: 2, Role.OWNER: 3}


class StaffUser(IdMixin, TimestampMixin, Base):
    """Platform-wide identity; access to tenants goes through memberships (no RLS)."""

    __tablename__ = "staff_users"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)


class Membership(TimestampMixin, Base):
    """Read during login before a tenant is chosen, so it is a routing table (no RLS)."""

    __tablename__ = "memberships"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff_users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20))

    __table_args__ = (CheckConstraint("role in ('owner','manager','operator')", name="role"),)


class StaffSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "staff_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
