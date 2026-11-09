"""Address suggestions with coordinates (needed for delivery zones). Port + adapters."""

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.modules.delivery.provider import GeoPoint

log = logging.getLogger("app.geocoder")


@dataclass(frozen=True, slots=True)
class AddressSuggestion:
    value: str
    lat: float | None
    lon: float | None
    has_house: bool


class Geocoder(Protocol):
    async def suggest(self, query: str, near: list[GeoPoint], limit: int) -> list[AddressSuggestion]: ...


class NullGeocoder:
    """No provider configured: the storefront falls back to a free-text address."""

    async def suggest(self, query: str, near: list[GeoPoint], limit: int) -> list[AddressSuggestion]:
        return []


class DemoGeocoder:
    """Deterministic addresses in central Sochi (inside the demo zone) and Adler (outside). Dev/E2E only."""

    ADDRESSES = (
        AddressSuggestion("г Сочи, Курортный пр-кт, д 18", 43.5855, 39.7231, True),
        AddressSuggestion("г Сочи, ул Навагинская, д 9", 43.5815, 39.7200, True),
        AddressSuggestion("г Сочи, ул Воровского, д 22", 43.5843, 39.7262, True),
        AddressSuggestion("г Сочи, Адлерский р-н, ул Ленина, д 1", 43.4305, 39.9200, True),
    )

    async def suggest(self, query: str, near: list[GeoPoint], limit: int) -> list[AddressSuggestion]:
        words = query.lower().replace(",", " ").split()
        return [a for a in self.ADDRESSES if all(w in a.value.lower() for w in words)][:limit]


class DadataGeocoder:
    """DaData address suggestions (Russian addresses, FIAS-based, with coordinates for houses)."""

    URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"

    def __init__(self, http: httpx.AsyncClient, api_key: str, radius_meters: int = 30_000) -> None:
        self.http = http
        self.api_key = api_key
        self.radius_meters = radius_meters

    async def suggest(self, query: str, near: list[GeoPoint], limit: int) -> list[AddressSuggestion]:
        body: dict[str, Any] = {"query": query, "count": limit}
        if near:
            # Only addresses around the cafe's branches.
            body["locations_geo"] = [{"lat": p.lat, "lon": p.lon, "radius_meters": self.radius_meters} for p in near]
        try:
            response = await self.http.post(
                self.URL,
                json=body,
                timeout=3.0,
                headers={"Authorization": f"Token {self.api_key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            items = response.json().get("suggestions", [])
        except (httpx.HTTPError, ValueError) as exc:
            # Suggestions are a convenience: degrade to free text instead of failing checkout.
            log.warning("address suggest failed", extra={"error": type(exc).__name__})
            return []
        result = []
        for item in items:
            data = item.get("data") or {}
            lat, lon = data.get("geo_lat"), data.get("geo_lon")
            result.append(
                AddressSuggestion(
                    value=str(item.get("value", "")),
                    lat=float(lat) if lat else None,
                    lon=float(lon) if lon else None,
                    has_house=bool(data.get("house")),
                )
            )
        return result
