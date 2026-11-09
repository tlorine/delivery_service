import asyncio
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import ProductVariant, StoplistEntry
from app.modules.ordering.models import Order, OrderItem, OrderItemModifier
from tests.integration.conftest import FakeClock, make_client
from tests.integration.factories import OUTSIDE, Cafe, add, make_cafe, new_cart, place

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def cafe(owner_session: AsyncSession) -> Cafe:
    return await make_cafe(owner_session, "a", "cafe-a.test")


@pytest.fixture
async def client(app: Any) -> Any:
    async with make_client(app, "cafe-a.test") as c:
        yield c


async def filled_cart(client: Any, cafe: Cafe) -> str:
    token = await new_cart(client)
    r = await add(
        client,
        token,
        cafe.variants["classic-shawarma/Большая"],
        2,
        [(cafe.modifiers["Чесночный"], 1), (cafe.modifiers["Сыр"], 2)],
    )
    assert r.status_code == 200, r.text
    r = await add(client, token, cafe.variants["lemonade/0,5 л"], 1)
    assert r.status_code == 200, r.text
    return token


# (420.00 + 2 × 50.00) × 2 + 220.00 = 1260.00 ₽; delivery 150.00 ₽ (free from 1500.00)
EXPECTED_SUBTOTAL = (42_000 + 2 * 5_000) * 2 + 22_000


async def test_full_order_flow(client: Any, cafe: Cafe, owner_session: AsyncSession) -> None:
    token = await filled_cart(client, cafe)
    cart = (await client.get("/v1/cart", headers={"X-Cart-Token": token})).json()
    assert cart["subtotal_minor"] == EXPECTED_SUBTOTAL
    assert cart["item_count"] == 3

    quote = (
        await client.post(
            "/v1/checkout/quote",
            headers={"X-Cart-Token": token},
            json={
                "fulfillment": "delivery",
                "payment_method": "cash",
                "address": {"street": "Курортный проспект, 18", "lat": 43.5855, "lon": 39.7231},
            },
        )
    ).json()
    assert quote["ok"] is True, quote
    assert quote["delivery_fee_minor"] == 15_000
    assert quote["total_minor"] == EXPECTED_SUBTOTAL + 15_000

    r = await place(client, token, expected_total_minor=quote["total_minor"], comment="Без лука")
    assert r.status_code == 201, r.text
    created = r.json()
    order = created["order"]
    assert order["status"] == "pending"
    assert order["number"] == 1
    assert order["customer_phone"] == "+79181234567"
    assert order["total_minor"] == EXPECTED_SUBTOTAL + 15_000
    assert order["branch_id"] == str(cafe.branch_id)
    big = next(i for i in order["items"] if i["variant_name"] == "Большая")
    assert big["unit_price_minor"] == 52_000
    assert {m["name"] for m in big["modifiers"]} == {"Чесночный", "Сыр"}

    status = await client.get(f"/v1/orders/{created['order_token']}")
    assert status.status_code == 200
    assert status.json()["id"] == order["id"]
    assert status.json()["history"][0]["to_status"] == "pending"

    # The cart is spent; a new order needs a new cart.
    assert (await client.get("/v1/cart", headers={"X-Cart-Token": token})).status_code == 200
    assert (await add(client, token, cafe.variants["cola/0,5 л"])).json()["code"] == "cart_not_found"


async def test_snapshot_survives_menu_price_change(client: Any, cafe: Cafe, owner_session: AsyncSession) -> None:
    token = await filled_cart(client, cafe)
    order = (await place(client, token)).json()["order"]
    variant = await owner_session.get(ProductVariant, cafe.variants["classic-shawarma/Большая"])
    assert variant is not None
    variant.price_minor = 99_900
    variant.name = "XXL"
    await owner_session.commit()
    items = (await owner_session.scalars(select(OrderItem).where(OrderItem.order_id == uuid.UUID(order["id"])))).all()
    big = next(i for i in items if i.variant_id == cafe.variants["classic-shawarma/Большая"])
    assert (big.variant_name, big.unit_price_minor) == ("Большая", 52_000)


async def test_client_cannot_send_prices_or_status(client: Any, cafe: Cafe) -> None:
    token = await filled_cart(client, cafe)
    for field, value in [
        ("total_minor", 1),
        ("status", "completed"),
        ("subtotal_minor", 0),
        ("tenant_id", str(uuid.uuid4())),
    ]:
        r = await place(client, token, **{field: value})
        assert r.status_code == 422, field
        assert r.json()["code"] == "validation_error"
    r = await client.post(
        "/v1/cart/items",
        headers={"X-Cart-Token": token},
        json={"variant_id": str(cafe.variants["cola/0,5 л"]), "price_minor": 1},
    )
    assert r.status_code == 422


