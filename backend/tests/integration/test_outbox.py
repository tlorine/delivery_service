from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import SecretBox
from app.modules.notifications.models import OutboxEvent
from app.modules.notifications.worker import OutboxProcessor
from tests.integration.conftest import FakeClock, FakeTelegram, make_client
from tests.integration.factories import Cafe, add, make_cafe, new_cart, place

pytestmark = pytest.mark.asyncio
STAFF_CHAT = -100123


@pytest.fixture
async def cafe(owner_session: AsyncSession, settings: Settings) -> Cafe:
    return await make_cafe(
        owner_session, "a", "cafe-a.test", SecretBox(settings.encryption_key.get_secret_value()), STAFF_CHAT
    )


async def order(app: Any, cafe: Cafe) -> dict[str, Any]:
    async with make_client(app, cafe.host) as c:
        token = await new_cart(c)
        await add(c, token, cafe.variants["classic-shawarma/Стандарт"], 3, [(cafe.modifiers["Острый"], 1)])
        r = await place(c, token, comment="<b>домофон</b> не работает")
        assert r.status_code == 201
        result: dict[str, Any] = r.json()
        return result


async def test_new_order_reaches_staff_chat(app: Any, container: Any, cafe: Cafe, telegram: FakeTelegram) -> None:
    created = await order(app, cafe)
    processor = await container.get(OutboxProcessor)
    assert await processor.drain() == 1
    [(method, payload)] = telegram.calls
    assert method == "sendMessage"
    assert payload["chat_id"] == STAFF_CHAT
    text = payload["text"]
    assert f"Заказ №{created['order']['number']}" in text
    assert "Шаурма классическая" in text
    assert "+ Острый" in text
    assert "&lt;b&gt;домофон&lt;/b&gt;" in text  # customer input is HTML-escaped
    assert "1 110 ₽" in text  # 3 × 320 ₽ + 150 ₽ delivery
    assert created["order"]["id"] in text  # admin link
    assert await processor.drain() == 0


async def test_failure_is_retried_with_backoff(
    app: Any, container: Any, cafe: Cafe, telegram: FakeTelegram, clock: FakeClock, owner_session: AsyncSession
) -> None:
    await order(app, cafe)
    processor = await container.get(OutboxProcessor)
    telegram.fail_with = {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 7}}
    assert await processor.drain() == 1
    event = await owner_session.scalar(select(OutboxEvent))
    assert event is not None
    assert (event.status, event.attempts) == ("pending", 1)
    assert "Too Many Requests" in (event.last_error or "")
    assert await processor.drain() == 0  # not due yet

    telegram.fail_with = None
    clock.advance(seconds=8)
    assert await processor.drain() == 1
    await owner_session.refresh(event)
    assert (event.status, event.attempts) == ("done", 2)
    assert len(telegram.calls) == 1


async def test_customer_cancellation_is_announced_but_staff_actions_are_not(
    app: Any, container: Any, cafe: Cafe, telegram: FakeTelegram
) -> None:
    created = await order(app, cafe)
    async with make_client(app, cafe.host) as c:
        await c.post(f"/v1/orders/{created['order_token']}/cancel")
    processor = await container.get(OutboxProcessor)
    assert await processor.drain() == 2
    assert "покупателем" in telegram.calls[-1][1]["text"]


async def test_tenant_without_bot_is_skipped(
    app: Any, container: Any, owner_session: AsyncSession, telegram: FakeTelegram
) -> None:
    cafe = await make_cafe(owner_session, "nobot", "nobot.test")
    await order(app, cafe)
    processor = await container.get(OutboxProcessor)
    assert await processor.drain() == 1
    assert telegram.calls == []
