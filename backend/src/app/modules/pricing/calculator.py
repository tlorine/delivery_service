"""Pure pricing and modifier rules. Integers only (ADR-0008); no I/O so it is trivially testable."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ModifierRule:
    id: uuid.UUID
    group_id: uuid.UUID
    name: str
    price_minor: int
    max_quantity: int
    available: bool


@dataclass(frozen=True, slots=True)
class GroupRule:
    id: uuid.UUID
    name: str
    min_selected: int
    max_selected: int
    modifiers: tuple[ModifierRule, ...]


@dataclass(frozen=True, slots=True)
class ModifierChoice:
    modifier_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class PricedModifier:
    modifier_id: uuid.UUID
    group_name: str
    name: str
    unit_price_minor: int
    quantity: int


@dataclass(frozen=True, slots=True)
class LineProblem:
    code: str  # invalid_modifiers | item_unavailable
    detail: str


@dataclass(slots=True)
class LineResult:
    unit_price_minor: int  # variant + modifiers, for one piece
    quantity: int
    line_total_minor: int
    modifiers: list[PricedModifier] = field(default_factory=list)
    problems: list[LineProblem] = field(default_factory=list)


def validate_and_price_modifiers(
    groups: Sequence[GroupRule], choices: Sequence[ModifierChoice]
) -> tuple[list[PricedModifier], list[LineProblem]]:
    by_id = {m.id: (g, m) for g in groups for m in g.modifiers}
    problems: list[LineProblem] = []
    priced: list[PricedModifier] = []
    per_group: dict[uuid.UUID, int] = {g.id: 0 for g in groups}
    seen: set[uuid.UUID] = set()

    for choice in choices:
        if choice.modifier_id in seen:
            problems.append(LineProblem("invalid_modifiers", "modifier selected twice"))
            continue
        seen.add(choice.modifier_id)
        found = by_id.get(choice.modifier_id)
        if found is None:
            problems.append(LineProblem("invalid_modifiers", "modifier does not belong to this product"))
            continue
        group, mod = found
        if not 1 <= choice.quantity <= mod.max_quantity:
            problems.append(LineProblem("invalid_modifiers", f"'{mod.name}': quantity out of range"))
            continue
        if not mod.available:
            problems.append(LineProblem("item_unavailable", f"'{mod.name}' is unavailable"))
            continue
        per_group[group.id] += choice.quantity
        priced.append(PricedModifier(mod.id, group.name, mod.name, mod.price_minor, choice.quantity))

    for g in groups:
        n = per_group[g.id]
        if n < g.min_selected:
            problems.append(LineProblem("invalid_modifiers", f"'{g.name}': choose at least {g.min_selected}"))
        elif n > g.max_selected:
            problems.append(LineProblem("invalid_modifiers", f"'{g.name}': choose at most {g.max_selected}"))
    return priced, problems


def price_line(variant_price_minor: int, modifiers: Sequence[PricedModifier], quantity: int) -> LineResult:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    unit = variant_price_minor + sum(m.unit_price_minor * m.quantity for m in modifiers)
    return LineResult(unit, quantity, unit * quantity, list(modifiers))


def delivery_fee(fee_minor: int, free_from_minor: int | None, subtotal_minor: int) -> int:
    if free_from_minor is not None and subtotal_minor >= free_from_minor:
        return 0
    return fee_minor
