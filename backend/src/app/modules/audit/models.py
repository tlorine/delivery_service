import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantMixin


class AuditLog(IdMixin, TenantMixin, Base):
    """Append-only journal of significant actions. `data` must not contain personal data."""

    __tablename__ = "audit_log"

    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_audit_log_tenant_created", "tenant_id", "created_at"),)
