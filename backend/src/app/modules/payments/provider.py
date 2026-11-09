"""Payment port (docs/architecture/integrations.md). Card data never touches our system."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD_ON_DELIVERY = "card_on_delivery"
    ONLINE = "online"  # via a PaymentProvider (YooKassa, SBP) - after the pilot


class PaymentStatus(StrEnum):
    NOT_REQUIRED = "not_required"  # paid on receipt, the cafe's own cash register issues the receipt
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    REFUNDED = "refunded"


OFFLINE_METHODS = frozenset({PaymentMethod.CASH, PaymentMethod.CARD_ON_DELIVERY})


@dataclass(frozen=True, slots=True)
class PaymentInit:
    external_id: str
    confirmation_url: str | None


@dataclass(frozen=True, slots=True)
class PaymentWebhookEvent:
    external_event_id: str
    external_payment_id: str
    status: PaymentStatus


class PaymentProvider(Protocol):
    code: str

    async def create_payment(
        self, order_id: uuid.UUID, amount_minor: int, currency: str, idempotency_key: str, return_url: str
    ) -> PaymentInit: ...

    async def get_status(self, external_id: str) -> PaymentStatus: ...

    async def refund(self, external_id: str, amount_minor: int, idempotency_key: str) -> PaymentStatus: ...

    async def parse_webhook(self, headers: Mapping[str, str], body: bytes) -> PaymentWebhookEvent:
        """Must authenticate the notification (signature, or re-fetching the payment from the provider)."""
        ...


def initial_status(method: PaymentMethod) -> PaymentStatus:
    if method in OFFLINE_METHODS:
        return PaymentStatus.NOT_REQUIRED
    raise NotImplementedError("online payments are not enabled yet")  # gated by enabled_methods() below


def enabled_methods() -> frozenset[PaymentMethod]:
    """Methods the platform can process. ONLINE appears here once a provider adapter is configured."""
    return OFFLINE_METHODS
