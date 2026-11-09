from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration. Values come from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Application role: no table ownership, no BYPASSRLS (ADR-0002).
    database_url: str = "postgresql+asyncpg://delivery_app:delivery_app@localhost:5432/delivery"
    # Owner role, used only by migrations and platform CLI.
    migrator_database_url: str = "postgresql+asyncpg://delivery:delivery@localhost:5432/delivery"
    db_pool_size: int = 10

    # Used to derive order access tokens (HMAC) and must stay stable across restarts.
    session_secret: SecretStr = SecretStr("dev-only-session-secret-change-me-0123456789")
    # Fernet key (urlsafe base64, 32 bytes) for secrets stored in the DB: bot tokens, provider keys.
    encryption_key: SecretStr = SecretStr("pZ6yRrFv0wXc1oB8x3m3wQ0fJv0sZr1C2kX6l0n0q2Y=")

    # Hosts on which the API is reachable without tenant context (mobile uses X-Tenant there).
    platform_api_hosts: list[str] = Field(default_factory=lambda: ["api.localhost"])
    # Only trust X-Forwarded-Host from the reverse proxy.
    trust_forwarded_host: bool = False
    cors_origins: list[str] = Field(default_factory=list)

    staff_session_ttl_days: int = 14
    telegram_init_data_max_age_seconds: int = 86_400
    telegram_api_base: str = "https://api.telegram.org"
    admin_base_url: str | None = None  # links in staff notifications
    # Address suggestions with coordinates (required for delivery zones). "demo" = fixed Sochi addresses for
    # local development and E2E; refused in production.
    geocoder: Literal["none", "dadata", "demo"] = "none"
    dadata_api_key: SecretStr | None = None

    cart_ttl_days: int = 30
    order_rate_limit_per_minute: int = 10
    login_rate_limit_per_minute: int = 10

    outbox_poll_interval_seconds: float = 3.0
    outbox_max_attempts: int = 10

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self) -> "Settings":
        if self.environment == "production":
            for name in ("session_secret", "encryption_key"):
                default = type(self).model_fields[name].default
                if getattr(self, name).get_secret_value() == default.get_secret_value():
                    raise ValueError(f"{name.upper()} must be set in production")
            if self.geocoder == "demo":
                raise ValueError("GEOCODER=demo is not allowed in production")
        if self.geocoder == "dadata" and not self.dadata_api_key:
            raise ValueError("GEOCODER=dadata requires DADATA_API_KEY")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
