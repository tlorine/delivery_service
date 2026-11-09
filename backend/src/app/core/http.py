from starlette.requests import Request

from app.core.config import Settings


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_forwarded_host:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def channel_of(request: Request) -> str:
    """Informational only (analytics, notifications); never used for authorization."""
    value = request.headers.get("x-client", "web").split("/")[0].strip().lower()
    return value if value in {"web", "telegram", "mobile"} else "web"