async def test_price_changed_since_quote(client: Any, cafe: Cafe, owner_session: AsyncSession) -> None:
    token = await filled_cart(client, cafe)
    shown = EXPECTED_SUBTOTAL + 15_000
    variant = await owner_session.get(ProductVariant, cafe.variants["lemonade/0,5 л"])
    assert variant is not None
    variant.price_minor = 25_000
    await owner_session.commit()
    r = await place(client, token, expected_total_minor=shown)
    assert r.status_code == 409
    assert r.json()["code"] == "price_changed"
    assert r.json()["extra"]["quote"]["total_minor"] == shown + 3_000
    assert (await place(client, token, expected_total_minor=shown + 3_000)).status_code == 201


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"address": {"street": "Адлер, ул. Ленина, 1", **OUTSIDE}}, "outside_delivery_zone"),
        ({"address": None}, "address_required"),
        ({"fulfillment": "pickup"}, "branch_required"),
        ({"payment_method": "online"}, "payment_method_unavailable"),
        ({"payment_method": "card_on_delivery", "change_from_minor": 500_000}, "invalid_change"),
        ({"change_from_minor": 100}, "invalid_change"),
        ({"customer": {"name": "Анна", "phone": "12345"}}, "invalid_phone"),
    ],
)
async def test_business_rule_violations(client: Any, cafe: Cafe, overrides: dict[str, Any], code: str) -> None:
    token = await filled_cart(client, cafe)
    r = await place(client, token, **overrides)
    assert r.status_code == 422, r.text
    assert r.json()["code"] == code


async def test_personal_data_consent_is_required(client: Any, cafe: Cafe) -> None:
    token = await filled_cart(client, cafe)
    assert (await place(client, token, personal_data_consent=False)).status_code == 422


async def test_below_minimum_for_delivery_but_fine_for_pickup(client: Any, cafe: Cafe) -> None:
    token = await new_cart(client)
    await add(client, token, cafe.variants["cola/0,5 л"])  # 120 ₽ < 700 ₽ minimum
    assert (await place(client, token)).json()["code"] == "below_min_order"
    r = await place(client, token, fulfillment="pickup", branch_id=str(cafe.branch_id), address=None)
    assert r.status_code == 201, r.text
    assert r.json()["order"]["delivery_fee_minor"] == 0


async def test_free_delivery_threshold(client: Any, cafe: Cafe) -> None:
    token = await new_cart(client)
    await add(client, token, cafe.variants["double-burger/Стандарт"], 3)  # 1650 ₽ >= 1500 ₽
    order = (await place(client, token)).json()["order"]
    assert order["delivery_fee_minor"] == 0
    assert order["total_minor"] == 165_000


async def test_closed_branch_requires_scheduled_time(client: Any, cafe: Cafe, clock: FakeClock) -> None:
    token = await filled_cart(client, cafe)
    clock.advance(hours=12)  # 00:00 local: closed
    assert (await place(client, token)).json()["code"] == "branch_closed"
    tomorrow_noon = clock.now() + timedelta(hours=12)
    r = await place(client, token, requested_at=tomorrow_noon.isoformat())
    assert r.status_code == 201, r.text
    slots = (
        await client.get(
            "/v1/storefront/time-slots", params={"branch_id": str(cafe.branch_id), "fulfillment": "delivery"}
        )
    ).json()
    assert slots, "slots for tomorrow are offered"


async def test_requested_time_validation(client: Any, cafe: Cafe, clock: FakeClock) -> None:
    token = await filled_cart(client, cafe)
    too_soon = clock.now() + timedelta(minutes=10)
    assert (await place(client, token, requested_at=too_soon.isoformat())).json()["code"] == "invalid_requested_time"
    at_night = clock.now() + timedelta(hours=15)  # 03:00 local
    assert (await place(client, token, requested_at=at_night.isoformat())).json()["code"] == "invalid_requested_time"


async def test_stoplist_blocks_checkout(client: Any, cafe: Cafe, owner_session: AsyncSession) -> None:
    token = await filled_cart(client, cafe)
    owner_session.add(
        StoplistEntry(tenant_id=cafe.id, branch_id=cafe.branch_id, variant_id=cafe.variants["lemonade/0,5 л"])
    )
    await owner_session.commit()
    r = await place(client, token)
    assert r.json()["code"] == "item_unavailable"
    cart = (
        await client.get("/v1/cart", params={"branch_id": str(cafe.branch_id)}, headers={"X-Cart-Token": token})
    ).json()
    assert cart["has_problems"] is True
    await owner_session.execute(delete(StoplistEntry))
    await owner_session.commit()
    assert (await place(client, token)).status_code == 201


