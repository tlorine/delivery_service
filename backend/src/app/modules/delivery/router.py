from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.core.config import Settings
from app.core.http import client_ip
from app.di import Limiters
from app.modules.delivery.geocoder import Geocoder
from app.modules.delivery.provider import GeoPoint
from app.modules.tenancy.context import TenantContext
from app.modules.tenancy.service import BranchService

router = APIRouter(prefix="/v1/address", tags=["storefront"], route_class=DishkaRoute)


class AddressSuggestionOut(BaseModel):
    value: str
    lat: float | None
    lon: float | None
    has_house: bool


@router.get("/suggest", response_model=list[AddressSuggestionOut])
async def suggest(
    request: Request,
    tenant: FromDishka[TenantContext],
    branches: FromDishka[BranchService],
    geocoder: FromDishka[Geocoder],
    limiters: FromDishka[Limiters],
    settings: FromDishka[Settings],
    q: Annotated[str, Query(min_length=3, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[AddressSuggestionOut]:
    """Suggestions near the cafe's branches. Empty when no provider is configured."""
    limiters.suggest.hit(f"suggest:{client_ip(request, settings)}")
    near = [GeoPoint(b.lat, b.lon) for b in await branches.list_active() if b.lat is not None and b.lon is not None]
    items = await geocoder.suggest(q, near, limit)
    return [AddressSuggestionOut(value=i.value, lat=i.lat, lon=i.lon, has_house=i.has_house) for i in items]
