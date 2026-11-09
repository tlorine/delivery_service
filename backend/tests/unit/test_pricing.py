import uuid

import pytest

from app.modules.pricing.calculator import (
    GroupRule,
    ModifierChoice,
    ModifierRule,
    delivery_fee,
    price_line,
    validate_and_price_modifiers,
)

G_SAUCE, G_EXTRA = uuid.uuid4(), uuid.uuid4()
GARLIC, SPICY, CHEESE, BACON, GONE = (uuid.uuid4() for _ in range(5))
GROUPS = (
    GroupRule(
        G_SAUCE,
        "Соус",
        1,
        1,
        (
            ModifierRule(GARLIC, G_SAUCE, "Чесночный", 0, 1, True),
            ModifierRule(SPICY, G_SAUCE, "Острый", 0, 1, True),
        ),
    ),
    GroupRule(
        G_EXTRA,
        "Добавки",
        0,
        3,
        (
            ModifierRule(CHEESE, G_EXTRA, "Сыр", 5_000, 2, True),
            ModifierRule(BACON, G_EXTRA, "Бекон", 8_000, 2, True),
            ModifierRule(GONE, G_EXTRA, "Нет в наличии", 1_000, 1, False),
        ),
    ),
)


def choose(*pairs: tuple[uuid.UUID, int]) -> list[ModifierChoice]:
    return [ModifierChoice(m, q) for m, q in pairs]


def test_line_total_includes_modifiers_times_quantity() -> None:
    mods, problems = validate_and_price_modifiers(GROUPS, choose((GARLIC, 1), (CHEESE, 2), (BACON, 1)))
    assert problems == []
    line = price_line(32_000, mods, 3)
    assert line.unit_price_minor == 32_000 + 2 * 5_000 + 8_000
    assert line.line_total_minor == 3 * 50_000


@pytest.mark.parametrize(
    ("choices", "code"),
    [
        (choose(), "invalid_modifiers"),  # required sauce missing
        (choose((GARLIC, 1), (SPICY, 1)), "invalid_modifiers"),  # max 1 sauce
        (choose((GARLIC, 1), (CHEESE, 2), (BACON, 2)), "invalid_modifiers"),  # 4 extras > max 3
        (choose((GARLIC, 1), (CHEESE, 3)), "invalid_modifiers"),  # above modifier max_quantity
        (choose((GARLIC, 1), (uuid.uuid4(), 1)), "invalid_modifiers"),  # foreign modifier
        (choose((GARLIC, 1), (GARLIC, 1)), "invalid_modifiers"),  # duplicate
        (choose((GARLIC, 0)), "invalid_modifiers"),  # zero quantity
        (choose((GARLIC, 1), (GONE, 1)), "item_unavailable"),  # stop-listed modifier
    ],
)
def test_invalid_selections(choices: list[ModifierChoice], code: str) -> None:
    _, problems = validate_and_price_modifiers(GROUPS, choices)
    assert code in {p.code for p in problems}


def test_product_without_groups_rejects_any_modifier() -> None:
    _, problems = validate_and_price_modifiers((), choose((GARLIC, 1)))
    assert problems


def test_price_line_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValueError, match="positive"):
        price_line(100, [], 0)


@pytest.mark.parametrize(
    ("fee", "free_from", "subtotal", "expected"),
    [(15_000, 150_000, 149_999, 15_000), (15_000, 150_000, 150_000, 0), (15_000, None, 10**9, 15_000), (0, None, 1, 0)],
)
def test_delivery_fee(fee: int, free_from: int | None, subtotal: int, expected: int) -> None:
    assert delivery_fee(fee, free_from, subtotal) == expected
