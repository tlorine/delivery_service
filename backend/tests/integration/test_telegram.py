import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import SecretBox
from app.modules.customers.models import Customer
from app.modules.ordering.models import Order
from app.modules.telegram.models import TelegramBot
from app.modules.telegram.service import link_code
from tests.integration.conftest import OPEN_TIME, make_client
from tests.integration.factories import Cafe, add, make_cafe, new_cart, order_body

pytestmark = pytest.mark.asyncio


def signed_init_data(bot_token: str, user_id: int = 42, auth_date: datetime = OPEN_TIME) -> str:
    fields = {
        "auth_date": str(int(auth_date.timestamp())),
        "user": json.dumps({"id": user_id, "first_name": "Анна"}),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


@pytest.fixture
async def cafes(owner_session: AsyncSession, settings: Settings) -> tuple[Cafe, Cafe]:
    box = SecretBox(settings.encryption_key.get_secret_value())
    return (
        await make_cafe(owner_session, "a", "cafe-a.test", box, chat_id=None),
        await make_cafe(owner_session, "b", "cafe-b.test", box, chat_id=None),
    )


async def bot_of(session: AsyncSession, cafe: Cafe, settings: Settings) -> tuple[TelegramBot, str]:
    bot = await session.scalar(select(TelegramBot).where(TelegramBot.tenant_id == cafe.id))
    assert bot is not None
    return bot, SecretBox(settings.encryption_key.get_secret_value()).decrypt(bot.token_encrypted)


async def checkout_with(app: Any, cafe: Cafe, init_data: str | None) -> Any:
    async with make_client(app, cafe.host) as c:
        token = await new_cart(c)
        await add(c, token, cafe.variants["double-burger/Стандарт"], 2)
        headers = {"X-Cart-Token": token, "Idempotency-Key": uuid.uuid4().hex}
        if init_data is not None:
            headers["X-Telegram-Init-Data"] = init_data
        return await c.post("/v1/orders", json=order_body(), headers=headers)


async def test_order_from_mini_app_is_linked_to_telegram_user(
    app: Any, cafes: tuple[Cafe, Cafe], owner_session: AsyncSession, settings: Settings
) -> None:
    a, _ = cafes
    _, token = await bot_of(owner_session, a, settings)
    r = await checkout_with(app, a, signed_init_data(token, user_id=777))
    assert r.status_code == 201, r.text
    order = await owner_session.get(Order, uuid.UUID(r.json()["order"]["id"]))
    assert order is not None
    assert order.channel == "telegram"
    customer = await owner_session.get(Customer, order.customer_id)
    assert customer is not None
    assert customer.telegram_user_id == 777


async def test_init_data_signed_by_another_cafes_bot_is_refused(
    app: Any, cafes: tuple[Cafe, Cafe], owner_session: AsyncSession, settings: Settings
) -> None:
    a, b = cafes
    _, token_b = await bot_of(owner_session, b, settings)
    r = await checkout_with(app, a, signed_init_data(token_b))
    assert (r.status_code, r.json()["code"]) == (401, "invalid_init_data")


async def test_forged_or_stale_init_data_is_refused(
    app: Any, cafes: tuple[Cafe, Cafe], owner_session: AsyncSession, settings: Settings
) -> None:
    a, _ = cafes
    _, token = await bot_of(owner_session, a, settings)
    forged = signed_init_data(token).replace("%22id%22%3A+42", "%22id%22%3A+1")
    assert (await checkout_with(app, a, forged)).status_code == 401
    stale = signed_init_data(token, auth_date=datetime(2026, 11, 1, tzinfo=UTC))
    assert (await checkout_with(app, a, stale)).status_code == 401


async def test_telegram_account_moves_with_new_phone(
    app: Any, cafes: tuple[Cafe, Cafe], owner_session: AsyncSession, settings: Settings
) -> None:
    a, _ = cafes
    _, token = await bot_of(owner_session, a, settings)
    assert (await checkout_with(app, a, signed_init_data(token, user_id=5))).status_code == 201
    async with make_client(app, a.host) as c:
        cart = await new_cart(c)
        await add(c, cart, a.variants["double-burger/Стандарт"], 2)
        r = await c.post(
            "/v1/orders",
            json=order_body(customer={"name": "Анна", "phone": "+7 999 000 11 22"}),
            headers={
                "X-Cart-Token": cart,
                "Idempotency-Key": uuid.uuid4().hex,
                "X-Telegram-Init-Data": signed_init_data(token, user_id=5),
            },
        )
    assert r.status_code == 201, r.text
    linked = (await owner_session.scalars(select(Customer).where(Customer.telegram_user_id == 5))).all()
    assert [c.phone for c in linked] == ["+79990001122"]


async def test_webhook_requires_the_bot_secret(
    app: Any, cafes: tuple[Cafe, Cafe], owner_session: AsyncSession, settings: Settings
) -> None:
    bot, _ = await bot_of(owner_session, cafes[0], settings)
    update = {"message": {"text": "/start", "chat": {"id": 1, "type": "private"}}}
    async with make_client(app, "api.platform.test") as c:
        r = await c.post(f"/v1/telegram/webhook/{bot.bot_id}", json=update)
        assert r.status_code == 401
        r = await c.post(
            f"/v1/telegram/webhook/{bot.bot_id}", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}
        )
        assert r.status_code == 401
        r = await c.post(
            f"/v1/telegram/webhook/{bot.bot_id}",
            json=update,
            headers={"X-Telegram-Bot-Api-Secret-Token": bot.webhook_secret},
        )
    assert r.status_code == 200
    reply = r.json()
    assert reply["method"] == "sendMessage"
    assert reply["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"] == "https://cafe-a.test/"


