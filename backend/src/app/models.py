"""Import every model so metadata is complete (Alembic, tests)."""

from app.modules.audit.models import AuditLog
from app.modules.cart.models import Cart, CartItem
from app.modules.catalog.models import (
    Category,
    Modifier,
    ModifierGroup,
    Product,
    ProductModifierGroup,
    ProductVariant,
    StoplistEntry,
)
from app.modules.customers.models import Customer
from app.modules.delivery.models import DeliveryZone
from app.modules.identity.models import Membership, StaffSession, StaffUser
from app.modules.notifications.models import OutboxEvent
from app.modules.ordering.models import Order, OrderItem, OrderItemModifier, OrderStatusChange
from app.modules.telegram.models import TelegramBot
from app.modules.tenancy.models import Branch, BranchHours, Tenant, TenantCounter, TenantDomain

__all__ = [
    "AuditLog",
    "Branch",
    "BranchHours",
    "Cart",
    "CartItem",
    "Category",
    "Customer",
    "DeliveryZone",
    "Membership",
    "Modifier",
    "ModifierGroup",
    "Order",
    "OrderItem",
    "OrderItemModifier",
    "OrderStatusChange",
    "OutboxEvent",
    "Product",
    "ProductModifierGroup",
    "ProductVariant",
    "StaffSession",
    "StaffUser",
    "StoplistEntry",
    "TelegramBot",
    "Tenant",
    "TenantCounter",
    "TenantDomain",
]
