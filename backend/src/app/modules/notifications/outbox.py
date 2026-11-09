import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import OutboxEvent


class OutboxEventType:
    ORDER_CREATED = "order.created"
    ORDER_STATUS_CHANGED = "order.status_changed"


def emit(session: AsyncSession, tenant_id: uuid.UUID, event_type: str, payload: dict[str, Any]) -> None:
    """Add an event to the caller's transaction. Payload carries ids only: no personal data in the queue."""
    session.add(OutboxEvent(tenant_id=tenant_id, type=event_type, payload=payload))


async def wake_worker(session: AsyncSession) -> None:
    """NOTIFY is delivered on commit, so the worker never sees an event before it exists."""
    await session.execute(text("NOTIFY outbox"))
