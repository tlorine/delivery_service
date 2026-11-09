import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import (
    Category,
    Modifier,
    ModifierGroup,
    Product,
    ProductModifierGroup,
    ProductVariant,
    StoplistEntry,
)
from app.modules.pricing.calculator import GroupRule, ModifierRule
from app.modules.tenancy.context import TenantContext


@dataclass(frozen=True, slots=True)
class VariantRule:
    """Everything pricing needs to validate and price one cart line."""

    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    variant_name: str
    price_minor: int
    available: bool
    groups: tuple[GroupRule, ...]


@dataclass(slots=True)
class MenuVariant:
    id: uuid.UUID
    name: str
    price_minor: int
    weight_value: int | None
    weight_unit: str | None
    available: bool


@dataclass(slots=True)
class MenuProduct:
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    image_url: str | None
    variants: list[MenuVariant]
    modifier_groups: list[GroupRule]
    available: bool


@dataclass(slots=True)
class MenuCategory:
    id: uuid.UUID
    slug: str
    name: str
    products: list[MenuProduct] = field(default_factory=list)


class CatalogService:
    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.tenant = tenant

    async def _stoplist(self, branch_id: uuid.UUID | None) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        if branch_id is None:
            return set(), set()
        rows = await self.session.scalars(
            select(StoplistEntry).where(StoplistEntry.tenant_id == self.tenant.id, StoplistEntry.branch_id == branch_id)
        )
        variants, modifiers = set(), set()
        for r in rows:
            if r.variant_id:
                variants.add(r.variant_id)
            if r.modifier_id:
                modifiers.add(r.modifier_id)
        return variants, modifiers

    async def _groups_for(
        self, product_ids: Iterable[uuid.UUID], stopped_modifiers: set[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[GroupRule, ...]]:
        t = self.tenant.id
        links = (
            await self.session.execute(
                select(ProductModifierGroup.product_id, ModifierGroup)
                .join(
                    ModifierGroup,
                    (ModifierGroup.id == ProductModifierGroup.group_id) & (ModifierGroup.tenant_id == t),
                )
                .where(
                    ProductModifierGroup.tenant_id == t,
                    ProductModifierGroup.product_id.in_(list(product_ids)),
                )
                .order_by(ProductModifierGroup.sort, ModifierGroup.sort)
            )
        ).all()
        group_ids = {g.id for _, g in links}
        mods: dict[uuid.UUID, list[ModifierRule]] = defaultdict(list)
        if group_ids:
            for m in await self.session.scalars(
                select(Modifier)
                .where(Modifier.tenant_id == t, Modifier.group_id.in_(group_ids), Modifier.is_active.is_(True))
                .order_by(Modifier.sort, Modifier.name)
            ):
                mods[m.group_id].append(
                    ModifierRule(m.id, m.group_id, m.name, m.price_minor, m.max_quantity, m.id not in stopped_modifiers)
                )
        result: dict[uuid.UUID, list[GroupRule]] = defaultdict(list)
        for product_id, g in links:
            result[product_id].append(GroupRule(g.id, g.name, g.min_selected, g.max_selected, tuple(mods[g.id])))
        return {k: tuple(v) for k, v in result.items()}

    async def variant_rules(
        self, variant_ids: Iterable[uuid.UUID], branch_id: uuid.UUID | None
    ) -> dict[uuid.UUID, VariantRule]:
        ids = list(set(variant_ids))
        if not ids:
            return {}
        t = self.tenant.id
        rows = (
            await self.session.execute(
                select(ProductVariant, Product, Category)
                .join(Product, (Product.id == ProductVariant.product_id) & (Product.tenant_id == t))
                .join(Category, (Category.id == Product.category_id) & (Category.tenant_id == t))
                .where(ProductVariant.tenant_id == t, ProductVariant.id.in_(ids))
            )
        ).all()
        stopped_variants, stopped_modifiers = await self._stoplist(branch_id)
        groups = await self._groups_for({p.id for _, p, _ in rows}, stopped_modifiers)
        return {
            v.id: VariantRule(
                variant_id=v.id,
                product_id=p.id,
                product_name=p.name,
                variant_name=v.name,
                price_minor=v.price_minor,
                available=v.is_active and p.is_active and c.is_active and v.id not in stopped_variants,
                groups=groups.get(p.id, ()),
            )
            for v, p, c in rows
        }

    async def menu(self, branch_id: uuid.UUID | None) -> list[MenuCategory]:
        t = self.tenant.id
        categories = (
            await self.session.scalars(
                select(Category)
                .where(Category.tenant_id == t, Category.is_active.is_(True))
                .order_by(Category.sort, Category.name)
            )
        ).all()
        products = (
            await self.session.scalars(
                select(Product)
                .where(Product.tenant_id == t, Product.is_active.is_(True))
                .order_by(Product.sort, Product.name)
            )
        ).all()
        variants = (
            await self.session.scalars(
                select(ProductVariant)
                .where(ProductVariant.tenant_id == t, ProductVariant.is_active.is_(True))
                .order_by(ProductVariant.sort, ProductVariant.price_minor)
            )
        ).all()
        stopped_variants, stopped_modifiers = await self._stoplist(branch_id)
        groups = await self._groups_for([p.id for p in products], stopped_modifiers)

        by_product: dict[uuid.UUID, list[MenuVariant]] = defaultdict(list)
        for v in variants:
            by_product[v.product_id].append(
                MenuVariant(v.id, v.name, v.price_minor, v.weight_value, v.weight_unit, v.id not in stopped_variants)
            )
        by_category: dict[uuid.UUID, list[MenuProduct]] = defaultdict(list)
        for p in products:
            pv = by_product.get(p.id)
            if not pv:
                continue  # a product without sellable variants is not shown
            by_category[p.category_id].append(
                MenuProduct(
                    p.id,
                    p.slug,
                    p.name,
                    p.description,
                    p.image_url,
                    pv,
                    list(groups.get(p.id, ())),
                    any(v.available for v in pv),
                )
            )
        return [MenuCategory(c.id, c.slug, c.name, by_category[c.id]) for c in categories if by_category.get(c.id)]
