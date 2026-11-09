"""Outbox handlers: route domain events to notification channels.

The domain only emits events; Telegram is one channel among possible others (e-mail, SMS, push).
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import SecretBox
from app.modules.customers.models import Customer
from app.modules.notifications.outbox import OutboxEventType
from app.modules.notifications.templates import new_order_message, status_message
from app.modules.notifications.worker import Handler, RetryLater
from app.modules.ordering.models import Order
from app.modules.ordering.read import load_order_views
from app.modules.telegram.client import TelegramApiError, TelegramBotApi
from app.modules.telegram.models import TelegramBot
from app.modules.tenancy.models import Branch

log = logging.getLogger("app.notifications")


class TelegramStaffNotifier:
    """Messages to the cafe's staff chat through the cafe's own bot."""

    def __init__(self, api: TelegramBotApi, box: SecretBox, settings: Settings) -> None:
        self.api = api
        self.box = box
        self.settings = settings

    async def _bot(self, session: AsyncSession, tenant_id: uuid.UUID) -> TelegramBot | None:
        bot = await session.scalar(
            select(TelegramBot).where(TelegramBot.tenant_id == tenant_id, TelegramBot.is_active.is_(True))
        )
        if bot is None or bot.notify_chat_id is None:
            log.info("telegram notification skipped: no bot or chat", extra={"tenant_id": str(tenant_id)})
            return None
        return bot

    async def _send(self, bot: TelegramBot, text: str) -> None:
        assert bot.notify_chat_id is not None
        try:
            await self.api.send_message(self.box.decrypt(bot.token_encrypted), bot.notify_chat_id, text)
        except TelegramApiError as exc:
            if exc.retry_after:
                raise RetryLater(exc.retry_after) from exc
            raise

    async def on_order_created(self, session: AsyncSession, tenant_id: uuid.UUID, payload: dict[str, Any]) -> None:
        bot = await self._bot(session, tenant_id)
        if bot is None:
            return
        order = await session.scalar(
            select(Order).where(Order.tenant_id == tenant_id, Order.id == uuid.UUID(payload["order_id"]))
        )
        if order is None:
            return
        branch = await session.scalar(select(Branch).where(Branch.tenant_id == tenant_id, Branch.id == order.branch_id))
        view = (await load_order_views(session, tenant_id, [order]))[0]
        admin_url = (
            f"{self.settings.admin_base_url.rstrip('/')}/orders/{order.id}" if self.settings.admin_base_url else None
        )
        await self._send(bot, new_order_message(view, branch.timezone if branch else "Europe/Moscow", admin_url))

    async def on_status_changed(self, session: AsyncSession, tenant_id: uuid.UUID, payload: dict[str, Any]) -> None:
        # Staff already see their own actions in the admin panel; only a customer cancellation is news to them.
        if payload.get("to") != "cancelled":
            return
        bot = await self._bot(session, tenant_id)
        if bot is None:
            return
        order = await session.scalar(
            select(Order).where(Order.tenant_id == tenant_id, Order.id == uuid.UUID(payload["order_id"]))
        )
        if order is None:
            return
        view = (await load_order_views(session, tenant_id, [order]))[0]
        last = view.history[-1] if view.history else None
        if last is None or last.actor_type != "customer":
            return
        await self._send(bot, "❌ " + status_message(view) + " (покупателем)")


class TelegramCustomerNotifier:
    """Status updates to buyers who ordered from the Mini App (they started the cafe's bot)."""

    def __init__(self, api: TelegramBotApi, box: SecretBox) -> None:
        self.api = api
        self.box = box

    async def on_event(self, session: AsyncSession, tenant_id: uuid.UUID, payload: dict[str, Any]) -> None:
        row = (
            await session.execute(
                select(Order, Customer.telegram_user_id)
                .join(Customer, (Customer.id == Order.customer_id) & (Customer.tenant_id == tenant_id))
                .where(Order.tenant_id == tenant_id, Order.id == uuid.UUID(payload["order_id"]))
            )
        ).first()
        if row is None:
            return
        order, telegram_user_id = row
        if telegram_user_id is None or order.channel != "telegram":
            return
        bot = await session.scalar(
            select(TelegramBot).where(TelegramBot.tenant_id == tenant_id, TelegramBot.is_active.is_(True))
        )
        if bot is None:
            return
        view = (await load_order_views(session, tenant_id, [order]))[0]
        text = (
            f"Заказ №{view.number} принят. Мы сообщим, когда его подтвердят."
            if "to" not in payload
            else status_message(view)
        )
        try:
            await self.api.send_message(self.box.decrypt(bot.token_encrypted), telegram_user_id, text)
        except TelegramApiError as exc:
            if exc.retry_after:
                raise RetryLater(exc.retry_after) from exc
            # 403: the user blocked the bot - nothing to retry.
            log.info("customer notification not delivered", extra={"tenant_id": str(tenant_id)})


def build_handlers(staff: TelegramStaffNotifier, customer: TelegramCustomerNotifier) -> dict[str, list[Handler]]:
    """Each event fans out to channels. A failing channel retries the event; handlers must be idempotent
    enough for at-least-once delivery (a duplicate message is acceptable, a lost order is not)."""
    return {
        OutboxEventType.ORDER_CREATED: [staff.on_order_created, customer.on_event],
        OutboxEventType.ORDER_STATUS_CHANGED: [staff.on_status_changed, customer.on_event],
    }
