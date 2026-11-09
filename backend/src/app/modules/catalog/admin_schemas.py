import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Slug = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=100)]
# Strict: JSON integers only ("100" or 1.0 are refused), minor units (ADR-0008).
Money = Annotated[int, Field(strict=True, ge=0, le=100_000_000, description="Minor units (kopecks)")]


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryIn(In):
    name: Name
    slug: Slug | None = None
    sort: int = 0
    is_active: bool = True


class CategoryPatch(In):
    name: Name | None = None
    slug: Slug | None = None
    sort: int | None = None
    is_active: bool | None = None


class VariantIn(In):
    name: Name
    price_minor: Money
    weight_value: int | None = Field(None, ge=0, le=100_000)
    weight_unit: Annotated[str, StringConstraints(pattern=r"^(g|kg|ml|l)$")] | None = None
    sort: int = 0
    is_active: bool = True


class VariantPatch(In):
    name: Name | None = None
    price_minor: Money | None = None
    weight_value: int | None = Field(None, ge=0, le=100_000)
    weight_unit: Annotated[str, StringConstraints(pattern=r"^(g|kg|ml|l)$")] | None = None
    sort: int | None = None
    is_active: bool | None = None


class ProductIn(In):
    category_id: uuid.UUID
    name: Name
    slug: Slug | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    image_url: Annotated[str, StringConstraints(pattern=r"^https://", max_length=1000)] | None = None
    sort: int = 0
    is_active: bool = True
    variants: list[VariantIn] = Field(min_length=1, max_length=20)
    modifier_group_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class ProductPatch(In):
    category_id: uuid.UUID | None = None
    name: Name | None = None
    slug: Slug | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    image_url: Annotated[str, StringConstraints(pattern=r"^https://", max_length=1000)] | None = None
    sort: int | None = None
    is_active: bool | None = None


class ProductGroupsIn(In):
    group_ids: list[uuid.UUID] = Field(max_length=20)


class ModifierIn(In):
    name: Name
    price_minor: Money = 0
    max_quantity: int = Field(1, ge=1, le=20)
    sort: int = 0
    is_active: bool = True


class ModifierPatch(In):
    name: Name | None = None
    price_minor: Money | None = None
    max_quantity: int | None = Field(None, ge=1, le=20)
    sort: int | None = None
    is_active: bool | None = None


class ModifierGroupIn(In):
    name: Name
    min_selected: int = Field(0, ge=0, le=20)
    max_selected: int = Field(1, ge=1, le=20)
    sort: int = 0
    modifiers: list[ModifierIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _bounds(self) -> "ModifierGroupIn":
        if self.min_selected > self.max_selected:
            raise ValueError("min_selected must not exceed max_selected")
        return self


class ModifierGroupPatch(In):
    name: Name | None = None
    min_selected: int | None = Field(None, ge=0, le=20)
    max_selected: int | None = Field(None, ge=1, le=20)
    sort: int | None = None


class StopIn(In):
    stopped: bool


# ---- output -------------------------------------------------------------------------------------


class VariantAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    price_minor: int
    weight_value: int | None
    weight_unit: str | None
    sort: int
    is_active: bool


class ProductAdminOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    slug: str
    name: str
    description: str | None
    image_url: str | None
    sort: int
    is_active: bool
    variants: list[VariantAdminOut]
    modifier_group_ids: list[uuid.UUID]


class CategoryAdminOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    sort: int
    is_active: bool


class ModifierAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    price_minor: int
    max_quantity: int
    sort: int
    is_active: bool


class ModifierGroupAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    min_selected: int
    max_selected: int
    sort: int
    modifiers: list[ModifierAdminOut]


class CatalogAdminOut(BaseModel):
    categories: list[CategoryAdminOut]
    products: list[ProductAdminOut]
    modifier_groups: list[ModifierGroupAdminOut]


class StoplistOut(BaseModel):
    branch_id: uuid.UUID
    variant_ids: list[uuid.UUID]
    modifier_ids: list[uuid.UUID]
