from sqlalchemy import BigInteger, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantMixin, TimestampMixin


class Customer(IdMixin, TenantMixin, TimestampMixin, Base):
    """A buyer of one tenant. The same person at two cafes is two customers (no cross-tenant profile)."""

    __tablename__ = "customers"

    phone: Mapped[str | None] = mapped_column(String(16))  # E.164
    name: Mapped[str | None] = mapped_column(String(200))
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index(
            "uq_customers_phone",
            "tenant_id",
            "phone",
            unique=True,
            postgresql_where=text("phone is not null"),
        ),
        Index(
            "uq_customers_telegram",
            "tenant_id",
            "telegram_user_id",
            unique=True,
            postgresql_where=text("telegram_user_id is not null"),
        ),
    )
