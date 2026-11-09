from typing import Any

import httpx


class TelegramApiError(Exception):
    def __init__(self, description: str, retry_after: int | None = None) -> None:
        super().__init__(description)
        self.retry_after = retry_after


class TelegramBotApi:
    """Thin Bot API client: we need a handful of methods, not an SDK (integrations.md)."""

    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")

    async def call(self, token: str, method: str, payload: dict[str, Any]) -> Any:
        response = await self.http.post(f"{self.base_url}/bot{token}/{method}", json=payload, timeout=10.0)
        data = response.json()
        if not data.get("ok"):
            params = data.get("parameters") or {}
            raise TelegramApiError(str(data.get("description", response.status_code)), params.get("retry_after"))
        return data["result"]

    async def send_message(
        self, token: str, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        await self.call(token, "sendMessage", payload)
