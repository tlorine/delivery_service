"""Opening hours in the branch's local time zone (IANA). Pure functions over plain data."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class Interval:
    weekday: int  # 0 = Monday
    opens_at: time
    closes_at: time  # <= opens_at: closes next day


def _concrete(day: date, iv: Interval, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, iv.opens_at, tz)
    end_day = day + timedelta(days=1) if iv.closes_at <= iv.opens_at else day
    return start, datetime.combine(end_day, iv.closes_at, tz)


def open_windows(
    hours: Sequence[Interval], tz_name: str, around: datetime, days: int = 2
) -> list[tuple[datetime, datetime]]:
    """Concrete open windows from yesterday (overnight shifts) through `days` days ahead, as aware datetimes."""
    tz = ZoneInfo(tz_name)
    local = around.astimezone(tz).date()
    windows = []
    for offset in range(-1, days + 1):
        day = local + timedelta(days=offset)
        for iv in hours:
            if iv.weekday == day.weekday():
                windows.append(_concrete(day, iv, tz))
    return sorted(windows)


def is_open_at(hours: Sequence[Interval], tz_name: str, moment: datetime) -> bool:
    return any(s <= moment < e for s, e in open_windows(hours, tz_name, moment, days=0))


def current_window_end(hours: Sequence[Interval], tz_name: str, moment: datetime) -> datetime | None:
    for s, e in open_windows(hours, tz_name, moment, days=0):
        if s <= moment < e:
            return e
    return None


def next_opening(hours: Sequence[Interval], tz_name: str, moment: datetime) -> datetime | None:
    for s, _ in open_windows(hours, tz_name, moment, days=7):
        if s > moment:
            return s
    return None


def time_slots(
    hours: Sequence[Interval],
    tz_name: str,
    now: datetime,
    lead: timedelta,
    step: timedelta = timedelta(minutes=30),
    days: int = 1,
) -> list[datetime]:
    """Selectable 'ready by' times: at least `lead` from now, aligned to `step`, inside open windows."""
    earliest = now + lead
    slots: list[datetime] = []
    step_s = int(step.total_seconds())
    for start, end in open_windows(hours, tz_name, now, days=days):
        t = max(start + lead, earliest)
        # align up to the step in local time
        ts = int(t.timestamp())
        t = datetime.fromtimestamp(((ts + step_s - 1) // step_s) * step_s, tz=start.tzinfo)
        while t <= end:
            if not slots or t > slots[-1]:
                slots.append(t)
            t += step
    return slots
