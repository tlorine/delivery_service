import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import tenant_of
from app.modules.audit.models import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def record(
        self,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        *,
        actor_type: str,
        actor_id: uuid.UUID | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Added to the caller's transaction: the audit entry commits or rolls back with the change."""
        self.session.add(
            AuditLog(
                tenant_id=tenant_of(self.session),
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                data=data or {},
            )
        )
