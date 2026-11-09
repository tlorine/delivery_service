"""Platform operations that run as the owner role (bypassing RLS by design): tenant onboarding and demo data."""

import uuid
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecretBox, hash_password
from app.modules.catalog.models import Category, Modifier, ModifierGroup, Product, ProductModifierGroup, ProductVariant
from app.modules.delivery.geo import validate_polygon
from app.modules.delivery.models import DeliveryZone
from app.modules.identity.models import Membership, Role, StaffUser
from app.modules.telegram.models import TelegramBot
from app.modules.tenancy.models import Branch, BranchHours, Tenant, TenantDomain


async def create_tenant(
    session: AsyncSession, slug: str, name: str, hosts: list[str], timezone: str = "Europe/Moscow"
) -> Tenant:
    tenant = Tenant(slug=slug.lower(), name=name, timezone=timezone)
    session.add(tenant)
    await session.flush()
    for i, host in enumerate(hosts):
        session.add(TenantDomain(tenant_id=tenant.id, host=host.lower(), is_primary=i == 0))
    await session.flush()
    return tenant


async def create_staff(
    session: AsyncSession, tenant_id: uuid.UUID, email: str, name: str, password: str, role: Role
) -> StaffUser:
    email = email.strip().lower()
    user = await session.scalar(select(StaffUser).where(StaffUser.email == email))
    if user is None:
        user = StaffUser(email=email, name=name, password_hash=hash_password(password))
        session.add(user)
        await session.flush()
    session.add(Membership(tenant_id=tenant_id, user_id=user.id, role=role))
    await session.flush()
    return user


async def set_telegram_bot(
    session: AsyncSession,
    box: SecretBox,
    tenant_id: uuid.UUID,
    token: str,
    username: str,
    chat_id: int | None,
    webhook_secret: str,
) -> TelegramBot:
    bot_id = int(token.split(":", 1)[0])
    bot = await session.scalar(select(TelegramBot).where(TelegramBot.tenant_id == tenant_id))
    if bot is None:
        bot = TelegramBot(
            tenant_id=tenant_id, bot_id=bot_id, username=username, token_encrypted=b"", webhook_secret=webhook_secret
        )
        session.add(bot)
    bot.bot_id, bot.username, bot.notify_chat_id = bot_id, username, chat_id
    bot.token_encrypted = box.encrypt(token)
    await session.flush()
    return bot


# Central Sochi, roughly from Mamaika to Matsesta. GeoJSON order: [lon, lat].
SOCHI_CENTER_ZONE = {
    "type": "Polygon",
    "coordinates": [[[39.68, 43.54], [39.78, 43.54], [39.78, 43.63], [39.68, 43.63], [39.68, 43.54]]],
}


