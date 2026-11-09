import json

import httpx

from app.modules.delivery.geocoder import DadataGeocoder
from app.modules.delivery.provider import GeoPoint


async def test_dadata_maps_suggestions_and_restricts_to_branches() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "suggestions": [
                    {
                        "value": "г Сочи, ул Навагинская, д 9",
                        "data": {"geo_lat": "43.5815", "geo_lon": "39.72", "house": "9"},
                    },
                    {"value": "г Сочи, ул Навагинская", "data": {"geo_lat": None, "geo_lon": None, "house": None}},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await DadataGeocoder(http, "KEY").suggest("навагинская 9", [GeoPoint(43.58, 39.72)], 5)

    assert [(r.lat, r.lon, r.has_house) for r in result] == [(43.5815, 39.72, True), (None, None, False)]
    body = json.loads(seen[0].content)
    assert body["locations_geo"] == [{"lat": 43.58, "lon": 39.72, "radius_meters": 30_000}]
    assert seen[0].headers["Authorization"] == "Token KEY"


async def test_dadata_failure_degrades_to_no_suggestions() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as http:
        assert await DadataGeocoder(http, "KEY").suggest("abc", [], 5) == []


async def test_demo_geocoder_matches_all_words() -> None:
    from app.modules.delivery.geocoder import DemoGeocoder

    result = await DemoGeocoder().suggest("сочи навагинская", [], 5)
    assert [r.value for r in result] == ["г Сочи, ул Навагинская, д 9"]


def test_demo_geocoder_refused_in_production() -> None:
    import pytest

    from app.core.config import Settings

    with pytest.raises(ValueError, match="not allowed in production"):
        Settings(environment="production", session_secret="x" * 40, encryption_key="k" * 44, geocoder="demo")