async def test_cart_merges_same_configuration(client: Any, cafe: Cafe) -> None:
    token = await new_cart(client)
    v, garlic = cafe.variants["cheeseburger/Стандарт"], cafe.modifiers["Чесночный"]
    await add(client, token, v, 1, [(garlic, 1)])
    await add(client, token, v, 2, [(garlic, 1)])
    cart = (await add(client, token, v, 1)).json()
    assert sorted(i["quantity"] for i in cart["items"]) == [1, 3]
    item = next(i for i in cart["items"] if i["quantity"] == 3)
    cart = (
        await client.patch(f"/v1/cart/items/{item['id']}", headers={"X-Cart-Token": token}, json={"quantity": 0})
    ).json()
    assert [i["quantity"] for i in cart["items"]] == [1]


async def test_invalid_modifiers_rejected_when_adding(client: Any, cafe: Cafe) -> None:
    token = await new_cart(client)
    r = await add(client, token, cafe.variants["lemonade/0,5 л"], 1, [(cafe.modifiers["Сыр"], 1)])
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_modifiers"
    r = await add(
        client,
        token,
        cafe.variants["cheeseburger/Стандарт"],
        1,
        [(cafe.modifiers["Чесночный"], 1), (cafe.modifiers["Острый"], 1), (cafe.modifiers["Сырный"], 1)],
    )
    assert r.json()["code"] == "invalid_modifiers"  # max 2 sauces


async def test_idempotent_retry_returns_same_order(client: Any, cafe: Cafe, owner_session: AsyncSession) -> None:
    token = await filled_cart(client, cafe)
    key = uuid.uuid4().hex
    first = await place(client, token, key)
    again = await place(client, token, key)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["order"]["id"] == again.json()["order"]["id"]
    assert first.json()["order_token"] == again.json()["order_token"]
    assert await owner_session.scalar(select(func.count()).select_from(Order)) == 1

    other = await place(client, token, key, comment="другое тело")
    assert other.status_code == 422
    assert other.json()["code"] == "idempotency_key_reused"
    fresh_key = await place(client, token)
    assert fresh_key.json()["code"] == "cart_already_checked_out"


async def test_concurrent_checkouts_of_one_cart_create_one_order(
    client: Any, cafe: Cafe, owner_session: AsyncSession
) -> None:
    token = await filled_cart(client, cafe)
    responses = await asyncio.gather(*(place(client, token) for _ in range(8)))
    codes = sorted(r.status_code for r in responses)
    assert codes.count(201) == 1, [r.text for r in responses]
    assert all(r.json()["code"] == "cart_already_checked_out" for r in responses if r.status_code != 201)
    assert await owner_session.scalar(select(func.count()).select_from(Order)) == 1


async def test_concurrent_retries_with_same_key(client: Any, cafe: Cafe, owner_session: AsyncSession) -> None:
    token = await filled_cart(client, cafe)
    key = uuid.uuid4().hex
    responses = await asyncio.gather(*(place(client, token, key) for _ in range(6)))
    assert {r.status_code for r in responses} <= {200, 201}
    assert len({r.json()["order"]["id"] for r in responses}) == 1
    assert await owner_session.scalar(select(func.count()).select_from(Order)) == 1


async def test_order_numbers_are_sequential_under_concurrency(
    app: Any, cafe: Cafe, owner_session: AsyncSession
) -> None:
    async with make_client(app, "cafe-a.test") as c:
        tokens = [await filled_cart(c, cafe) for _ in range(6)]
        responses = await asyncio.gather(*(place(c, t) for t in tokens))
    assert sorted(r.json()["order"]["number"] for r in responses) == [1, 2, 3, 4, 5, 6]
    mods = await owner_session.scalar(select(func.count()).select_from(OrderItemModifier))
    assert mods == 6 * 2


async def test_customer_cancels_pending_order(client: Any, cafe: Cafe) -> None:
    token = await filled_cart(client, cafe)
    created = (await place(client, token)).json()
    r = await client.post(f"/v1/orders/{created['order_token']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    again = await client.post(f"/v1/orders/{created['order_token']}/cancel")
    assert again.status_code == 409


async def test_unknown_order_token(client: Any, cafe: Cafe) -> None:
    assert (await client.get(f"/v1/orders/{uuid.uuid4().hex}.deadbeef")).status_code == 404
