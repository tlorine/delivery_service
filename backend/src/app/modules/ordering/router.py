from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Header, Request, Response, status

from app.core.config import Settings
from app.core.http import channel_of, client_ip
from app.di import Limiters
from app.modules.cart.router import CartToken
from app.modules.ordering.schemas import OrderCreatedOut, OrderIn, OrderOut, QuoteIn, QuoteOut
from app.modules.ordering.service import OrderService
from app.modules.telegram.service import TelegramIdentity

router = APIRouter(prefix="/v1", tags=["orders"], route_class=DishkaRoute)

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key", min_length=8, max_length=100, description="Client-generated UUID per checkout attempt"
    ),
]


@router.post("/checkout/quote", response_model=QuoteOut)
async def quote(body: QuoteIn, orders: FromDishka[OrderService], x_cart_token: CartToken = None) -> QuoteOut:
    """Validate the cart against checkout conditions without placing an order. Never raises on rule problems."""
    return await orders.quote(x_cart_token, body)


@router.post(
    "/orders",
    response_model=OrderCreatedOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Idempotent replay: the order created earlier with this key"}},
)
async def place_order(
    body: OrderIn,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKey,
    orders: FromDishka[OrderService],
    limiters: FromDishka[Limiters],
    settings: FromDishka[Settings],
    telegram: FromDishka[TelegramIdentity],
    x_cart_token: CartToken = None,
    x_telegram_init_data: Annotated[
        str | None,
        Header(alias="X-Telegram-Init-Data", description="Raw Mini App initData; verified with the cafe's bot"),
    ] = None,
) -> OrderCreatedOut:
    limiters.orders.hit(f"order:{client_ip(request, settings)}")
    # Verified identity only: initDataUnsafe or a bare user id from the client is never trusted.
    telegram_user = await telegram.verify(x_telegram_init_data) if x_telegram_init_data else None
    channel = "telegram" if telegram_user else channel_of(request)
    order, created = await orders.checkout(
        x_cart_token, idempotency_key, body, channel, telegram_user.id if telegram_user else None
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return OrderCreatedOut(order=await orders.view(order), order_token=orders.access_token(order))


@router.get("/orders/{order_token}", response_model=OrderOut)
async def get_order(order_token: str, orders: FromDishka[OrderService]) -> OrderOut:
    return await orders.view(await orders.get_by_token(order_token))


@router.post("/orders/{order_token}/cancel", response_model=OrderOut)
async def cancel_order(order_token: str, orders: FromDishka[OrderService]) -> OrderOut:
    return await orders.view(await orders.cancel_by_customer(order_token))
