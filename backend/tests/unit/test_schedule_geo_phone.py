from datetime import UTC, datetime, time, timedelta

import pytest

from app.core.phone import normalize_phone
from app.modules.delivery.geo import polygon_contains, validate_polygon
from app.modules.tenancy.schedule import Interval, current_window_end, is_open_at, next_opening, time_slots

TZ = "Europe/Moscow"  # UTC+3, no DST
DAILY = [Interval(d, time(10), time(23)) for d in range(7)]
NIGHT = [Interval(4, time(20), time(4))]  # Friday 20:00 -> Saturday 04:00


def msk(day: int, hour: int, minute: int = 0) -> datetime:
    """2026-11-<day> local Moscow time as an aware UTC datetime."""
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC) - timedelta(hours=3)


def test_open_and_closed_in_local_time() -> None:
    assert is_open_at(DAILY, TZ, msk(10, 10, 0))
    assert is_open_at(DAILY, TZ, msk(10, 22, 59))
    assert not is_open_at(DAILY, TZ, msk(10, 23, 0))
    assert not is_open_at(DAILY, TZ, msk(10, 9, 59))


def test_overnight_interval_belongs_to_the_previous_day() -> None:
    # 2026-11-13 is a Friday.
    assert is_open_at(NIGHT, TZ, msk(13, 21))
    assert is_open_at(NIGHT, TZ, msk(14, 3, 30))
    assert not is_open_at(NIGHT, TZ, msk(14, 4, 0))
    assert current_window_end(NIGHT, TZ, msk(13, 21)) == msk(14, 4)


def test_next_opening() -> None:
    assert next_opening(DAILY, TZ, msk(10, 23, 30)) == msk(11, 10)


def test_time_slots_respect_lead_time_and_closing() -> None:
    slots = time_slots(DAILY, TZ, msk(10, 21, 50), timedelta(minutes=40), days=0)
    assert slots[0] == msk(10, 22, 30)
    assert slots[-1] == msk(10, 23, 0)


ZONE = {
    "type": "Polygon",
    "coordinates": [
        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],  # hole
    ],
}


@pytest.mark.parametrize(("lat", "lon", "inside"), [(1, 1, True), (5, 5, False), (11, 5, False), (9.99, 0.01, True)])
def test_polygon_with_hole(lat: float, lon: float, inside: bool) -> None:
    assert polygon_contains(ZONE, lat, lon) is inside


def test_polygon_validation() -> None:
    validate_polygon(ZONE)
    with pytest.raises(ValueError, match="closed"):
        validate_polygon({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8 (918) 123-45-67", "+79181234567"),
        ("+7 918 123 45 67", "+79181234567"),
        ("9181234567", "+79181234567"),
        ("8 862 200-00-00", "+78622000000"),
        ("12345", None),
        ("+7 018 123 45 67", None),
        ("", None),
    ],
)
def test_phone_normalization_ru(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw, "RU") == expected


def test_phone_other_country_requires_plus() -> None:
    assert normalize_phone("+995 555 12 34 56", "GE") == "+995555123456"
    assert normalize_phone("555 12 34 56", "GE") is None
