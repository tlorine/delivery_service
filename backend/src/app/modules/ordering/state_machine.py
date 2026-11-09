"""Order lifecycle (docs/architecture/domain-model.md §3). Any transition not listed here is refused."""

from enum import StrEnum

from app.core.errors import Conflict


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Fulfillment(StrEnum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class Actor(StrEnum):
    CUSTOMER = "customer"
    STAFF = "staff"
    SYSTEM = "system"


S = OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    S.PENDING: frozenset({S.CONFIRMED, S.REJECTED, S.CANCELLED}),
    S.CONFIRMED: frozenset({S.PREPARING, S.CANCELLED}),
    S.PREPARING: frozenset({S.READY, S.CANCELLED}),
    S.READY: frozenset({S.DELIVERING, S.COMPLETED, S.CANCELLED}),
    S.DELIVERING: frozenset({S.COMPLETED}),
    S.COMPLETED: frozenset(),
    S.CANCELLED: frozenset(),
    S.REJECTED: frozenset(),
}

FINAL = frozenset(s for s, nxt in ALLOWED_TRANSITIONS.items() if not nxt)
REASON_REQUIRED = frozenset({S.REJECTED, S.CANCELLED})


def check_transition(
    current: OrderStatus, target: OrderStatus, fulfillment: Fulfillment, actor: Actor, reason: str | None
) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise Conflict(f"cannot move order from {current} to {target}", code="invalid_status_transition")
    if current == S.READY and target == S.DELIVERING and fulfillment != Fulfillment.DELIVERY:
        raise Conflict("pickup orders are not delivered", code="invalid_status_transition")
    if current == S.READY and target == S.COMPLETED and fulfillment != Fulfillment.PICKUP:
        raise Conflict("delivery orders complete after delivering", code="invalid_status_transition")
    if actor == Actor.CUSTOMER and not (current == S.PENDING and target == S.CANCELLED):
        raise Conflict("customers can only cancel pending orders", code="invalid_status_transition")
    if actor == Actor.STAFF and target in REASON_REQUIRED and not (reason and reason.strip()):
        raise Conflict("a reason is required", code="reason_required")


def next_statuses(current: OrderStatus, fulfillment: Fulfillment) -> list[OrderStatus]:
    """What the admin UI may offer as buttons."""
    result = []
    for target in ALLOWED_TRANSITIONS[current]:
        try:
            check_transition(current, target, fulfillment, Actor.SYSTEM, "x")
        except Conflict:
            continue
        result.append(target)
    order = list(OrderStatus)
    return sorted(result, key=order.index)
