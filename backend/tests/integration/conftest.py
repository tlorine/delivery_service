"""Test infrastructure: a real PostgreSQL with the real migrations, the app role subject to RLS, a fake clock
and a fake Telegram API. Configure with TEST_DATABASE_URL / TEST_MIGRATOR_DATABASE_URL."""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from dishka import Provider, Scope, provide
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import create_engine, create_sessionmaker
from app.di import build_container
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[2]
APP_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://delivery_app:delivery_app@localhost:54329/delivery_test"
)
OWNER_URL = os.environ.get(
    "TEST_MIGRATOR_DATABASE_URL", "postgresql+asyncpg://delivery:delivery@localhost:54329/delivery_test"
)

# Tuesday 2026-11-10 12:00 in Sochi (UTC+3): the demo branch (10:00-23:00) is open.
OPEN_TIME = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


@dataclass
class FakeTelegram:
    """Records Bot API calls; `fail_with` makes the next calls fail with this Bot API payload."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    fail_with: dict[str, Any] | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        import json

        method = request.url.path.rsplit("/", 1)[-1]
        if self.fail_with is not None:
            return httpx.Response(429, json=self.fail_with)
        self.calls.append((method, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.calls)}})


def _settings() -> Settings:
    return Settings(
        environment="test",
        database_url=APP_URL,
        migrator_database_url=OWNER_URL,
        db_pool_size=20,
        platform_api_hosts=["api.platform.test"],
        order_rate_limit_per_minute=10_000,
        login_rate_limit_per_minute=10_000,
        log_level="WARNING",
        admin_base_url="https://admin.platform.test",
    )


@pytest.fixture(scope="session")
def settings() -> Settings:
    return _settings()


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    env = {**os.environ, "ALEMBIC_DATABASE_URL": OWNER_URL}
    for args in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, check=True, capture_output=True)


@pytest.fixture(scope="session")
def clock() -> FakeClock:
    return FakeClock(OPEN_TIME)


@pytest.fixture(scope="session")
def telegram() -> FakeTelegram:
    return FakeTelegram()


@pytest.fixture(scope="session")
async def container(settings: Settings, clock: FakeClock, telegram: FakeTelegram) -> AsyncIterator[Any]:
    class TestOverrides(Provider):
        @provide(scope=Scope.APP, override=True)
        def clock(self) -> Clock:
            return clock

        @provide(scope=Scope.APP, override=True)
        async def http(self) -> AsyncIterator[httpx.AsyncClient]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(telegram.handler)) as client:
                yield client

    c = build_container(settings, TestOverrides())
    yield c
    await c.close()


@pytest.fixture(scope="session")
async def app(settings: Settings, container: Any) -> Any:
    return create_app(settings, container)


@pytest.fixture(scope="session")
async def owner_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine(OWNER_URL, 5)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db(owner_engine: AsyncEngine, clock: FakeClock, telegram: FakeTelegram) -> AsyncIterator[None]:
    clock.current = OPEN_TIME
    telegram.calls.clear()
    telegram.fail_with = None
    yield
    async with owner_engine.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT string_agg(quote_ident(tablename), ', ') FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
        ).scalar_one()
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def owner_session(owner_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Owner role: bypasses RLS. Only for arranging test data, like the platform CLI."""
    async with create_sessionmaker(owner_engine)() as session:
        yield session


def make_client(app: Any, host: str, **headers: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=f"http://{host}", headers=headers)
