from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.identity.models import StaffUser
from tests.integration.conftest import FakeClock, make_client
from tests.integration.factories import PASSWORD, Cafe, add, login, make_cafe, new_cart, place

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def cafe(owner_session: AsyncSession) -> Cafe:
    return await make_cafe(owner_session, "a", "cafe-a.test")


async def make_order(app: Any, cafe: Cafe, **overrides: Any) -> dict[str, Any]:
    async with make_client(app, cafe.host) as c:
        token = await new_cart(c)
        await add(c, token, cafe.variants["double-burger/Стандарт"], 2)
        r = await place(c, token, **overrides)
        assert r.status_code == 201, r.text
        body: dict[str, Any] = r.json()
        return body


@pytest.fixture
async def admin(app: Any) -> Any:
    async with make_client(app, "admin.platform.test") as c:
        yield c


async def test_login_me_logout(admin: Any, cafe: Cafe) -> None:
    token = await login(admin, cafe.owner_email)
    auth = {"Authorization": f"Bearer {token}"}
    me = (await admin.get("/v1/admin/auth/me", headers=auth)).json()
    assert me["memberships"][0]["role"] == "owner"
    assert me["memberships"][0]["tenant_slug"] == "a"
    assert (await admin.post("/v1/admin/auth/logout", headers=auth)).status_code == 204
    assert (await admin.get("/v1/admin/auth/me", headers=auth)).status_code == 401


async def test_bad_credentials_are_indistinguishable(admin: Any, cafe: Cafe) -> None:
    wrong_pw = await admin.post("/v1/admin/auth/login", json={"email": cafe.owner_email, "password": "nope"})
    no_user = await admin.post("/v1/admin/auth/login", json={"email": "ghost@x.test", "password": "nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


async def test_session_expires(admin: Any, cafe: Cafe, clock: FakeClock) -> None:
    token = await login(admin, cafe.operator_email)
    clock.advance(days=15)
    r = await admin.get("/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})
    assert (r.status_code, r.json()["code"]) == (401, "session_expired")


async def test_disabled_staff_loses_access_immediately(admin: Any, cafe: Cafe, owner_session: AsyncSession) -> None:
    token = await login(admin, cafe.operator_email)
    user = await owner_session.scalar(select(StaffUser).where(StaffUser.email == cafe.operator_email))
    assert user is not None
    user.is_active = False
    await owner_session.commit()
    assert (await admin.get("/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_operator_runs_delivery_order_to_completion(
    app: Any, admin: Any, cafe: Cafe, owner_session: AsyncSession
) -> None:
    created = await make_order(app, cafe)
    order_id = created["order"]["id"]
    auth = {"Authorization": f"Bearer {await login(admin, cafe.operator_email)}"}

    listed = (await admin.get("/v1/admin/orders", params={"status": "pending"}, headers=auth)).json()
    assert [o["id"] for o in listed["items"]] == [order_id]
    assert listed["items"][0]["next_statuses"] == ["confirmed", "cancelled", "rejected"]

    for target in ("confirmed", "preparing", "ready", "delivering", "completed"):
        r = await admin.post(f"/v1/admin/orders/{order_id}/transitions", headers=auth, json={"to_status": target})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == target

    async with make_client(app, cafe.host) as c:
        seen = (await c.get(f"/v1/orders/{created['order_token']}")).json()
    assert seen["status"] == "completed"
    assert [h["to_status"] for h in seen["history"]] == [
        "pending",
        "confirmed",
        "preparing",
        "ready",
        "delivering",
        "completed",
    ]
    actions = (await owner_session.scalars(select(AuditLog.action).where(AuditLog.entity_id == seen["id"]))).all()
    assert actions.count("order.status_changed") == 5
    assert "order.created" in actions


async def test_invalid_transition_and_reason_rules(app: Any, admin: Any, cafe: Cafe) -> None:
    order_id = (await make_order(app, cafe, fulfillment="pickup", branch_id=str(cafe.branch_id), address=None))[
        "order"
    ]["id"]
    auth = {"Authorization": f"Bearer {await login(admin, cafe.operator_email)}"}
    url = f"/v1/admin/orders/{order_id}/transitions"
    assert (await admin.post(url, headers=auth, json={"to_status": "ready"})).json()[
        "code"
    ] == "invalid_status_transition"
    assert (await admin.post(url, headers=auth, json={"to_status": "rejected"})).json()["code"] == "reason_required"
    r = await admin.post(url, headers=auth, json={"to_status": "rejected", "reason": "Нет продуктов"})
    assert r.json()["status"] == "rejected"
    assert (await admin.post(url, headers=auth, json={"to_status": "confirmed"})).status_code == 409


async def test_customer_cancel_races_staff_confirm(app: Any, admin: Any, cafe: Cafe) -> None:
    import asyncio

    created = await make_order(app, cafe)
    auth = {"Authorization": f"Bearer {await login(admin, cafe.operator_email)}"}
    async with make_client(app, cafe.host) as shop:
        confirm, cancel = await asyncio.gather(
            admin.post(
                f"/v1/admin/orders/{created['order']['id']}/transitions", headers=auth, json={"to_status": "confirmed"}
            ),
            shop.post(f"/v1/orders/{created['order_token']}/cancel"),
        )
    assert sorted([confirm.status_code, cancel.status_code]) == [200, 409]


async def test_cookie_auth_requires_csrf_header(admin: Any, app: Any, cafe: Cafe) -> None:
    order_id = (await make_order(app, cafe))["order"]["id"]
    r = await admin.post("/v1/admin/auth/login", json={"email": cafe.operator_email, "password": PASSWORD})
    assert "staff_session" in r.cookies
    admin.cookies.set("staff_session", r.cookies["staff_session"])
    assert (await admin.get("/v1/admin/orders")).status_code == 200  # GET with cookie is fine
    url = f"/v1/admin/orders/{order_id}/transitions"
    r = await admin.post(url, json={"to_status": "confirmed"})
    assert (r.status_code, r.json()["code"]) == (403, "csrf_check_failed")
    r = await admin.post(url, json={"to_status": "confirmed"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200


async def test_admin_requires_authentication(admin: Any, cafe: Cafe) -> None:
    assert (await admin.get("/v1/admin/orders")).status_code == 401
    assert (await admin.get("/v1/admin/orders", headers={"Authorization": "Bearer forged"})).status_code == 401
