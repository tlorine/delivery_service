import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import Role
from app.seed import create_staff
from tests.integration.conftest import FakeClock, make_client
from tests.integration.factories import PASSWORD, Cafe, add, login, make_cafe, new_cart, place

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def cafes(owner_session: AsyncSession) -> tuple[Cafe, Cafe]:
    a = await make_cafe(owner_session, "a", "cafe-a.test")
    b = await make_cafe(owner_session, "b", "cafe-b.test")
    await create_staff(owner_session, a.id, "manager@a.test", "Manager", PASSWORD, Role.MANAGER)
    await owner_session.commit()
    return a, b


@pytest.fixture
async def admin(app: Any) -> Any:
    async with make_client(app, "admin.platform.test") as c:
        yield c


async def auth(admin: Any, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {await login(admin, email)}"}


async def test_role_boundaries(admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, _ = cafes
    op = await auth(admin, a.operator_email)
    mgr = await auth(admin, "manager@a.test")
    owner = await auth(admin, a.owner_email)
    body = {"name": "Супы"}
    assert (await admin.post("/v1/admin/categories", headers=op, json=body)).json()["code"] == "insufficient_role"
    assert (await admin.post("/v1/admin/categories", headers=mgr, json=body)).status_code == 201
    assert (
        await admin.get("/v1/admin/catalog", headers=op)
    ).status_code == 200  # operators see the menu for stop-lists
    assert (await admin.get("/v1/admin/settings", headers=mgr)).status_code == 403
    assert (await admin.get("/v1/admin/settings", headers=owner)).status_code == 200
    assert (await admin.get("/v1/admin/staff", headers=mgr)).status_code == 403
    assert (await admin.get("/v1/admin/analytics/summary", headers=op)).status_code == 403


async def test_menu_editing_reaches_the_storefront(app: Any, admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, _ = cafes
    h = await auth(admin, "manager@a.test")
    category = (await admin.post("/v1/admin/categories", headers=h, json={"name": "Супы"})).json()["id"]
    group = (
        await admin.post(
            "/v1/admin/modifier-groups",
            headers=h,
            json={
                "name": "Хлеб",
                "min_selected": 1,
                "max_selected": 1,
                "modifiers": [{"name": "Белый"}, {"name": "Бородинский", "price_minor": 2_000}],
            },
        )
    ).json()["id"]
    r = await admin.post(
        "/v1/admin/products",
        headers=h,
        json={
            "category_id": category,
            "name": "Борщ украинский",
            "description": "Со сметаной",
            "variants": [{"name": "300 мл", "price_minor": 29_000, "weight_value": 300, "weight_unit": "ml"}],
            "modifier_group_ids": [group],
        },
    )
    assert r.status_code == 201, r.text
    product_id = r.json()["id"]

    catalog = (await admin.get("/v1/admin/catalog", headers=h)).json()
    product = next(p for p in catalog["products"] if p["id"] == product_id)
    assert product["slug"] == "borsch-ukrainskiy"
    assert product["modifier_group_ids"] == [group]

    async with make_client(app, a.host) as shop:
        menu = (await shop.get("/v1/storefront/menu")).json()
        soups = next(c for c in menu["categories"] if c["slug"] == "supy")
        assert soups["products"][0]["modifier_groups"][0]["name"] == "Хлеб"

        # New price applies to carts immediately (carts hold no prices).
        variant_id = product["variants"][0]["id"]
        token = await new_cart(shop)
        bread = next(g for g in catalog["modifier_groups"] if g["id"] == group)["modifiers"][0]["id"]
        await add(shop, token, uuid.UUID(variant_id), 1, [(uuid.UUID(bread), 1)])
        assert (
            await admin.patch(f"/v1/admin/variants/{variant_id}", headers=h, json={"price_minor": 31_000})
        ).status_code == 204
        assert (await shop.get("/v1/cart", headers={"X-Cart-Token": token})).json()["subtotal_minor"] == 31_000

        # Hidden products disappear from the menu.
        await admin.patch(f"/v1/admin/products/{product_id}", headers=h, json={"is_active": False})
        menu = (await shop.get("/v1/storefront/menu")).json()
        assert all(c["slug"] != "supy" for c in menu["categories"])


async def test_ordered_items_can_only_be_hidden(app: Any, admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, _ = cafes
    async with make_client(app, a.host) as shop:
        token = await new_cart(shop)
        await add(shop, token, a.variants["double-burger/Стандарт"], 2)
        assert (await place(shop, token)).status_code == 201
    h = await auth(admin, "manager@a.test")
    catalog = (await admin.get("/v1/admin/catalog", headers=h)).json()
    burger = next(p for p in catalog["products"] if p["slug"] == "double-burger")
    r = await admin.delete(f"/v1/admin/products/{burger['id']}", headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "product_has_orders")
    assert (await admin.delete(f"/v1/admin/variants/{burger['variants'][0]['id']}", headers=h)).json()[
        "code"
    ] == "last_variant"
    # A never-ordered product is deleted for real; a non-empty category is protected.
    cola = next(p for p in catalog["products"] if p["slug"] == "cola")
    assert (await admin.delete(f"/v1/admin/products/{cola['id']}", headers=h)).status_code == 204
    r = await admin.delete(f"/v1/admin/categories/{burger['category_id']}", headers=h)
    assert r.json()["code"] == "category_not_empty"


async def test_stoplist_by_operator(app: Any, admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, _ = cafes
    h = await auth(admin, a.operator_email)
    variant = a.variants["lemonade/0,5 л"]
    url = f"/v1/admin/branches/{a.branch_id}/stoplist/variants/{variant}"
    r = await admin.put(url, headers=h, json={"stopped": True})
    assert r.json()["variant_ids"] == [str(variant)]
    assert (await admin.put(url, headers=h, json={"stopped": True})).json()["variant_ids"] == [
        str(variant)
    ]  # idempotent
    async with make_client(app, a.host) as shop:
        menu = (await shop.get("/v1/storefront/menu", params={"branch_id": str(a.branch_id)})).json()
        lemonade = next(p for c in menu["categories"] for p in c["products"] if p["slug"] == "lemonade")
        assert {v["name"]: v["available"] for v in lemonade["variants"]} == {"0,3 л": True, "0,5 л": False}
    assert (await admin.put(url, headers=h, json={"stopped": False})).json()["variant_ids"] == []


async def test_cross_tenant_ids_are_not_found(admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    h = await auth(admin, b.owner_email)
    assert (
        await admin.patch(f"/v1/admin/variants/{a.variants['cola/0,5 л']}", headers=h, json={"price_minor": 1})
    ).status_code == 404
    assert (
        await admin.put(
            f"/v1/admin/branches/{a.branch_id}/stoplist/variants/{b.variants['cola/0,5 л']}",
            headers=h,
            json={"stopped": True},
        )
    ).status_code == 404
    assert (
        await admin.put(
            f"/v1/admin/branches/{b.branch_id}/stoplist/variants/{a.variants['cola/0,5 л']}",
            headers=h,
            json={"stopped": True},
        )
    ).status_code == 404
    r = await admin.post(
        "/v1/admin/products",
        headers=h,
        json={"category_id": str(uuid.uuid4()), "name": "x", "variants": [{"name": "x", "price_minor": 1}]},
    )
    assert r.status_code == 404


async def test_validation_of_prices_groups_and_urls(admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    h = await auth(admin, "manager@a.test")
    assert (
        await admin.post(
            "/v1/admin/modifier-groups", headers=h, json={"name": "x", "min_selected": 3, "max_selected": 1}
        )
    ).status_code == 422
    catalog = (await admin.get("/v1/admin/catalog", headers=h)).json()
    variant = catalog["products"][0]["variants"][0]["id"]
    for bad in (-1, 1.5, "100"):
        assert (
            await admin.patch(f"/v1/admin/variants/{variant}", headers=h, json={"price_minor": bad})
        ).status_code == 422
    r = await admin.patch(
        f"/v1/admin/products/{catalog['products'][0]['id']}", headers=h, json={"image_url": "javascript:alert(1)"}
    )
    assert r.status_code == 422


async def test_hours_zones_and_branch_settings(
    app: Any, admin: Any, cafes: tuple[Cafe, Cafe], clock: FakeClock
) -> None:
    a, _ = cafes
    h = await auth(admin, "manager@a.test")
    # Closed on Tuesdays (the test clock is a Tuesday noon).
    week = [{"weekday": d, "opens_at": "10:00", "closes_at": "23:00"} for d in range(7) if d != 1]
    assert (
        await admin.put(f"/v1/admin/branches/{a.branch_id}/hours", headers=h, json={"intervals": week})
    ).status_code == 204
    async with make_client(app, a.host) as shop:
        assert (await shop.get("/v1/storefront")).json()["branches"][0]["is_open_now"] is False

    zones = (await admin.get(f"/v1/admin/branches/{a.branch_id}/delivery-zones", headers=h)).json()
    zone_id = zones[0]["id"]
    bad = {"polygon": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]}}
    assert (await admin.patch(f"/v1/admin/delivery-zones/{zone_id}", headers=h, json=bad)).json()[
        "code"
    ] == "invalid_polygon"
    assert (
        await admin.patch(
            f"/v1/admin/delivery-zones/{zone_id}", headers=h, json={"fee_minor": 9_900, "min_order_minor": 0}
        )
    ).status_code == 204

    r = await admin.patch(
        f"/v1/admin/branches/{a.branch_id}", headers=h, json={"delivery_enabled": False, "pickup_enabled": False}
    )
    assert r.json()["code"] == "no_fulfillment"
    r = await admin.patch(f"/v1/admin/branches/{a.branch_id}", headers=h, json={"payment_methods": ["bitcoin"]})
    assert r.status_code == 422
    assert (
        await admin.patch(f"/v1/admin/branches/{a.branch_id}", headers=h, json={"prep_time_min": 15})
    ).status_code == 204


async def test_settings_and_telegram_link(admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, _ = cafes
    h = await auth(admin, a.owner_email)
    r = await admin.patch(
        "/v1/admin/settings", headers=h, json={"name": "Кафе «Прибой»", "branding": {"description": "Шаурма у моря"}}
    )
    assert r.status_code == 204
    s = (await admin.get("/v1/admin/settings", headers=h)).json()
    assert (s["name"], s["branding"]["description"]) == ("Кафе «Прибой»", "Шаурма у моря")
    assert s["telegram_bot"] is None  # no bot connected for this cafe


async def test_staff_management_guards(admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, _ = cafes
    owner = await auth(admin, a.owner_email)
    staff = (await admin.get("/v1/admin/staff", headers=owner)).json()
    owner_id = next(x["user_id"] for x in staff if x["role"] == "owner")
    operator_id = next(x["user_id"] for x in staff if x["role"] == "operator")
    assert (await admin.delete(f"/v1/admin/staff/{owner_id}", headers=owner)).json()["code"] == "cannot_remove_self"
    assert (await admin.patch(f"/v1/admin/staff/{owner_id}", headers=owner, json={"role": "manager"})).json()[
        "code"
    ] == "last_owner"
    r = await admin.post(
        "/v1/admin/staff", headers=owner, json={"email": "new@a.test", "name": "Новый", "role": "operator"}
    )
    assert r.json()["code"] == "password_required"
    r = await admin.post(
        "/v1/admin/staff",
        headers=owner,
        json={"email": "New@A.test", "name": "Новый", "role": "operator", "password": "long-enough-1"},
    )
    assert r.status_code == 201
    assert (
        await admin.post("/v1/admin/auth/login", json={"email": "new@a.test", "password": "long-enough-1"})
    ).status_code == 200

    # Removing a member revokes their sessions immediately.
    operator = await auth(admin, a.operator_email)
    assert (await admin.delete(f"/v1/admin/staff/{operator_id}", headers=owner)).status_code == 204
    assert (await admin.get("/v1/admin/orders", headers=operator)).status_code == 401


async def test_analytics_in_cafe_time(app: Any, admin: Any, cafes: tuple[Cafe, Cafe], clock: FakeClock) -> None:
    a, _ = cafes
    async with make_client(app, a.host) as shop:
        for qty in (2, 3):
            token = await new_cart(shop)
            await add(shop, token, a.variants["double-burger/Стандарт"], qty)
            assert (await place(shop, token)).status_code == 201
        token = await new_cart(shop)
        await add(shop, token, a.variants["double-burger/Стандарт"], 2)
        cancelled = (await place(shop, token)).json()
        await shop.post(f"/v1/orders/{cancelled['order_token']}/cancel")
    h = await auth(admin, "manager@a.test")
    s = (await admin.get("/v1/admin/analytics/summary", headers=h, params={"days": 7})).json()
    # 2 × 550 + 150 delivery and 3 × 550 (free delivery from 1500): cancelled orders excluded.
    assert s["today_orders"] == 2
    assert s["today_revenue_minor"] == 125_000 + 165_000
    assert s["today_average_minor"] == 145_000
    assert s["today_cancelled"] == 1
    assert s["pending_now"] == 2
    assert len(s["days"]) == 7 and s["days"][-1]["orders"] == 2
    assert s["top_products"][0] == {"name": "Двойной бургер", "quantity": 5, "revenue_minor": 275_000}
    clock.advance(days=1)
    s = (await admin.get("/v1/admin/analytics/summary", headers=h)).json()
    assert s["today_orders"] == 0 and s["days"][-2]["orders"] == 2
    _ = timedelta


async def test_brand_colour_and_cover_reach_the_storefront(app: Any, admin: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    h = await auth(admin, a.owner_email)
    body = {"branding": {"accent_color": "#1f6f43", "cover_url": "https://cdn.example.ru/cover.jpg"}}
    assert (await admin.patch("/v1/admin/settings", headers=h, json=body)).status_code == 204
    s = (await admin.get("/v1/admin/settings", headers=h)).json()
    assert s["branding"]["accent_color"] == "#1F6F43"  # normalized
    assert s["branding"]["cover_url"] == "https://cdn.example.ru/cover.jpg"

    for bad in (
        {"accent_color": "red"},
        {"accent_color": "#1F6F43; background: url(x)"},
        {"accent_color": "#12345"},
        {"cover_url": "http://insecure.example/c.jpg"},
        {"cover_url": "javascript:alert(1)"},
    ):
        r = await admin.patch("/v1/admin/settings", headers=h, json={"branding": bad})
        assert r.status_code == 422, bad

    async with make_client(app, a.host) as shop:
        branding = (await shop.get("/v1/storefront")).json()["branding"]
    assert (branding["accent_color"], branding["cover_url"]) == ("#1F6F43", "https://cdn.example.ru/cover.jpg")
    async with make_client(app, b.host) as shop:
        assert "accent_color" not in (await shop.get("/v1/storefront")).json()["branding"]  # other cafe untouched

    # Clearing returns the storefront to the platform defaults.
    await admin.patch("/v1/admin/settings", headers=h, json={"branding": {"accent_color": None, "cover_url": None}})
    s = (await admin.get("/v1/admin/settings", headers=h)).json()
    assert s["branding"]["accent_color"] is None and s["branding"]["cover_url"] is None
