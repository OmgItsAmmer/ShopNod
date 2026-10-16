"""Time-window helpers. Pure functions; all arithmetic in the shop's local time zone."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .types import MIN_WINDOW_MINUTES, Limits


def parse_hhmm(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - unknown zone name: fall back to UTC
        return ZoneInfo("UTC")


def local_day_bounds(now: datetime, tz_name: str) -> tuple[datetime, datetime]:
    """UTC start/end of the shop-local calendar day containing `now`."""
    tz = _tz(tz_name)
    local = now.astimezone(tz)
    start = datetime.combine(local.date(), time(0), tzinfo=tz)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def _at(local_date, minutes: int, tz: ZoneInfo) -> datetime:
    return datetime.combine(local_date, time(0), tzinfo=tz) + timedelta(minutes=minutes)


def allowed_span_minutes(limits: Limits) -> int:
    span = limits.allowed_end_min - limits.allowed_start_min
    return span if span > 0 else 24 * 60


def within_allowed(start: datetime, end: datetime, limits: Limits) -> bool:
    """True if [start, end] sits inside allowed hours on a single local day."""
    lo, hi = limits.allowed_start_min, limits.allowed_end_min
    if hi <= lo:  # no real restriction configured
        return True
    tz = _tz(limits.tz)
    ls, le = start.astimezone(tz), end.astimezone(tz)
    if ls.date() != le.date() and not (le.time() == time(0) and (le - ls) <= timedelta(days=1)):
        return False
    s_min = ls.hour * 60 + ls.minute
    e_min = le.hour * 60 + le.minute + (24 * 60 if le.date() != ls.date() else 0)
    return lo <= s_min and e_min <= hi


def fit_window(
    start: datetime, end: datetime, now: datetime, limits: Limits
) -> tuple[datetime, datetime]:
    """Move a window into the next allowed time (never earlier than `now`)."""
    tz = _tz(limits.tz)
    span = allowed_span_minutes(limits)
    duration = min(max(end - start, timedelta(minutes=MIN_WINDOW_MINUTES)), timedelta(minutes=span))
    s = max(start, now)
    lo, hi = limits.allowed_start_min, limits.allowed_end_min
    if hi <= lo:
        return s, s + duration
    for _ in range(9):
        local = s.astimezone(tz)
        day_start = _at(local.date(), lo, tz)
        day_end = _at(local.date(), hi, tz)
        if local < day_start:
            s = day_start.astimezone(UTC)
            continue
        if local + timedelta(minutes=MIN_WINDOW_MINUTES) > day_end:
            s = _at(local.date() + timedelta(days=1), lo, tz).astimezone(UTC)
            continue
        e = min(local + duration, day_end)
        return s, e.astimezone(UTC)
    return s, s + duration  # pragma: no cover - unreachable in practice


def round_up(dt: datetime, minutes: int = 5) -> datetime:
    """Round a datetime up to the next `minutes` boundary (seconds dropped)."""
    base = dt.replace(second=0, microsecond=0)
    if base < dt:
        base += timedelta(minutes=1)
    extra = (-(base.minute)) % minutes
    return base + timedelta(minutes=extra)


def local_hour(dt: datetime, tz_name: str) -> int:
    return dt.astimezone(_tz(tz_name)).hour


def local_weekday_key(dt: datetime, tz_name: str) -> str:
    return ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[dt.astimezone(_tz(tz_name)).weekday()]
