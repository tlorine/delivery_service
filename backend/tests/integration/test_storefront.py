from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import make_client
from tests.integration.factories import make_cafe


async def test_tenant_is_resolved_from_host(app: Any, owner_session: AsyncSession) -> None:
    await make_cafe(owner_session, "a", "cafe-a.test")
    async with make_client(app, "cafe-a.test") as c:
        r = await c.get("/v1/storefront")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "a"
    assert body["currency"] == "RUB"
    assert body["branches"][0]["is_open_now"] is True
    assert body["branches"][0]["timezone"] == "Europe/Moscow"


async def test_unknown_host_is_404_problem(app: Any, owner_session: AsyncSession) -> None:
    await make_cafe(owner_session, "a", "cafe-a.test")
    async with make_client(app, "nobody.test") as c:
        r = await c.get("/v1/storefront")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "tenant_not_found"


async def test_x_tenant_only_honoured_on_platform_api_host(app: Any, owner_session: AsyncSession) -> None:
    await make_cafe(owner_session, "a", "cafe-a.test")
    await make_cafe(owner_session, "b", "cafe-b.test")
    async with make_client(app, "api.platform.test", **{"X-Tenant": "b"}) as c:
        assert (await c.get("/v1/storefront")).json()["slug"] == "b"
    # On a cafe's own domain the header cannot switch tenants.
    async with make_client(app, "cafe-a.test", **{"X-Tenant": "b"}) as c:
        assert (await c.get("/v1/storefront")).json()["slug"] == "a"


async def test_menu_has_modifiers_and_integer_prices(app: Any, owner_session: AsyncSession) -> None:
    await make_cafe(owner_session, "a", "cafe-a.test")
    async with make_client(app, "cafe-a.test") as c:
        menu = (await c.get("/v1/storefront/menu")).json()
    shawarma = next(p for cat in menu["categories"] for p in cat["products"] if p["slug"] == "classic-shawarma")
    assert [v["price_minor"] for v in shawarma["variants"]] == [32_000, 42_000]
    assert {g["name"] for g in shawarma["modifier_groups"]} == {"Соус", "Добавки"}


async def test_health(app: Any) -> None:
    async with make_client(app, "anything") as c:
        assert (await c.get("/health/live")).json() == {"status": "ok"}
        assert (await c.get("/health/ready")).json() == {"status": "ok"}


async def test_address_suggest_without_provider_is_empty(app: Any, owner_session: AsyncSession) -> None:
    await make_cafe(owner_session, "a", "cafe-a.test")
    async with make_client(app, "cafe-a.test") as c:
        r = await c.get("/v1/address/suggest", params={"q": "Навагинская"})
        assert (r.status_code, r.json()) == (200, [])
        assert (await c.get("/v1/address/suggest", params={"q": "ab"})).status_code == 422
