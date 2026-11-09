import uuid

from sqlalchemy import BigInteger, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class TelegramBot(IdMixin, TimestampMixin, Base):
    """The tenant's own bot. Routing table: looked up by bot id from webhooks (no RLS)."""

    __tablename__ = "telegram_bots"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), unique=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # numeric prefix of the token
    username: Mapped[str] = mapped_column(String(64))
    token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    webhook_secret: Mapped[str] = mapped_column(String(64))
    notify_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(default=True)
