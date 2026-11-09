"""Menu management for staff. Every change is one transaction with an audit record."""

import uuid
from collections import defaultdict
from typing import Any, TypeVar

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleViolation, Conflict, NotFound
from app.core.slug import slugify
from app.modules.audit.service import AuditService
from app.modules.catalog import admin_schemas as s
from app.modules.catalog.models import (
    Category,
    Modifier,
    ModifierGroup,
    Product,
    ProductModifierGroup,
    ProductVariant,
    StoplistEntry,
)
from app.modules.identity.service import StaffContext
from app.modules.ordering.models import OrderItem, OrderItemModifier
from app.modules.tenancy.service import BranchService

T = TypeVar("T", Category, Product, ProductVariant, ModifierGroup, Modifier)


class CatalogAdminService:
    def __init__(self, session: AsyncSession, staff: StaffContext, audit: AuditService, branches: BranchService):
        self.session = session
        self.staff = staff
        self.tenant_id = staff.tenant_id
        self.audit = audit
        self.branches = branches

    # ---- helpers ------------------------------------------------------------------------------

    async def _get(self, model: type[T], entity_id: uuid.UUID) -> T:
        row = await self.session.scalar(select(model).where(model.tenant_id == self.tenant_id, model.id == entity_id))
        if row is None:
            raise NotFound(f"{model.__tablename__} not found", code="not_found")
        return row

    def _record(self, action: str, entity: str, entity_id: uuid.UUID, **data: Any) -> None:
        self.audit.record(
            f"catalog.{entity}.{action}",
            entity,
            entity_id,
            actor_type="staff",
            actor_id=self.staff.user_id,
            data={k: str(v) for k, v in data.items()},
        )

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if "slug" in str(exc.orig):
                raise Conflict("this address (slug) is already used", code="slug_taken") from exc
            raise

    async def _unique_slug(
        self, model: type[Category] | type[Product], base: str, exclude: uuid.UUID | None = None
    ) -> str:
        slug, n = base, 1
        while True:
            stmt = select(model.id).where(model.tenant_id == self.tenant_id, model.slug == slug)
            if exclude:
                stmt = stmt.where(model.id != exclude)
            if await self.session.scalar(stmt) is None:
                return slug
            n += 1
            slug = f"{base}-{n}"

    @staticmethod
    def _apply(entity: object, patch: s.In) -> dict[str, Any]:
        changes = patch.model_dump(exclude_unset=True)
        for key, value in changes.items():
            setattr(entity, key, value)
        return changes

    # ---- read ---------------------------------------------------------------------------------

    async def catalog(self) -> s.CatalogAdminOut:
        t = self.tenant_id
        categories = (
            await self.session.scalars(
                select(Category).where(Category.tenant_id == t).order_by(Category.sort, Category.name)
            )
        ).all()
        products = (
            await self.session.scalars(
                select(Product).where(Product.tenant_id == t).order_by(Product.sort, Product.name)
            )
        ).all()
        variants = (
            await self.session.scalars(
                select(ProductVariant)
                .where(ProductVariant.tenant_id == t)
                .order_by(ProductVariant.sort, ProductVariant.price_minor)
            )
        ).all()
        links = (
            await self.session.scalars(
                select(ProductModifierGroup)
                .where(ProductModifierGroup.tenant_id == t)
                .order_by(ProductModifierGroup.sort)
            )
        ).all()
        groups = (
            await self.session.scalars(
                select(ModifierGroup)
                .where(ModifierGroup.tenant_id == t)
                .order_by(ModifierGroup.sort, ModifierGroup.name)
            )
        ).all()
        modifiers = (
            await self.session.scalars(
                select(Modifier).where(Modifier.tenant_id == t).order_by(Modifier.sort, Modifier.name)
            )
        ).all()

        v_by_p: dict[uuid.UUID, list[s.VariantAdminOut]] = defaultdict(list)
        for v in variants:
            v_by_p[v.product_id].append(s.VariantAdminOut.model_validate(v, from_attributes=True))
        g_by_p: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for link in links:
            g_by_p[link.product_id].append(link.group_id)
        m_by_g: dict[uuid.UUID, list[s.ModifierAdminOut]] = defaultdict(list)
        for m in modifiers:
            m_by_g[m.group_id].append(s.ModifierAdminOut.model_validate(m, from_attributes=True))
        return s.CatalogAdminOut(
            categories=[s.CategoryAdminOut.model_validate(c, from_attributes=True) for c in categories],
            products=[
                s.ProductAdminOut(
                    id=p.id,
                    category_id=p.category_id,
                    slug=p.slug,
                    name=p.name,
                    description=p.description,
                    image_url=p.image_url,
                    sort=p.sort,
                    is_active=p.is_active,
                    variants=v_by_p[p.id],
                    modifier_group_ids=g_by_p[p.id],
                )
                for p in products
            ],
            modifier_groups=[
                s.ModifierGroupAdminOut(
                    id=g.id,
                    name=g.name,
                    min_selected=g.min_selected,
                    max_selected=g.max_selected,
                    sort=g.sort,
                    modifiers=m_by_g[g.id],
                )
                for g in groups
            ],
        )

    # ---- categories ---------------------------------------------------------------------------

    async def create_category(self, body: s.CategoryIn) -> uuid.UUID:
        slug = body.slug or await self._unique_slug(Category, slugify(body.name, "category"))
        category = Category(
            tenant_id=self.tenant_id, slug=slug, name=body.name, sort=body.sort, is_active=body.is_active
        )
        self.session.add(category)
        await self.session.flush()
        self._record("created", "category", category.id, name=body.name)
        await self._commit()
        return category.id

    async def update_category(self, category_id: uuid.UUID, patch: s.CategoryPatch) -> None:
        category = await self._get(Category, category_id)
        changes = self._apply(category, patch)
        self._record("updated", "category", category.id, **changes)
        await self._commit()

    async def delete_category(self, category_id: uuid.UUID) -> None:
        category = await self._get(Category, category_id)
        has_products = await self.session.scalar(
            select(exists().where(Product.tenant_id == self.tenant_id, Product.category_id == category.id))
        )
        if has_products:
            raise Conflict("move or delete the products first", code="category_not_empty")
        await self.session.delete(category)
        self._record("deleted", "category", category_id)
        await self._commit()

    # ---- products and variants ----------------------------------------------------------------

    async def _check_groups(self, group_ids: list[uuid.UUID]) -> None:
        if not group_ids:
            return
        found = set(
            (
                await self.session.scalars(
                    select(ModifierGroup.id).where(
                        ModifierGroup.tenant_id == self.tenant_id, ModifierGroup.id.in_(group_ids)
                    )
                )
            ).all()
        )
        if found != set(group_ids):
            raise NotFound("modifier group not found", code="not_found")

    async def create_product(self, body: s.ProductIn) -> uuid.UUID:
        await self._get(Category, body.category_id)
        await self._check_groups(body.modifier_group_ids)
        slug = body.slug or await self._unique_slug(Product, slugify(body.name, "product"))
        product = Product(
            tenant_id=self.tenant_id,
            category_id=body.category_id,
            slug=slug,
            name=body.name,
            description=body.description,
            image_url=body.image_url,
            sort=body.sort,
            is_active=body.is_active,
        )
        self.session.add(product)
        await self.session.flush()
        for v in body.variants:
            self.session.add(ProductVariant(tenant_id=self.tenant_id, product_id=product.id, **v.model_dump()))
        for i, gid in enumerate(dict.fromkeys(body.modifier_group_ids)):
            self.session.add(
                ProductModifierGroup(tenant_id=self.tenant_id, product_id=product.id, group_id=gid, sort=i)
            )
        self._record("created", "product", product.id, name=body.name)
        await self._commit()
        return product.id

    async def update_product(self, product_id: uuid.UUID, patch: s.ProductPatch) -> None:
        product = await self._get(Product, product_id)
        if patch.category_id is not None:
            await self._get(Category, patch.category_id)
        changes = self._apply(product, patch)
        self._record("updated", "product", product.id, **changes)
        await self._commit()

    async def set_product_groups(self, product_id: uuid.UUID, group_ids: list[uuid.UUID]) -> None:
        product = await self._get(Product, product_id)
        await self._check_groups(group_ids)
        await self.session.execute(
            delete(ProductModifierGroup).where(
                ProductModifierGroup.tenant_id == self.tenant_id, ProductModifierGroup.product_id == product.id
            )
        )
        for i, gid in enumerate(dict.fromkeys(group_ids)):
            self.session.add(
                ProductModifierGroup(tenant_id=self.tenant_id, product_id=product.id, group_id=gid, sort=i)
            )
        self._record("groups_set", "product", product.id, groups=len(group_ids))
        await self._commit()

    async def delete_product(self, product_id: uuid.UUID) -> None:
        product = await self._get(Product, product_id)
        ordered = await self.session.scalar(
            select(exists().where(OrderItem.tenant_id == self.tenant_id, OrderItem.product_id == product.id))
        )
        if ordered:
            raise Conflict("the product was ordered before: hide it instead", code="product_has_orders")
        await self.session.delete(product)  # variants, links, stop-list entries cascade
        self._record("deleted", "product", product_id)
        await self._commit()

    async def add_variant(self, product_id: uuid.UUID, body: s.VariantIn) -> uuid.UUID:
        product = await self._get(Product, product_id)
        variant = ProductVariant(tenant_id=self.tenant_id, product_id=product.id, **body.model_dump())
        self.session.add(variant)
        await self.session.flush()
        self._record("created", "variant", variant.id, product=product.id, price_minor=body.price_minor)
        await self._commit()
        return variant.id

    async def update_variant(self, variant_id: uuid.UUID, patch: s.VariantPatch) -> None:
        variant = await self._get(ProductVariant, variant_id)
        before = variant.price_minor
        changes = self._apply(variant, patch)
        self._record(
            "updated",
            "variant",
            variant.id,
            **changes,
            **({"price_before": before} if "price_minor" in changes else {}),
        )
        await self._commit()

    async def delete_variant(self, variant_id: uuid.UUID) -> None:
        variant = await self._get(ProductVariant, variant_id)
        siblings = await self.session.scalar(
            select(func.count())
            .select_from(ProductVariant)
            .where(ProductVariant.tenant_id == self.tenant_id, ProductVariant.product_id == variant.product_id)
        )
        if (siblings or 0) <= 1:
            raise BusinessRuleViolation("a product needs at least one variant", code="last_variant")
        ordered = await self.session.scalar(
            select(exists().where(OrderItem.tenant_id == self.tenant_id, OrderItem.variant_id == variant.id))
        )
        if ordered:
            raise Conflict("the variant was ordered before: hide it instead", code="variant_has_orders")
        await self.session.delete(variant)
        self._record("deleted", "variant", variant_id)
        await self._commit()

    # ---- modifier groups ----------------------------------------------------------------------

    async def create_group(self, body: s.ModifierGroupIn) -> uuid.UUID:
        group = ModifierGroup(
            tenant_id=self.tenant_id,
            name=body.name,
            min_selected=body.min_selected,
            max_selected=body.max_selected,
            sort=body.sort,
        )
        self.session.add(group)
        await self.session.flush()
        for m in body.modifiers:
            self.session.add(Modifier(tenant_id=self.tenant_id, group_id=group.id, **m.model_dump()))
        self._record("created", "modifier_group", group.id, name=body.name)
        await self._commit()
        return group.id

    async def update_group(self, group_id: uuid.UUID, patch: s.ModifierGroupPatch) -> None:
        group = await self._get(ModifierGroup, group_id)
        changes = self._apply(group, patch)
        if group.min_selected > group.max_selected:
            raise BusinessRuleViolation("min_selected must not exceed max_selected", code="invalid_bounds")
        self._record("updated", "modifier_group", group.id, **changes)
        await self._commit()

    async def delete_group(self, group_id: uuid.UUID) -> None:
        group = await self._get(ModifierGroup, group_id)
        ordered = await self.session.scalar(
            select(
                exists().where(
                    OrderItemModifier.tenant_id == self.tenant_id,
                    OrderItemModifier.modifier_id.in_(select(Modifier.id).where(Modifier.group_id == group.id)),
                )
            )
        )
        if ordered:
            raise Conflict("modifiers of this group were ordered before: hide them instead", code="group_has_orders")
        await self.session.delete(group)
        self._record("deleted", "modifier_group", group_id)
        await self._commit()

    async def add_modifier(self, group_id: uuid.UUID, body: s.ModifierIn) -> uuid.UUID:
        group = await self._get(ModifierGroup, group_id)
        modifier = Modifier(tenant_id=self.tenant_id, group_id=group.id, **body.model_dump())
        self.session.add(modifier)
        await self.session.flush()
        self._record("created", "modifier", modifier.id, group=group.id)
        await self._commit()
        return modifier.id

    async def update_modifier(self, modifier_id: uuid.UUID, patch: s.ModifierPatch) -> None:
        modifier = await self._get(Modifier, modifier_id)
        changes = self._apply(modifier, patch)
        self._record("updated", "modifier", modifier.id, **changes)
        await self._commit()

    async def delete_modifier(self, modifier_id: uuid.UUID) -> None:
        modifier = await self._get(Modifier, modifier_id)
        ordered = await self.session.scalar(
            select(
                exists().where(
                    OrderItemModifier.tenant_id == self.tenant_id, OrderItemModifier.modifier_id == modifier.id
                )
            )
        )
        if ordered:
            raise Conflict("the modifier was ordered before: hide it instead", code="modifier_has_orders")
        await self.session.delete(modifier)
        self._record("deleted", "modifier", modifier_id)
        await self._commit()

    # ---- stop-list ----------------------------------------------------------------------------

    async def stoplist(self, branch_id: uuid.UUID) -> s.StoplistOut:
        await self.branches.get(branch_id, active_only=False)
        rows = (
            await self.session.scalars(
                select(StoplistEntry).where(
                    StoplistEntry.tenant_id == self.tenant_id, StoplistEntry.branch_id == branch_id
                )
            )
        ).all()
        return s.StoplistOut(
            branch_id=branch_id,
            variant_ids=[r.variant_id for r in rows if r.variant_id],
            modifier_ids=[r.modifier_id for r in rows if r.modifier_id],
        )

    async def set_stop(
        self,
        branch_id: uuid.UUID,
        *,
        variant_id: uuid.UUID | None = None,
        modifier_id: uuid.UUID | None = None,
        stopped: bool,
    ) -> s.StoplistOut:
        await self.branches.get(branch_id, active_only=False)
        if variant_id:
            await self._get(ProductVariant, variant_id)
        if modifier_id:
            await self._get(Modifier, modifier_id)
        cond = [StoplistEntry.tenant_id == self.tenant_id, StoplistEntry.branch_id == branch_id]
        cond.append(StoplistEntry.variant_id == variant_id if variant_id else StoplistEntry.modifier_id == modifier_id)
        existing = await self.session.scalar(select(StoplistEntry).where(*cond))
        if stopped and existing is None:
            self.session.add(
                StoplistEntry(
                    tenant_id=self.tenant_id, branch_id=branch_id, variant_id=variant_id, modifier_id=modifier_id
                )
            )
        elif not stopped and existing is not None:
            await self.session.delete(existing)
        target = variant_id or modifier_id
        assert target is not None
        self.audit.record(
            "stoplist." + ("added" if stopped else "removed"),
            "variant" if variant_id else "modifier",
            target,
            actor_type="staff",
            actor_id=self.staff.user_id,
            data={"branch": str(branch_id)},
        )
        await self._commit()
        return await self.stoplist(branch_id)
