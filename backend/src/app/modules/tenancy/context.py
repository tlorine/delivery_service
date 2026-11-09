import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TenantContext:
    """The tenant of the current request, established by the server only (never from the request body)."""

    id: uuid.UUID
    slug: str
    name: str
    currency: str
    country: str
    locale: str
    timezone: str
    branding: dict[str, Any] = field(default_factory=dict)
