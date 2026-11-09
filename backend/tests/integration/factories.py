"""Two independent cafes with deliberately identical slugs and menus: isolation bugs cannot hide behind
different data."""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecretBox
from app.modules.catalog.models import Modifier, ModifierGroup, Product, ProductVariant
from app.modules.identity.models import Role
from app.modules.tenancy.models import Branch
from app.seed import create_staff, seed_demo, set_telegram_bot

PASSWORD = "correct-horse-battery"
# A point inside the demo delivery zone (central Sochi) and one outside (Adler).
INSIDE = {"lat": 43.5855, "lon": 39.7231}
OUTSIDE = {"lat": 43.4305, "lon": 39.9200}


@dataclass
class Cafe:
    id: uuid.UUID
    host: str
    branch_id: uuid.UUID
    variants: dict[str, uuid.UUID]  # "<product slug>/<variant name>" -> id
    modifiers: dict[str, uuid.UUID]  # name -> id
    owner_email: str
    operator_email: str


async def make_cafe(
    session: AsyncSession, slug: str, host: str, box: SecretBox | None = None, chat_id: int | None = None
) -> Cafe:
    tenant = await seed_demo(session, slug, (host,))
    owner = f"owner@{slug}.test"
    operator = f"operator@{slug}.test"
    await create_staff(session, tenant.id, owner, "Owner", PASSWORD, Role.OWNER)
    await create_staff(session, tenant.id, operator, "Operator", PASSWORD, Role.OPERATOR)
    if box is not None:
        await set_telegram_bot(
            session, box, tenant.id, f"{abs(hash(slug)) % 10**9}:TEST-TOKEN-{slug}", f"{slug}_bot", chat_id, "secret"
        )
    branch = await session.scalar(select(Branch).where(Branch.tenant_id == tenant.id))
    assert branch is not None
    rows = (
        await session.execute(
            select(Product.slug, ProductVariant.name, ProductVariant.id)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(ProductVariant.tenant_id == tenant.id)
        )
    ).all()
    mods = (
        await session.execute(
            select(Modifier.name, Modifier.id)
            .join(ModifierGroup, ModifierGroup.id == Modifier.group_id)
            .where(Modifier.tenant_id == tenant.id)
        )
    ).all()
    await session.commit()
    return Cafe(tenant.id, host, branch.id, {f"{s}/{n}": i for s, n, i in rows}, dict(mods), owner, operator)


async def new_cart(client: httpx.AsyncClient) -> str:
    r = await client.post("/v1/carts")
    assert r.status_code == 201, r.text
    token: str = r.json()["cart_token"]
    return token


async def add(
    client: httpx.AsyncClient,
    token: str,
    variant: uuid.UUID,
    qty: int = 1,
    modifiers: list[tuple[uuid.UUID, int]] | None = None,
) -> httpx.Response:
    return await client.post(
        "/v1/cart/items",
        headers={"X-Cart-Token": token},
        json={
            "variant_id": str(variant),
            "quantity": qty,
            "modifiers": [{"modifier_id": str(m), "quantity": q} for m, q in modifiers or []],
        },
    )


def order_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "fulfillment": "delivery",
        "address": {"street": "Курортный проспект, 18", "flat": "12", **INSIDE},
        "payment_method": "cash",
        "customer": {"name": "Анна", "phone": "8 (918) 123-45-67"},
        "personal_data_consent": True,
    }
    body.update(overrides)
    return body


async def place(client: httpx.AsyncClient, token: str, key: str | None = None, **overrides: Any) -> httpx.Response:
    return await client.post(
        "/v1/orders",
        json=order_body(**overrides),
        headers={"X-Cart-Token": token, "Idempotency-Key": key or uuid.uuid4().hex},
    )


async def login(client: httpx.AsyncClient, email: str) -> str:
    r = await client.post("/v1/admin/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    token: str = r.json()["token"]
    return token
