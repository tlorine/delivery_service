import uuid
from datetime import datetime
from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.modules.identity.models import Role
from app.modules.identity.service import StaffContext
from app.modules.ordering.schemas import OrderOut, TransitionIn
from app.modules.ordering.service import OrderService
from app.modules.ordering.state_machine import Fulfillment, OrderStatus, next_statuses

router = APIRouter(prefix="/v1/admin/orders", tags=["admin: orders"], route_class=DishkaRoute)


class AdminOrderOut(OrderOut):
    next_statuses: list[OrderStatus]


class OrderListOut(BaseModel):
    items: list[AdminOrderOut]
    next_before: datetime | None


def _admin(o: OrderOut) -> AdminOrderOut:
    return AdminOrderOut(**o.model_dump(), next_statuses=next_statuses(o.status, Fulfillment(o.fulfillment)))


@router.get("", response_model=OrderListOut)
async def list_orders(
    staff: FromDishka[StaffContext],
    orders: FromDishka[OrderService],
    status: Annotated[list[OrderStatus] | None, Query()] = None,
    branch_id: uuid.UUID | None = None,
    before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> OrderListOut:
    staff.require(Role.OPERATOR)
    rows = await orders.list_orders(status, branch_id, before, limit)
    views = await orders.views(rows)
    return OrderListOut(
        items=[_admin(v) for v in views], next_before=rows[-1].created_at if len(rows) == limit else None
    )


@router.get("/{order_id}", response_model=AdminOrderOut)
async def get_order(
    order_id: uuid.UUID, staff: FromDishka[StaffContext], orders: FromDishka[OrderService]
) -> AdminOrderOut:
    staff.require(Role.OPERATOR)
    return _admin(await orders.view(await orders.get(order_id)))


@router.post("/{order_id}/transitions", response_model=AdminOrderOut)
async def transition(
    order_id: uuid.UUID, body: TransitionIn, staff: FromDishka[StaffContext], orders: FromDishka[OrderService]
) -> AdminOrderOut:
    staff.require(Role.OPERATOR)
    order = await orders.transition_by_staff(order_id, body.to_status, staff.user_id, body.reason)
    return _admin(await orders.view(order))
