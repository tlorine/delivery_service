import hashlib
import hmac
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import bind_tenant
from app.core.errors import NotFound, Unauthorized
from app.core.security import SecretBox
from app.modules.telegram.init_data import TelegramUser, verify_init_data
from app.modules.telegram.models import TelegramBot
from app.modules.tenancy.context import TenantContext
from app.modules.tenancy.models import Tenant, TenantDomain


def link_code(secret: str, bot_id: int) -> str:
    """Stateless code that connects a staff chat to the cafe's bot (`/link <code>` in the chat)."""
    return hmac.new(secret.encode(), f"tg-link:{bot_id}".encode(), hashlib.sha256).hexdigest()[:12]


class TelegramIdentity:
    """Verifies Mini App initData with the bot of the *current* tenant (ADR-0007)."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, box: SecretBox, clock: Clock, settings: Settings):
        self.session = session
        self.tenant = tenant
        self.box = box
        self.clock = clock
        self.settings = settings

    async def verify(self, init_data: str) -> TelegramUser:
        from datetime import timedelta

        bot = await self.session.scalar(
            select(TelegramBot).where(TelegramBot.tenant_id == self.tenant.id, TelegramBot.is_active.is_(True))
        )
        if bot is None:
            raise Unauthorized("this storefront has no Telegram bot", code="invalid_init_data")
        verified = verify_init_data(
            init_data,
            self.box.decrypt(bot.token_encrypted),
            self.clock.now(),
            timedelta(seconds=self.settings.telegram_init_data_max_age_seconds),
        )
        return verified.user


class TelegramWebhook:
    """Updates from a tenant's bot. Replies are returned as the webhook response (no extra API call)."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def bot(self, bot_id: int, secret_header: str | None) -> TelegramBot:
        bot = await self.session.scalar(select(TelegramBot).where(TelegramBot.bot_id == bot_id))
        if bot is None or not bot.is_active:
            raise NotFound()
        if not secret_header or not hmac.compare_digest(secret_header, bot.webhook_secret):
            raise Unauthorized("bad webhook secret", code="invalid_webhook_secret")
        return bot

    async def storefront_url(self, bot: TelegramBot) -> str | None:
        host = await self.session.scalar(
            select(TenantDomain.host)
            .where(TenantDomain.tenant_id == bot.tenant_id)
            .order_by(TenantDomain.is_primary.desc(), TenantDomain.host)
        )
        return f"https://{host}/" if host else None

    async def handle(self, bot: TelegramBot, update: dict[str, Any]) -> dict[str, Any] | None:
        message = update.get("message") or {}
        text = str(message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if not text.startswith("/") or chat_id is None:
            return None
        command, _, arg = text.partition(" ")
        command = command.split("@", 1)[0].lower()

        if command == "/start":
            tenant = await self.session.get(Tenant, bot.tenant_id)
            url = await self.storefront_url(bot)
            reply: dict[str, Any] = {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": f"Здравствуйте! Это {tenant.name if tenant else 'наше кафе'}. "
                "Откройте меню, чтобы сделать заказ.",
            }
            if url and chat.get("type") == "private":
                reply["reply_markup"] = {"inline_keyboard": [[{"text": "Открыть меню", "web_app": {"url": url}}]]}
            return reply

        if command == "/link":
            expected = link_code(self.settings.session_secret.get_secret_value(), bot.bot_id)
            if not hmac.compare_digest(arg.strip(), expected):
                return {"method": "sendMessage", "chat_id": chat_id, "text": "Неверный код подключения."}
            # Routing table without RLS; still bind for the audit trail of this tenant.
            await bind_tenant(self.session, bot.tenant_id)
            bot.notify_chat_id = int(chat_id)
            await self.session.commit()
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "Готово: новые заказы будут приходить в этот чат.",
            }
        return None
