import uuid

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status
from pydantic import BaseModel

from app.modules.catalog import admin_schemas as s
from app.modules.catalog.admin_service import CatalogAdminService
from app.modules.identity.models import Role
from app.modules.identity.service import StaffContext

router = APIRouter(prefix="/v1/admin", tags=["admin: menu"], route_class=DishkaRoute)


class CreatedOut(BaseModel):
    id: uuid.UUID


@router.get("/catalog", response_model=s.CatalogAdminOut)
async def get_catalog(staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]) -> s.CatalogAdminOut:
    """Whole menu including hidden items, for the editor (operators need it for the stop-list)."""
    staff.require(Role.OPERATOR)
    return await svc.catalog()


@router.post("/categories", response_model=CreatedOut, status_code=201)
async def create_category(
    body: s.CategoryIn, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> CreatedOut:
    staff.require(Role.MANAGER)
    return CreatedOut(id=await svc.create_category(body))


@router.patch("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_category(
    category_id: uuid.UUID, body: s.CategoryPatch, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.update_category(category_id, body)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.delete_category(category_id)


@router.post("/products", response_model=CreatedOut, status_code=201)
async def create_product(
    body: s.ProductIn, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> CreatedOut:
    staff.require(Role.MANAGER)
    return CreatedOut(id=await svc.create_product(body))


@router.patch("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_product(
    product_id: uuid.UUID, body: s.ProductPatch, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.update_product(product_id, body)


@router.put("/products/{product_id}/modifier-groups", status_code=status.HTTP_204_NO_CONTENT)
async def set_product_groups(
    product_id: uuid.UUID,
    body: s.ProductGroupsIn,
    staff: FromDishka[StaffContext],
    svc: FromDishka[CatalogAdminService],
) -> None:
    staff.require(Role.MANAGER)
    await svc.set_product_groups(product_id, body.group_ids)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.delete_product(product_id)


@router.post("/products/{product_id}/variants", response_model=CreatedOut, status_code=201)
async def add_variant(
    product_id: uuid.UUID, body: s.VariantIn, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> CreatedOut:
    staff.require(Role.MANAGER)
    return CreatedOut(id=await svc.add_variant(product_id, body))


@router.patch("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_variant(
    variant_id: uuid.UUID, body: s.VariantPatch, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.update_variant(variant_id, body)


@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variant(
    variant_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.delete_variant(variant_id)


@router.post("/modifier-groups", response_model=CreatedOut, status_code=201)
async def create_group(
    body: s.ModifierGroupIn, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> CreatedOut:
    staff.require(Role.MANAGER)
    return CreatedOut(id=await svc.create_group(body))


@router.patch("/modifier-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_group(
    group_id: uuid.UUID,
    body: s.ModifierGroupPatch,
    staff: FromDishka[StaffContext],
    svc: FromDishka[CatalogAdminService],
) -> None:
    staff.require(Role.MANAGER)
    await svc.update_group(group_id, body)


@router.delete("/modifier-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.delete_group(group_id)


@router.post("/modifier-groups/{group_id}/modifiers", response_model=CreatedOut, status_code=201)
async def add_modifier(
    group_id: uuid.UUID, body: s.ModifierIn, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> CreatedOut:
    staff.require(Role.MANAGER)
    return CreatedOut(id=await svc.add_modifier(group_id, body))


@router.patch("/modifiers/{modifier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_modifier(
    modifier_id: uuid.UUID, body: s.ModifierPatch, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.update_modifier(modifier_id, body)


@router.delete("/modifiers/{modifier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_modifier(
    modifier_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> None:
    staff.require(Role.MANAGER)
    await svc.delete_modifier(modifier_id)


@router.get("/branches/{branch_id}/stoplist", response_model=s.StoplistOut)
async def get_stoplist(
    branch_id: uuid.UUID, staff: FromDishka[StaffContext], svc: FromDishka[CatalogAdminService]
) -> s.StoplistOut:
    staff.require(Role.OPERATOR)
    return await svc.stoplist(branch_id)


@router.put("/branches/{branch_id}/stoplist/variants/{variant_id}", response_model=s.StoplistOut)
async def stop_variant(
    branch_id: uuid.UUID,
    variant_id: uuid.UUID,
    body: s.StopIn,
    staff: FromDishka[StaffContext],
    svc: FromDishka[CatalogAdminService],
) -> s.StoplistOut:
    staff.require(Role.OPERATOR)
    return await svc.set_stop(branch_id, variant_id=variant_id, stopped=body.stopped)


@router.put("/branches/{branch_id}/stoplist/modifiers/{modifier_id}", response_model=s.StoplistOut)
async def stop_modifier(
    branch_id: uuid.UUID,
    modifier_id: uuid.UUID,
    body: s.StopIn,
    staff: FromDishka[StaffContext],
    svc: FromDishka[CatalogAdminService],
) -> s.StoplistOut:
    staff.require(Role.OPERATOR)
    return await svc.set_stop(branch_id, modifier_id=modifier_id, stopped=body.stopped)
