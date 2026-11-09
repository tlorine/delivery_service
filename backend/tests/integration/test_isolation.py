"""Cafe B must never see or touch cafe A's data, at the API and at the database level (ADR-0002).

Both cafes have identical slugs for categories/products and identical menus."""

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import bind_tenant, create_engine, create_sessionmaker
from app.modules.catalog.models import Category
from app.modules.ordering.models import Order
from tests.integration.conftest import APP_URL, make_client
from tests.integration.factories import Cafe, add, login, make_cafe, new_cart, place

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def cafes(owner_session: AsyncSession) -> tuple[Cafe, Cafe]:
    return await make_cafe(owner_session, "a", "cafe-a.test"), await make_cafe(owner_session, "b", "cafe-b.test")


@pytest.fixture
async def app_engine() -> Any:
    engine = create_engine(APP_URL, 2)
    yield engine
    await engine.dispose()


async def order_in_a(app: Any, a: Cafe) -> dict[str, Any]:
    async with make_client(app, a.host) as c:
        token = await new_cart(c)
        await add(c, token, a.variants["double-burger/Стандарт"], 2)
        r = await place(c, token)
        assert r.status_code == 201
        result: dict[str, Any] = r.json()
        result["cart_token"] = token
        return result


async def test_order_token_of_a_is_unknown_on_b(app: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    created = await order_in_a(app, a)
    async with make_client(app, b.host) as c:
        assert (await c.get(f"/v1/orders/{created['order_token']}")).status_code == 404
        assert (await c.post(f"/v1/orders/{created['order_token']}/cancel")).status_code == 404


async def test_cart_token_of_a_is_unknown_on_b(app: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    async with make_client(app, a.host) as c:
        token = await new_cart(c)
    async with make_client(app, b.host) as c:
        assert (await c.get("/v1/cart", headers={"X-Cart-Token": token})).status_code == 404
        r = await add(c, token, b.variants["cola/0,5 л"])
        assert r.json()["code"] == "cart_not_found"


async def test_cannot_add_variant_of_another_cafe(app: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    async with make_client(app, b.host) as c:
        token = await new_cart(c)
        r = await add(c, token, a.variants["cola/0,5 л"])
        assert r.status_code == 404
        assert r.json()["code"] == "product_not_found"
        ok = await add(c, token, b.variants["cola/0,5 л"])
        r = await add(c, token, b.variants["cheeseburger/Стандарт"], 1, [(a.modifiers["Сыр"], 1)])
        assert ok.status_code == 200
        assert r.json()["code"] == "invalid_modifiers"


async def test_pickup_at_branch_of_another_cafe_is_refused(app: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    async with make_client(app, b.host) as c:
        token = await new_cart(c)
        await add(c, token, b.variants["cola/0,5 л"])
        r = await place(c, token, fulfillment="pickup", branch_id=str(a.branch_id), address=None)
        assert r.json()["code"] == "branch_not_found"


async def test_staff_of_b_cannot_reach_orders_of_a(app: Any, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    created = await order_in_a(app, a)
    order_id = created["order"]["id"]
    async with make_client(app, "admin.platform.test") as c:
        token = await login(c, b.owner_email)
        auth = {"Authorization": f"Bearer {token}"}
        assert (await c.get("/v1/admin/orders", headers=auth)).json()["items"] == []
        assert (await c.get(f"/v1/admin/orders/{order_id}", headers=auth)).status_code == 404
        r = await c.post(f"/v1/admin/orders/{order_id}/transitions", headers=auth, json={"to_status": "confirmed"})
        assert r.status_code == 404
        # Choosing A's tenant explicitly is refused: no membership.
        r = await c.get("/v1/admin/orders", headers={**auth, "X-Tenant-Id": str(a.id)})
        assert (r.status_code, r.json()["code"]) == (403, "tenant_access_denied")


async def test_rls_without_tenant_sees_nothing(app_engine: AsyncEngine, cafes: tuple[Cafe, Cafe], app: Any) -> None:
    await order_in_a(app, cafes[0])
    async with create_sessionmaker(app_engine)() as s:
        assert await s.scalar(select(func.count()).select_from(Category)) == 0
        assert await s.scalar(select(func.count()).select_from(Order)) == 0


async def test_rls_hides_other_tenant_even_without_where(
    app_engine: AsyncEngine, cafes: tuple[Cafe, Cafe], app: Any
) -> None:
    a, b = cafes
    await order_in_a(app, a)
    async with create_sessionmaker(app_engine)() as s:
        await bind_tenant(s, b.id)
        # Deliberately no tenant filter: a forgotten WHERE must not leak.
        tenants = set((await s.scalars(select(Category.tenant_id))).all())
        assert tenants == {b.id}
        assert await s.scalar(select(func.count()).select_from(Order)) == 0
        await s.commit()
        # Still scoped after a commit (new transaction re-applies the tenant).
        assert set((await s.scalars(select(Category.tenant_id))).all()) == {b.id}


async def test_rls_blocks_writing_rows_for_another_tenant(app_engine: AsyncEngine, cafes: tuple[Cafe, Cafe]) -> None:
    a, b = cafes
    async with create_sessionmaker(app_engine)() as s:
        await bind_tenant(s, b.id)
        s.add(Category(id=uuid.uuid4(), tenant_id=a.id, slug="evil", name="evil"))
        with pytest.raises(DBAPIError, match="row-level security"):
            await s.flush()


async def test_composite_fk_blocks_cross_tenant_reference(
    owner_session: AsyncSession, cafes: tuple[Cafe, Cafe]
) -> None:
    """Even the owner role (no RLS) cannot attach B's stop-list entry to A's branch."""
    a, b = cafes
    with pytest.raises(DBAPIError, match="foreign key"):
        await owner_session.execute(
            text(
                "INSERT INTO stoplist_entries (id, tenant_id, branch_id, variant_id, created_at, updated_at) "
                "VALUES (:id, :t, :branch, :v, now(), now())"
            ),
            {"id": uuid.uuid4(), "t": b.id, "branch": a.branch_id, "v": b.variants["cola/0,5 л"]},
        )


async def test_app_role_cannot_alter_audit_log(app_engine: AsyncEngine, cafes: tuple[Cafe, Cafe]) -> None:
    async with create_sessionmaker(app_engine)() as s:
        await bind_tenant(s, cafes[0].id)
        with pytest.raises(DBAPIError, match="permission denied"):
            await s.execute(text("DELETE FROM audit_log"))


async def test_session_cannot_be_rebound_to_another_tenant(app_engine: AsyncEngine, cafes: tuple[Cafe, Cafe]) -> None:
    async with create_sessionmaker(app_engine)() as s:
        await bind_tenant(s, cafes[0].id)
        with pytest.raises(RuntimeError, match="another tenant"):
            await bind_tenant(s, cafes[1].id)
