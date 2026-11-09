"""Database plumbing and the tenant guard.

Every transaction on a session bound to a tenant starts with
`set_config('app.tenant_id', <id>, true)`, which PostgreSQL RLS policies read (ADR-0002).
The hook runs on *every* transaction begin, so a commit followed by more work stays scoped.
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import BigInteger, DateTime, ForeignKeyConstraint, MetaData, event, func, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, SessionTransaction, mapped_column

from app.core.ids import new_id

TENANT_KEY = "tenant_id"

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map: ClassVar[dict[Any, Any]] = {int: BigInteger, datetime: DateTime(timezone=True)}


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TenantMixin:
    """Marks a table as tenant-scoped. The migration enables RLS on every table with this column."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True)


def create_engine(url: str, pool_size: int = 10) -> AsyncEngine:
    return create_async_engine(url, pool_size=pool_size, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@event.listens_for(Session, "after_begin")
def _apply_tenant(session: Session, _tx: SessionTransaction, connection: Connection) -> None:
    tenant_id = session.info.get(TENANT_KEY)
    # Empty string = "no tenant": RLS policies then match no rows.
    connection.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id) if tenant_id else ""})


async def bind_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Scope the session to a tenant, including the transaction that may already be open."""
    current = session.info.get(TENANT_KEY)
    if current is not None and current != tenant_id:
        raise RuntimeError("session is already bound to another tenant")
    session.info[TENANT_KEY] = tenant_id
    if session.in_transaction():
        await session.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})


def tenant_of(session: AsyncSession) -> uuid.UUID:
    tenant_id: Any = session.info.get(TENANT_KEY)
    if tenant_id is None:
        raise RuntimeError("session is not bound to a tenant")
    return uuid.UUID(str(tenant_id))


def tenant_fk(column: str, target: str, ondelete: str = "CASCADE") -> ForeignKeyConstraint:
    """Composite FK (tenant_id, <column>) -> <target>(tenant_id, id).

    The referenced row must belong to the same tenant, so a bug cannot link an order to another
    tenant's branch or product. A NULL in <column> skips the check (MATCH SIMPLE).
    """
    return ForeignKeyConstraint(["tenant_id", column], [f"{target}.tenant_id", f"{target}.id"], ondelete=ondelete)
