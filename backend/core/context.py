"""What is going on around a shopper right now: time of day, weather, payday.

None of this needs a permission or a click. The weather comes from the shopper's *area* (the centre of the geohash
cell we already keep), never from their position, and it is fetched from Open-Meteo (free, no key). If the weather
service is slow or down, prediction simply carries on without it.

For demos, a shopper can "pretend it's evening and rainy". The override is stored on that shopper only (so one judge
flipping it never changes another judge's feed) and is honoured only when DEMO_MODE is on.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from . import geo
from .breaker import get_breaker
from .settings import get_settings

log = logging.getLogger("shopnod.context")

DAYPARTS = ("morning", "midday", "evening", "night")
WEATHERS = ("rain", "hot", "cold", "clear")
REPRESENTATIVE_HOUR = {"morning": 8, "midday": 13, "evening": 18, "night": 22}
HOT_C, COLD_C = 32.0, 14.0
WEATHER_TTL_S = 1800.0
WEATHER_FAIL_TTL_S = 120.0

DAYPART_PHRASE = {"morning": "this morning", "midday": "at lunchtime", "evening": "this evening", "night": "late at night"}
WEATHER_PHRASE = {"rain": "Rainy", "hot": "Hot", "cold": "Chilly", "clear": "Clear"}


def daypart_of(hour: int) -> str:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 16:
        return "midday"
    if 16 <= hour < 21:
        return "evening"
    return "night"


@dataclass(frozen=True)
class Context:
    """The situation one shopper is in. `weather` is rain|hot|cold|clear|unknown."""

    weather: str = "unknown"
    temp_c: float | None = None
    daypart_override: str | None = None
    demo: bool = False  # True when any part came from the demo switch

    def local(self, now: datetime, tz: str) -> tuple[int, str, int, int]:
        """(hour, daypart, weekday 0=Mon, day of month) in the shop's timezone, or the pretended daypart."""
        try:
            local = now.astimezone(ZoneInfo(tz))
        except Exception:  # noqa: BLE001
            local = now
        if self.daypart_override in REPRESENTATIVE_HOUR:
            h = REPRESENTATIVE_HOUR[self.daypart_override]
            return h, self.daypart_override, local.weekday(), local.day
        return local.hour, daypart_of(local.hour), local.weekday(), local.day

    @property
    def key(self) -> str:
        """Changes when the situation changes, so cached rankings are not reused across it."""
        return f"{self.weather}|{self.daypart_override or ''}"

    def summary(self, now: datetime, tz: str) -> str:
        _, part, _, _ = self.local(now, tz)
        when = {"morning": "morning", "midday": "midday", "evening": "evening", "night": "night"}[part]
        if self.weather in WEATHER_PHRASE:
            temp = f" · {round(self.temp_c)}°C" if self.temp_c is not None else ""
            return f"{WEATHER_PHRASE[self.weather]} {when}{temp}"
        return when.capitalize()


# ── weather ──────────────────────────────────────────────────────────────
def classify(code: int | None, temp_c: float | None, precip_mm: float | None) -> str:
    """Open-Meteo WMO weather code + temperature → rain|hot|cold|clear."""
    rainy = (precip_mm or 0) > 0.1 or (code is not None and (51 <= code <= 67 or 80 <= code <= 82 or 95 <= code <= 99))
    if rainy:
        return "rain"
    if temp_c is not None and temp_c >= HOT_C:
        return "hot"
    if temp_c is not None and temp_c <= COLD_C:
        return "cold"
    return "clear"


_cache: dict[str, tuple[float, tuple[str, float | None]]] = {}


def clear_weather_cache() -> None:
    _cache.clear()


async def get_weather(geohash6: str | None) -> tuple[str, float | None]:
    """(weather, temp_c) for the area, cached for 30 minutes. ("unknown", None) when unavailable."""
    s = get_settings()
    if not s.WEATHER_ENABLED or not geohash6:
        return "unknown", None
    hit = _cache.get(geohash6)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    breaker = get_breaker("weather")
    result: tuple[str, float | None] = ("unknown", None)
    ttl = WEATHER_FAIL_TTL_S
    if breaker.allow():
        lat, lng = geo.decode(geohash6)  # the cell centre, about 1 km: never the shopper's own position
        try:
            async with httpx.AsyncClient(timeout=s.WEATHER_TIMEOUT_S) as c:
                r = await c.get(
                    s.WEATHER_URL,
                    params={"latitude": round(lat, 2), "longitude": round(lng, 2), "current": "temperature_2m,precipitation,weather_code"},
                )
                r.raise_for_status()
                cur: dict[str, Any] = r.json().get("current") or {}
            temp = cur.get("temperature_2m")
            result = (classify(cur.get("weather_code"), temp, cur.get("precipitation")), float(temp) if temp is not None else None)
            ttl = WEATHER_TTL_S
            breaker.record_success()
        except Exception as exc:  # noqa: BLE001 - never let weather break the feed
            breaker.record_failure()
            log.info("weather unavailable", extra={"error": str(exc)[:120]})
    _cache[geohash6] = (time.monotonic() + ttl, result)
    return result


# ── per-shopper context (real, with the demo override on top) ────────────
def demo_override(prefs: dict[str, Any]) -> dict[str, str | None]:
    """The shopper's "pretend it's…" choice, only while DEMO_MODE is on."""
    if not get_settings().DEMO_MODE:
        return {"weather": None, "daypart": None}
    d = prefs.get("demo_ctx") or {}
    w, p = d.get("weather"), d.get("daypart")
    return {"weather": w if w in WEATHERS else None, "daypart": p if p in DAYPARTS else None}


async def resolve(prefs: dict[str, Any], geohash6: str | None) -> Context:
    ov = demo_override(prefs)
    if ov["weather"]:
        temp = {"hot": 36.0, "cold": 9.0, "rain": 22.0, "clear": 26.0}[ov["weather"]]
        return Context(weather=ov["weather"], temp_c=temp, daypart_override=ov["daypart"], demo=True)
    weather, temp_c = await get_weather(geohash6)
    return Context(weather=weather, temp_c=temp_c, daypart_override=ov["daypart"], demo=bool(ov["daypart"]))
