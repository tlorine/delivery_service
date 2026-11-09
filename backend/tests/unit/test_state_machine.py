import itertools

import pytest

from app.core.errors import Conflict
from app.modules.ordering.state_machine import (
    ALLOWED_TRANSITIONS,
    FINAL,
    Actor,
    Fulfillment,
    OrderStatus,
    check_transition,
    next_statuses,
)

S, F = OrderStatus, Fulfillment

VALID_DELIVERY = [S.PENDING, S.CONFIRMED, S.PREPARING, S.READY, S.DELIVERING, S.COMPLETED]
VALID_PICKUP = [S.PENDING, S.CONFIRMED, S.PREPARING, S.READY, S.COMPLETED]


@pytest.mark.parametrize(("path", "fulfillment"), [(VALID_DELIVERY, F.DELIVERY), (VALID_PICKUP, F.PICKUP)])
def test_happy_paths(path: list[OrderStatus], fulfillment: Fulfillment) -> None:
    for a, b in itertools.pairwise(path):
        check_transition(a, b, fulfillment, Actor.STAFF, None)


@pytest.mark.parametrize(("current", "target"), list(itertools.product(list(S), list(S))))
def test_every_unlisted_transition_is_refused(current: OrderStatus, target: OrderStatus) -> None:
    if target in ALLOWED_TRANSITIONS[current]:
        return
    with pytest.raises(Conflict) as e:
        check_transition(current, target, F.DELIVERY, Actor.STAFF, "reason")
    assert e.value.code == "invalid_status_transition"


def test_final_states_have_no_exits() -> None:
    assert {S.COMPLETED, S.CANCELLED, S.REJECTED} == FINAL


def test_pickup_cannot_be_delivered_and_delivery_cannot_skip_delivering() -> None:
    with pytest.raises(Conflict):
        check_transition(S.READY, S.DELIVERING, F.PICKUP, Actor.STAFF, None)
    with pytest.raises(Conflict):
        check_transition(S.READY, S.COMPLETED, F.DELIVERY, Actor.STAFF, None)


def test_customer_can_only_cancel_pending() -> None:
    check_transition(S.PENDING, S.CANCELLED, F.PICKUP, Actor.CUSTOMER, None)
    for current in (S.CONFIRMED, S.PREPARING, S.READY):
        with pytest.raises(Conflict):
            check_transition(current, S.CANCELLED, F.PICKUP, Actor.CUSTOMER, None)
    with pytest.raises(Conflict):
        check_transition(S.PENDING, S.CONFIRMED, F.PICKUP, Actor.CUSTOMER, None)


@pytest.mark.parametrize("target", [S.REJECTED, S.CANCELLED])
def test_staff_must_give_reason_to_reject_or_cancel(target: OrderStatus) -> None:
    for reason in (None, "", "   "):
        with pytest.raises(Conflict) as e:
            check_transition(S.PENDING, target, F.DELIVERY, Actor.STAFF, reason)
        assert e.value.code == "reason_required"
    check_transition(S.PENDING, target, F.DELIVERY, Actor.STAFF, "нет курьеров")


def test_next_statuses_respects_fulfillment() -> None:
    assert next_statuses(S.READY, F.PICKUP) == [S.COMPLETED, S.CANCELLED]
    assert next_statuses(S.READY, F.DELIVERY) == [S.DELIVERING, S.CANCELLED]
    assert next_statuses(S.COMPLETED, F.PICKUP) == []
