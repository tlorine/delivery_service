"""Basic numbers for a small cafe owner: no BI, just today and the last days, in the cafe's time zone."""

from datetime import date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.modules.identity.models import Role
from app.modules.identity.service import StaffContext
from app.modules.ordering.models import Order, OrderItem
from app.modules.tenancy.context import TenantContext

router = APIRouter(prefix="/v1/admin/analytics", tags=["admin: analytics"], route_class=DishkaRoute)

LOST = ("cancelled", "rejected")


class DayOut(BaseModel):
    date: date
    orders: int
    revenue_minor: int


class TopProductOut(BaseModel):
    name: str
    quantity: int
    revenue_minor: int


class SummaryOut(BaseModel):
    currency: str
    timezone: str
    today_orders: int
    today_revenue_minor: int
    today_average_minor: int
    today_cancelled: int
    pending_now: int
    days: list[DayOut]
    top_products: list[TopProductOut]


@router.get("/summary", response_model=SummaryOut)
async def summary(
    staff: FromDishka[StaffContext],
    tenant: FromDishka[TenantContext],
    session: FromDishka[AsyncSession],
    clock: FromDishka[Clock],
    days: Annotated[int, Query(ge=1, le=31)] = 7,
) -> SummaryOut:
    """Revenue counts orders that were not cancelled or rejected (paid on receipt: it is expected revenue)."""
    staff.require(Role.MANAGER)
    tz = ZoneInfo(tenant.timezone)
    today = clock.now().astimezone(tz).date()
    start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), tz)
    local_day = cast(func.timezone(tenant.timezone, Order.created_at), Date)
    t = tenant.id

    rows = (
        await session.execute(
            select(local_day, func.count(), func.coalesce(func.sum(Order.total_minor), 0))
            .where(Order.tenant_id == t, Order.created_at >= start, Order.status.not_in(LOST))
            .group_by(local_day)
        )
    ).all()
    by_day = {d: (n, int(rev)) for d, n, rev in rows}
    series = [
        DayOut(date=d, orders=by_day.get(d, (0, 0))[0], revenue_minor=by_day.get(d, (0, 0))[1])
        for d in (today - timedelta(days=i) for i in reversed(range(days)))
    ]
    today_n, today_rev = by_day.get(today, (0, 0))

    today_start = datetime.combine(today, datetime.min.time(), tz)
    cancelled = (
        await session.scalar(
            select(func.count())
            .select_from(Order)
            .where(Order.tenant_id == t, Order.created_at >= today_start, Order.status.in_(LOST))
        )
        or 0
    )
    pending = (
        await session.scalar(
            select(func.count()).select_from(Order).where(Order.tenant_id == t, Order.status == "pending")
        )
        or 0
    )
    top = (
        await session.execute(
            select(OrderItem.product_name, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total_minor))
            .join(Order, (Order.id == OrderItem.order_id) & (Order.tenant_id == t))
            .where(OrderItem.tenant_id == t, Order.created_at >= start, Order.status.not_in(LOST))
            .group_by(OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(5)
        )
    ).all()
    return SummaryOut(
        currency=tenant.currency,
        timezone=tenant.timezone,
        today_orders=today_n,
        today_revenue_minor=today_rev,
        today_average_minor=today_rev // today_n if today_n else 0,
        today_cancelled=cancelled,
        pending_now=pending,
        days=series,
        top_products=[TopProductOut(name=n, quantity=int(q), revenue_minor=int(r)) for n, q, r in top],
    )
