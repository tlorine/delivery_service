import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.ordering.state_machine import Fulfillment, OrderStatus
from app.modules.payments.provider import PaymentMethod

Str200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptStr = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=100)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields (e.g. total_minor, status) are rejected


class CustomerIn(Strict):
    name: Str200
    phone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=32)]


class AddressIn(Strict):
    street: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    flat: OptStr = None
    entrance: OptStr = None
    floor: OptStr = None
    intercom: OptStr = None
    comment: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=500)] = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class CheckoutIn(Strict):
    fulfillment: Fulfillment
    branch_id: uuid.UUID | None = Field(None, description="Required for pickup; for delivery chosen by zone if omitted")
    address: AddressIn | None = None
    payment_method: PaymentMethod
    change_from_minor: int | None = Field(
        None, strict=True, ge=0, description="Cash: banknote the courier needs change from"
    )
    requested_at: datetime | None = Field(None, description="Ready/delivered by; null = as soon as possible")
    comment: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=1000)] = None


class QuoteIn(CheckoutIn):
    pass


class OrderIn(CheckoutIn):
    customer: CustomerIn
    personal_data_consent: Literal[True] = Field(description="Consent to personal data processing (152-FZ)")
    expected_total_minor: int | None = Field(
        None, strict=True, ge=0, description="Total shown to the buyer; mismatch -> 409"
    )


class Problem(BaseModel):
    code: str
    detail: str
    item_id: uuid.UUID | None = None


class QuoteOut(BaseModel):
    ok: bool
    problems: list[Problem]
    branch_id: uuid.UUID | None
    currency: str
    subtotal_minor: int
    delivery_fee_minor: int
    total_minor: int
    min_order_minor: int | None
    delivery_zone_name: str | None
    estimated_ready_at: datetime | None


class OrderItemModifierOut(BaseModel):
    modifier_id: uuid.UUID
    group_name: str
    name: str
    unit_price_minor: int
    quantity: int


class OrderItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID
    product_name: str
    variant_name: str
    unit_price_minor: int
    quantity: int
    line_total_minor: int
    modifiers: list[OrderItemModifierOut]


class StatusChangeOut(BaseModel):
    from_status: OrderStatus | None
    to_status: OrderStatus
    actor_type: str
    reason: str | None
    created_at: datetime


class OrderOut(BaseModel):
    id: uuid.UUID
    number: int
    status: OrderStatus
    fulfillment: Fulfillment
    channel: str = Field(description="web | telegram | mobile")
    branch_id: uuid.UUID
    payment_method: PaymentMethod
    payment_status: str
    currency: str
    subtotal_minor: int
    delivery_fee_minor: int
    total_minor: int
    change_from_minor: int | None
    customer_name: str
    customer_phone: str
    address: AddressIn | None
    comment: str | None
    requested_at: datetime | None
    promised_at: datetime | None
    created_at: datetime
    items: list[OrderItemOut]
    history: list[StatusChangeOut]
    can_cancel: bool


class OrderCreatedOut(BaseModel):
    order: OrderOut
    order_token: str = Field(description="Secret for GET /v1/orders/{order_token}; keep it on the device")


class TransitionIn(Strict):
    to_status: OrderStatus
    reason: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=500)] = None
