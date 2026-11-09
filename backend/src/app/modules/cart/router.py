import uuid
from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Header, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.http import client_ip
from app.di import Limiters
from app.modules.cart.service import CartService, PricedCart
from app.modules.pricing.calculator import ModifierChoice
from app.modules.tenancy.context import TenantContext

router = APIRouter(prefix="/v1", tags=["cart"], route_class=DishkaRoute)

CartToken = Annotated[str | None, Header(alias="X-Cart-Token", description="Secret returned by POST /v1/carts")]


class ModifierChoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modifier_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=20)


class AddItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variant_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=99)
    modifiers: list[ModifierChoiceIn] = Field(default_factory=list, max_length=30)


class SetQuantityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=0, le=99)


class CartModifierOut(BaseModel):
    modifier_id: uuid.UUID
    group_name: str
    name: str
    unit_price_minor: int
    quantity: int


class LineProblemOut(BaseModel):
    code: str
    detail: str


class CartLineOut(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str
    variant_name: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int
    modifiers: list[CartModifierOut]
    problems: list[LineProblemOut]


class CartOut(BaseModel):
    id: uuid.UUID
    currency: str
    items: list[CartLineOut]
    item_count: int
    subtotal_minor: int
    has_problems: bool


class CartCreatedOut(BaseModel):
    cart_token: str
    cart: CartOut


def to_out(priced: PricedCart, currency: str) -> CartOut:
    items = []
    for line in priced.lines:
        p = line.priced
        items.append(
            CartLineOut(
                id=line.item_id,
                variant_id=line.variant_id,
                product_id=line.product_id,
                product_name=line.product_name,
                variant_name=line.variant_name,
                quantity=p.quantity if p else 0,
                unit_price_minor=p.unit_price_minor if p else 0,
                line_total_minor=p.line_total_minor if p and line.ok else 0,
                modifiers=[
                    CartModifierOut(
                        modifier_id=m.modifier_id,
                        group_name=m.group_name,
                        name=m.name,
                        unit_price_minor=m.unit_price_minor,
                        quantity=m.quantity,
                    )
                    for m in (p.modifiers if p else [])
                ],
                problems=[LineProblemOut(code=x.code, detail=x.detail) for x in line.problems],
            )
        )
    return CartOut(
        id=priced.cart.id,
        currency=currency,
        items=items,
        item_count=sum(i.quantity for i in items if not i.problems),
        subtotal_minor=priced.subtotal_minor,
        has_problems=any(i.problems for i in items),
    )


@router.post("/carts", response_model=CartCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_cart(
    request: Request,
    tenant: FromDishka[TenantContext],
    carts: FromDishka[CartService],
    limiters: FromDishka[Limiters],
    settings: FromDishka[Settings],
) -> CartCreatedOut:
    limiters.carts.hit(f"cart:{client_ip(request, settings)}")
    token, cart = await carts.create()
    return CartCreatedOut(cart_token=token, cart=to_out(await carts.price(cart, None), tenant.currency))


@router.get("/cart", response_model=CartOut)
async def get_cart(
    tenant: FromDishka[TenantContext],
    carts: FromDishka[CartService],
    x_cart_token: CartToken = None,
    branch_id: uuid.UUID | None = None,
) -> CartOut:
    cart = await carts.get(x_cart_token)
    return to_out(await carts.price(cart, branch_id), tenant.currency)


@router.post("/cart/items", response_model=CartOut)
async def add_item(
    body: AddItemIn,
    tenant: FromDishka[TenantContext],
    carts: FromDishka[CartService],
    x_cart_token: CartToken = None,
    branch_id: uuid.UUID | None = None,
) -> CartOut:
    choices = [ModifierChoice(m.modifier_id, m.quantity) for m in body.modifiers]
    cart = await carts.add_item(x_cart_token, body.variant_id, body.quantity, choices)
    return to_out(await carts.price(cart, branch_id), tenant.currency)


@router.patch("/cart/items/{item_id}", response_model=CartOut)
async def set_quantity(
    item_id: uuid.UUID,
    body: SetQuantityIn,
    tenant: FromDishka[TenantContext],
    carts: FromDishka[CartService],
    x_cart_token: CartToken = None,
    branch_id: uuid.UUID | None = None,
) -> CartOut:
    cart = await carts.set_quantity(x_cart_token, item_id, body.quantity)
    return to_out(await carts.price(cart, branch_id), tenant.currency)


@router.delete("/cart/items/{item_id}", response_model=CartOut)
async def remove_item(
    item_id: uuid.UUID,
    tenant: FromDishka[TenantContext],
    carts: FromDishka[CartService],
    x_cart_token: CartToken = None,
    branch_id: uuid.UUID | None = None,
) -> CartOut:
    cart = await carts.remove_item(x_cart_token, item_id)
    return to_out(await carts.price(cart, branch_id), tenant.currency)
