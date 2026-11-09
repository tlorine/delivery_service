import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.catalog.service import CatalogService
from app.modules.tenancy.context import TenantContext
from app.modules.tenancy.service import BranchService

router = APIRouter(prefix="/v1/storefront", tags=["storefront"], route_class=DishkaRoute)


class ModifierOut(BaseModel):
    id: uuid.UUID
    name: str
    price_minor: int
    max_quantity: int
    available: bool


class ModifierGroupOut(BaseModel):
    id: uuid.UUID
    name: str
    min_selected: int
    max_selected: int
    modifiers: list[ModifierOut]


class VariantOut(BaseModel):
    id: uuid.UUID
    name: str
    price_minor: int
    weight_value: int | None
    weight_unit: str | None
    available: bool


class ProductOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    image_url: str | None
    available: bool
    variants: list[VariantOut]
    modifier_groups: list[ModifierGroupOut]


class CategoryOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    products: list[ProductOut]


class MenuOut(BaseModel):
    currency: str
    branch_id: uuid.UUID | None
    categories: list[CategoryOut]


@router.get("/menu", response_model=MenuOut)
async def get_menu(
    tenant: FromDishka[TenantContext],
    catalog: FromDishka[CatalogService],
    branches: FromDishka[BranchService],
    branch_id: uuid.UUID | None = None,
) -> MenuOut:
    """Menu with availability at `branch_id` (stop-list). Without it: availability ignoring stop-lists."""
    if branch_id is not None:
        await branches.get(branch_id)
    categories = await catalog.menu(branch_id)
    return MenuOut(
        currency=tenant.currency,
        branch_id=branch_id,
        categories=[
            CategoryOut(
                id=c.id,
                slug=c.slug,
                name=c.name,
                products=[
                    ProductOut(
                        id=p.id,
                        slug=p.slug,
                        name=p.name,
                        description=p.description,
                        image_url=p.image_url,
                        available=p.available,
                        variants=[
                            VariantOut(
                                id=v.id,
                                name=v.name,
                                price_minor=v.price_minor,
                                weight_value=v.weight_value,
                                weight_unit=v.weight_unit,
                                available=v.available,
                            )
                            for v in p.variants
                        ],
                        modifier_groups=[
                            ModifierGroupOut(
                                id=g.id,
                                name=g.name,
                                min_selected=g.min_selected,
                                max_selected=g.max_selected,
                                modifiers=[
                                    ModifierOut(
                                        id=m.id,
                                        name=m.name,
                                        price_minor=m.price_minor,
                                        max_quantity=m.max_quantity,
                                        available=m.available,
                                    )
                                    for m in g.modifiers
                                ],
                            )
                            for g in p.modifier_groups
                        ],
                    )
                    for p in c.products
                ],
            )
            for c in categories
        ],
    )
