import uuid
from datetime import datetime, time, timedelta
from typing import Any

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.clock import Clock
from app.core.config import Settings
from app.modules.ordering.state_machine import Fulfillment
from app.modules.tenancy.context import TenantContext
from app.modules.tenancy.schedule import current_window_end, is_open_at, next_opening, time_slots
from app.modules.tenancy.service import BranchService

router = APIRouter(prefix="/v1/storefront", tags=["storefront"], route_class=DishkaRoute)


class HoursOut(BaseModel):
    weekday: int
    opens_at: time
    closes_at: time


class BranchOut(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    lat: float | None
    lon: float | None
    phone: str | None
    timezone: str
    delivery_enabled: bool
    pickup_enabled: bool
    payment_methods: list[str]
    prep_time_min: int
    delivery_time_min: int
    is_open_now: bool
    closes_at: datetime | None
    next_opening_at: datetime | None
    hours: list[HoursOut]


class StorefrontOut(BaseModel):
    slug: str
    name: str
    currency: str
    country: str
    locale: str
    branding: dict[str, Any]
    branches: list[BranchOut]
    server_time: datetime
    address_suggest_enabled: bool = Field(
        description="Delivery needs coordinates: without suggestions the storefront offers pickup only"
    )


@router.get("", response_model=StorefrontOut)
async def get_storefront(
    tenant: FromDishka[TenantContext],
    branches: FromDishka[BranchService],
    clock: FromDishka[Clock],
    settings: FromDishka[Settings],
) -> StorefrontOut:
    now = clock.now()
    rows = await branches.list_active()
    hours = await branches.hours([b.id for b in rows])
    out = []
    for b in rows:
        h = hours.get(b.id, [])
        out.append(
            BranchOut(
                id=b.id,
                name=b.name,
                address=b.address,
                lat=b.lat,
                lon=b.lon,
                phone=b.phone,
                timezone=b.timezone,
                delivery_enabled=b.delivery_enabled,
                pickup_enabled=b.pickup_enabled,
                payment_methods=b.payment_methods,
                prep_time_min=b.prep_time_min,
                delivery_time_min=b.delivery_time_min,
                is_open_now=is_open_at(h, b.timezone, now),
                closes_at=current_window_end(h, b.timezone, now),
                next_opening_at=next_opening(h, b.timezone, now),
                hours=[
                    HoursOut(weekday=i.weekday, opens_at=i.opens_at, closes_at=i.closes_at)
                    for i in sorted(h, key=lambda i: (i.weekday, i.opens_at))
                ],
            )
        )
    return StorefrontOut(
        slug=tenant.slug,
        name=tenant.name,
        currency=tenant.currency,
        country=tenant.country,
        locale=tenant.locale,
        branding=tenant.branding,
        branches=out,
        server_time=now,
        address_suggest_enabled=settings.geocoder != "none",
    )


@router.get("/time-slots", response_model=list[datetime])
async def get_time_slots(
    branches: FromDishka[BranchService],
    clock: FromDishka[Clock],
    branch_id: uuid.UUID,
    fulfillment: Fulfillment,
) -> list[datetime]:
    """Times a scheduled order can be placed for (today and tomorrow), in 30-minute steps."""
    branch = await branches.get(branch_id)
    lead = timedelta(minutes=branch.prep_time_min)
    if fulfillment == Fulfillment.DELIVERY:
        lead += timedelta(minutes=branch.delivery_time_min)
    h = (await branches.hours([branch.id])).get(branch.id, [])
    return time_slots(h, branch.timezone, clock.now(), lead)
