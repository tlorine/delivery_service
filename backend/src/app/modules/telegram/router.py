from typing import Annotated, Any

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response

from app.modules.telegram.service import TelegramWebhook

router = APIRouter(prefix="/v1/telegram", tags=["telegram"], route_class=DishkaRoute)


@router.post("/webhook/{bot_id}", include_in_schema=False)
async def webhook(
    bot_id: int,
    request: Request,
    hook: FromDishka[TelegramWebhook],
    secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> Response:
    bot = await hook.bot(bot_id, secret)
    update: dict[str, Any] = await request.json()
    reply = await hook.handle(bot, update)
    return JSONResponse(reply) if reply else Response(status_code=200)
