import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.geo import polygon_contains
from app.modules.delivery.models import DeliveryZone
from app.modules.delivery.provider import DeliveryQuote, GeoPoint
from app.modules.tenancy.context import TenantContext


class OwnCourierProvider:
    """The cafe's own couriers: price by the branch's delivery zones, manual assignment."""

    code = "own_courier"

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.tenant = tenant

    async def quote(self, destination: GeoPoint, branch_ids: list[uuid.UUID]) -> DeliveryQuote | None:
        if not branch_ids:
            return None
        zones = await self.session.scalars(
            select(DeliveryZone)
            .where(
                DeliveryZone.tenant_id == self.tenant.id,
                DeliveryZone.branch_id.in_(branch_ids),
                DeliveryZone.is_active.is_(True),
            )
            .order_by(DeliveryZone.priority, DeliveryZone.fee_minor)
        )
        for z in zones:
            if polygon_contains(z.polygon, destination.lat, destination.lon):
                return DeliveryQuote(z.branch_id, z.id, z.name, z.fee_minor, z.min_order_minor, z.free_from_minor)
        return None

    async def dispatch(self, order_id: uuid.UUID) -> str | None:
        return None