async def test_link_command_connects_staff_chat(
    app: Any, cafes: tuple[Cafe, Cafe], owner_session: AsyncSession, settings: Settings
) -> None:
    bot, _ = await bot_of(owner_session, cafes[0], settings)
    headers = {"X-Telegram-Bot-Api-Secret-Token": bot.webhook_secret}
    good = link_code(settings.session_secret.get_secret_value(), bot.bot_id)
    async with make_client(app, "api.platform.test") as c:
        bad = await c.post(
            f"/v1/telegram/webhook/{bot.bot_id}",
            headers=headers,
            json={"message": {"text": "/link nope", "chat": {"id": -100500, "type": "group"}}},
        )
        assert "Неверный" in bad.json()["text"]
        ok = await c.post(
            f"/v1/telegram/webhook/{bot.bot_id}",
            headers=headers,
            json={"message": {"text": f"/link@a_bot {good}", "chat": {"id": -100500, "type": "group"}}},
        )
    assert "Готово" in ok.json()["text"]
    await owner_session.refresh(bot)
    assert bot.notify_chat_id == -100500


async def test_mini_app_buyer_gets_status_updates(
    app: Any, container: Any, cafes: tuple[Cafe, Cafe], owner_session: AsyncSession, settings: Settings, telegram: Any
) -> None:
    from app.modules.notifications.worker import OutboxProcessor
    from tests.integration.factories import login

    a, _ = cafes
    _, token = await bot_of(owner_session, a, settings)
    created = (await checkout_with(app, a, signed_init_data(token, user_id=4242))).json()
    web_only = (await checkout_with(app, a, None)).json()
    async with make_client(app, "admin.platform.test") as admin:
        auth = {"Authorization": f"Bearer {await login(admin, a.operator_email)}"}
        for order in (created, web_only):
            await admin.post(
                f"/v1/admin/orders/{order['order']['id']}/transitions", headers=auth, json={"to_status": "confirmed"}
            )
    processor = await container.get(OutboxProcessor)
    await processor.drain()
    to_buyer = [p["text"] for m, p in telegram.calls if p["chat_id"] == 4242]
    assert to_buyer == [
        f"Заказ №{created['order']['number']} принят. Мы сообщим, когда его подтвердят.",
        f"Заказ №{created['order']['number']}: Подтверждён",
    ]
    # The web buyer has no Telegram identity: nothing is sent to anyone but staff chats (none configured here).
    assert all(p["chat_id"] == 4242 for _, p in telegram.calls)
