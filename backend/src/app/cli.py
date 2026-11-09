"""Platform CLI (owner role): `python -m app.cli <command>`. Run migrations first: `alembic upgrade head`."""

import argparse
import asyncio
import getpass
import os
import secrets
import sys
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.security import SecretBox
from app.modules.identity.models import Role
from app.modules.telegram.client import TelegramBotApi
from app.modules.telegram.models import TelegramBot
from app.modules.telegram.service import link_code
from app.modules.tenancy.models import Tenant, TenantDomain
from app.seed import create_staff, create_tenant, seed_demo, set_telegram_bot


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_engine(settings.migrator_database_url, 2)
    sm = create_sessionmaker(engine)
    try:
        async with sm() as session:
            if args.command == "seed-demo":
                tenant = await seed_demo(
                    session, args.slug, tuple(args.host), always_open=args.always_open, name=args.name
                )
                password = os.environ.get("DEMO_OWNER_PASSWORD") or secrets.token_urlsafe(12)
                await create_staff(session, tenant.id, args.owner_email, "Владелец", password, Role.OWNER)
                await session.commit()
                print(f"tenant {tenant.slug} ({tenant.id}); hosts: {', '.join(args.host)}")
                print(f"owner login: {args.owner_email} / {password}")
                return

            if args.command == "create-tenant":
                tenant = await create_tenant(session, args.slug, args.name, args.host, args.timezone)
                await session.commit()
                print(tenant.id)
                return

            found = await session.scalar(select(Tenant).where(Tenant.slug == args.tenant))
            if found is None:
                sys.exit(f"tenant '{args.tenant}' not found")
            tenant = found
            if args.command == "create-staff":
                password = os.environ.get("STAFF_PASSWORD") or getpass.getpass("Password: ")
                if len(password) < 10:
                    sys.exit("password must be at least 10 characters")
                await create_staff(session, tenant.id, args.email, args.name, password, Role(args.role))
            elif args.command == "telegram-setup":
                await telegram_setup(session, settings, tenant.id, args.public_url)
                return
            elif args.command == "set-telegram-bot":
                token = os.environ.get("TELEGRAM_BOT_TOKEN") or getpass.getpass("Bot token: ")
                bot = await set_telegram_bot(
                    session,
                    SecretBox(settings.encryption_key.get_secret_value()),
                    tenant.id,
                    token,
                    args.username,
                    args.chat_id,
                    secrets.token_urlsafe(24),
                )
                print(f"bot {bot.username} linked; webhook secret stored")
            await session.commit()
    finally:
        await engine.dispose()


async def telegram_setup(session: AsyncSession, settings: Settings, tenant_id: uuid.UUID, public_url: str) -> None:
    """Point the cafe's bot at this deployment: webhook (with secret) + menu button opening the storefront."""
    bot = await session.scalar(select(TelegramBot).where(TelegramBot.tenant_id == tenant_id))
    if bot is None:
        sys.exit("run set-telegram-bot first")
    host = await session.scalar(
        select(TenantDomain.host).where(TenantDomain.tenant_id == tenant_id).order_by(TenantDomain.is_primary.desc())
    )
    token = SecretBox(settings.encryption_key.get_secret_value()).decrypt(bot.token_encrypted)
    base = public_url.rstrip("/")
    async with httpx.AsyncClient() as http:
        api = TelegramBotApi(http, settings.telegram_api_base)
        await api.call(
            token,
            "setWebhook",
            {
                "url": f"{base}/v1/telegram/webhook/{bot.bot_id}",
                "secret_token": bot.webhook_secret,
                "allowed_updates": ["message"],
            },
        )
        if host:
            await api.call(
                token,
                "setChatMenuButton",
                {
                    "menu_button": {"type": "web_app", "text": "Меню", "web_app": {"url": f"https://{host}/"}},
                },
            )
    print(f"webhook: {base}/v1/telegram/webhook/{bot.bot_id}")
    print(f"menu button opens: https://{host}/" if host else "no domain: menu button not set")
    code = link_code(settings.session_secret.get_secret_value(), bot.bot_id)
    print(f"staff chat: add @{bot.username} to the group and send /link {code}")


def main() -> None:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("seed-demo", help="demo cafe with menu, branch and delivery zone")
    d.add_argument("--slug", default="demo")
    d.add_argument("--host", action="append", default=None)
    d.add_argument("--owner-email", default="owner@demo.local")
    d.add_argument("--always-open", action="store_true", help="24/7 hours (E2E)")
    d.add_argument("--name", default="Демо-кафе «У моря»")
    t = sub.add_parser("create-tenant")
    t.add_argument("slug")
    t.add_argument("name")
    t.add_argument("--host", action="append", required=True)
    t.add_argument("--timezone", default="Europe/Moscow")
    s = sub.add_parser("create-staff", help="password from STAFF_PASSWORD or prompt")
    s.add_argument("tenant")
    s.add_argument("email")
    s.add_argument("name")
    s.add_argument("--role", choices=[r.value for r in Role], default="operator")
    b = sub.add_parser("set-telegram-bot", help="token from TELEGRAM_BOT_TOKEN or prompt")
    b.add_argument("tenant")
    b.add_argument("username")
    b.add_argument("--chat-id", type=int)
    ts = sub.add_parser("telegram-setup", help="register webhook and Mini App menu button; prints the /link code")
    ts.add_argument("tenant")
    ts.add_argument("--public-url", required=True, help="HTTPS base URL where /v1 of this API is reachable")
    args = p.parse_args()
    if args.command == "seed-demo" and not args.host:
        args.host = ["localhost", "127.0.0.1"]
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
