"""Delivery port (docs/architecture/integrations.md). The ordering core depends on this, not on vendors."""

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GeoPoint:
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class DeliveryQuote:
    branch_id: uuid.UUID
    zone_id: uuid.UUID | None
    zone_name: str
    fee_minor: int
    min_order_minor: int
    free_from_minor: int | None


class DeliveryProvider(Protocol):
    code: str

    async def quote(self, destination: GeoPoint, branch_ids: list[uuid.UUID]) -> DeliveryQuote | None:
        """Cheapest-priority option among the given branches, or None if the address is not served."""
        ...

    async def dispatch(self, order_id: uuid.UUID) -> str | None:
        """Hand the order to couriers; returns an external id. Own couriers: nothing to do."""
        ...
