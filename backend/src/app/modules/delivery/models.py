import uuid
from typing import Any

from sqlalchemy import CheckConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantMixin, TimestampMixin, tenant_fk


class DeliveryZone(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "delivery_zones"

    branch_id: Mapped[uuid.UUID]
    name: Mapped[str] = mapped_column(String(200))
    # GeoJSON Polygon geometry: {"type": "Polygon", "coordinates": [[[lon, lat], ...], <holes>...]}
    polygon: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fee_minor: Mapped[int] = mapped_column(default=0)
    min_order_minor: Mapped[int] = mapped_column(default=0)
    free_from_minor: Mapped[int | None]
    priority: Mapped[int] = mapped_column(default=0)  # lower wins when zones overlap
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        tenant_fk("branch_id", "branches"),
        CheckConstraint("fee_minor >= 0 and min_order_minor >= 0", name="amounts"),
    )