async def seed_demo(
    session: AsyncSession,
    slug: str = "demo",
    hosts: tuple[str, ...] = ("localhost",),
    *,
    always_open: bool = False,
    name: str = "Демо-кафе «У моря»",
) -> Tenant:
    """Demo cafe. `always_open` (00:00-24:00 every day) makes E2E runs independent of the time of day."""
    tenant = await create_tenant(session, slug, name, list(hosts))
    t = tenant.id
    branch = Branch(
        tenant_id=t,
        name="Курортный проспект",
        address="Сочи, Курортный проспект, 18",
        lat=43.5855,
        lon=39.7231,
        phone="+78620000000",
        timezone="Europe/Moscow",
        prep_time_min=20,
        delivery_time_min=40,
        payment_methods=["cash", "card_on_delivery"],
    )
    session.add(branch)
    await session.flush()
    for weekday in range(7):
        session.add(
            BranchHours(tenant_id=t, branch_id=branch.id, weekday=weekday, opens_at=time(10), closes_at=time(23))
        )
    validate_polygon(SOCHI_CENTER_ZONE)
    session.add(
        DeliveryZone(
            tenant_id=t,
            branch_id=branch.id,
            name="Центр",
            polygon=SOCHI_CENTER_ZONE,
            fee_minor=15_000,
            min_order_minor=70_000,
            free_from_minor=150_000,
        )
    )

    sauces = ModifierGroup(tenant_id=t, name="Соус", min_selected=0, max_selected=2, sort=1)
    extras = ModifierGroup(tenant_id=t, name="Добавки", min_selected=0, max_selected=5, sort=2)
    session.add_all([sauces, extras])
    await session.flush()
    session.add_all(
        [
            Modifier(tenant_id=t, group_id=sauces.id, name="Чесночный", price_minor=0, sort=1),
            Modifier(tenant_id=t, group_id=sauces.id, name="Острый", price_minor=0, sort=2),
            Modifier(tenant_id=t, group_id=sauces.id, name="Сырный", price_minor=4_000, sort=3),
            Modifier(tenant_id=t, group_id=extras.id, name="Сыр", price_minor=5_000, max_quantity=2, sort=1),
            Modifier(tenant_id=t, group_id=extras.id, name="Бекон", price_minor=8_000, max_quantity=2, sort=2),
            Modifier(tenant_id=t, group_id=extras.id, name="Халапеньо", price_minor=3_000, sort=3),
        ]
    )

    menu: list[tuple[str, str, list[tuple[str, str, str, list[tuple[str, int, int, str]], bool]]]] = [
        (
            "shawarma",
            "Шаурма",
            [
                (
                    "classic-shawarma",
                    "Шаурма классическая",
                    "Курица, свежие овощи, соус в лаваше",
                    [("Стандарт", 32_000, 350, "g"), ("Большая", 42_000, 500, "g")],
                    True,
                ),
                (
                    "cheese-shawarma",
                    "Шаурма с сыром",
                    "Курица, сыр, томаты, соус",
                    [("Стандарт", 36_000, 380, "g")],
                    True,
                ),
            ],
        ),
        (
            "burgers",
            "Бургеры",
            [
                (
                    "cheeseburger",
                    "Чизбургер",
                    "Говяжья котлета, чеддер, маринованный огурец",
                    [("Стандарт", 39_000, 280, "g")],
                    True,
                ),
                (
                    "double-burger",
                    "Двойной бургер",
                    "Две котлеты, двойной сыр, бекон",
                    [("Стандарт", 55_000, 420, "g")],
                    True,
                ),
            ],
        ),
        (
            "drinks",
            "Напитки",
            [
                (
                    "lemonade",
                    "Лимонад домашний",
                    "Лимон, мята, тростниковый сахар",
                    [("0,3 л", 15_000, 300, "ml"), ("0,5 л", 22_000, 500, "ml")],
                    False,
                ),
                ("cola", "Кола", "", [("0,5 л", 12_000, 500, "ml")], False),
            ],
        ),
    ]
    for c_sort, (c_slug, c_name, products) in enumerate(menu):
        category = Category(tenant_id=t, slug=c_slug, name=c_name, sort=c_sort)
        session.add(category)
        await session.flush()
        for p_sort, (p_slug, p_name, desc, variants, with_modifiers) in enumerate(products):
            product = Product(
                tenant_id=t, category_id=category.id, slug=p_slug, name=p_name, description=desc or None, sort=p_sort
            )
            session.add(product)
            await session.flush()
            for v_sort, (v_name, price, weight, unit) in enumerate(variants):
                session.add(
                    ProductVariant(
                        tenant_id=t,
                        product_id=product.id,
                        name=v_name,
                        price_minor=price,
                        weight_value=weight,
                        weight_unit=unit,
                        sort=v_sort,
                    )
                )
            if with_modifiers:
                session.add(ProductModifierGroup(tenant_id=t, product_id=product.id, group_id=sauces.id, sort=1))
                session.add(ProductModifierGroup(tenant_id=t, product_id=product.id, group_id=extras.id, sort=2))
    await session.flush()
    return tenant
