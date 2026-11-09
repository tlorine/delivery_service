"""Outbox processor (ADR-0006): at-least-once delivery with exponential backoff."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import bind_tenant
from app.modules.notifications.models import OutboxEvent

log = logging.getLogger("app.outbox")

Handler = Callable[[AsyncSession, uuid.UUID, dict[str, Any]], Awaitable[None]]


class RetryLater(Exception):
    def __init__(self, delay_seconds: int) -> None:
        super().__init__(f"retry in {delay_seconds}s")
        self.delay_seconds = delay_seconds


def backoff(attempt: int) -> timedelta:
    return timedelta(seconds=min(5 * 2 ** (attempt - 1), 3600))


class OutboxProcessor:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        handlers: dict[str, list[Handler]],
        clock: Clock,
        settings: Settings,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.handlers = handlers
        self.clock = clock
        self.settings = settings

    async def process_one(self) -> bool:
        """Claim and process a single due event in its own transaction. Returns False when idle."""
        async with self.sessionmaker() as session:
            event = await session.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending", OutboxEvent.available_at <= self.clock.now())
                .order_by(OutboxEvent.available_at, OutboxEvent.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if event is None:
                return False
            # Handlers see only this tenant's rows (RLS), even though the outbox is cross-tenant.
            await bind_tenant(session, event.tenant_id)
            event.attempts += 1
            try:
                for handler in self.handlers.get(event.type, []):
                    await handler(session, event.tenant_id, event.payload)
            except Exception as exc:
                delay = (
                    exc.delay_seconds if isinstance(exc, RetryLater) else int(backoff(event.attempts).total_seconds())
                )
                failed = event.attempts >= self.settings.outbox_max_attempts
                event.status = "failed" if failed else "pending"
                event.available_at = self.clock.now() + timedelta(seconds=delay)
                cause = exc.__cause__ if isinstance(exc, RetryLater) and exc.__cause__ else exc
                event.last_error = f"{type(cause).__name__}: {cause}"[:2000]
                log.warning(
                    "outbox event failed",
                    extra={
                        "event_id": event.id,
                        "type": event.type,
                        "attempt": event.attempts,
                        "final": failed,
                        "error": type(cause).__name__,
                    },
                )
            else:
                event.status = "done"
                event.processed_at = self.clock.now()
                event.last_error = None
            await session.commit()
            return True

    async def drain(self, limit: int = 1000) -> int:
        n = 0
        while n < limit and await self.process_one():
            n += 1
        return n

    async def run_forever(self, stop: asyncio.Event, wake: asyncio.Event) -> None:
        log.info("outbox worker started")
        while not stop.is_set():
            wake.clear()
            try:
                processed = await self.drain(100)
            except Exception:
                log.exception("outbox loop error")
                processed = 0
            if processed == 0:
                waiters = {asyncio.create_task(stop.wait()), asyncio.create_task(wake.wait())}
                _, pending = await asyncio.wait(
                    waiters,
                    timeout=self.settings.outbox_poll_interval_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
        log.info("outbox worker stopped")


async def listen_for_wakeups(dsn: str, wake: asyncio.Event) -> None:
    """LISTEN outbox: wake the loop right after a commit instead of waiting for the poll interval."""
    import asyncpg

    conn = await asyncpg.connect(dsn.replace("postgresql+asyncpg://", "postgresql://"))  # type: ignore[no-untyped-call]
    await conn.add_listener("outbox", lambda *_: wake.set())
    try:
        await asyncio.Event().wait()
    finally:
        await conn.close()
