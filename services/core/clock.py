"""Overridable clock so tests (and quiet-detection drills) can use a fake time."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

_offset: timedelta | None = None
_fixed: datetime | None = None


def now() -> datetime:
    if _fixed is not None:
        return _fixed
    base = datetime.now(timezone.utc)
    return base + _offset if _offset else base


def set_fixed(dt: datetime | None) -> None:
    global _fixed
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    _fixed = dt


def advance(delta: timedelta) -> None:
    global _fixed, _offset
    if _fixed is not None:
        _fixed = _fixed + delta
    else:
        _offset = (_offset or timedelta()) + delta


def reset() -> None:
    global _fixed, _offset
    _fixed = None
    _offset = None
