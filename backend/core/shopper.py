"""Shopper side (Plan 1): consents, preferences, the feed, claims and privacy rights.

Privacy rules that hold everywhere in this module:
- No raw coordinates are stored. A shopper's area is a geohash6 cell (or a named market).
- Every distance shown or sent is rounded to 50 m.
- The Matching Agent never sees the install id, coordinates or names (see `matching_prompt`).
- One offer has one price for everyone: the feed never computes a per-shopper price.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import ai, clock, context, flags, geo, outbox, predict, tokens
from .errors import AppError, ErrorCode, not_found
from .models import (
    Claim,
    Consent,
    MarketArea,
    Notification,
    Offer,
    Redemption,
    Shop,
    Shopper,
    ShopperAffinity,
    ShopperEvent,
    ShopperPreference,
    ShopperPushToken,
    ShoppingList,
)
from .settings import get_settings

PURPOSES = ("location", "notifications", "list", "personalisation", "analytics")
POLICY_VERSION = "1.0"
BEHAVIOUR_TTL = timedelta(days=30)  # events, notifications, shopping lists
CLAIM_TTL = timedelta(minutes=30)
FEED_SIZE = 10
FEED_CACHE_TTL_S = 600
EVENT_TYPES = ("open", "dismiss", "save", "why_up", "why_down")
DEFAULT_PREFS: dict[str, Any] = {
    "categories": [], "dietary": [], "languages": ["en"], "max_distance_m": 800, "daily_limit": 3,
    "quiet_start": "21:00", "quiet_end": "08:00", "muted_shops": [], "muted_categories": [],
}
# Shop category keys (Plan 2 templates) → the labels the shopper app uses for interests.
CATEGORY_LABELS = {
    "bakery": "Bakery", "grocery": "Groceries", "fruit_veg": "Fruit & veg", "cafe": "Café", "general": "Household",
    "restaurant": "Meals", "meals": "Meals",
}
NOTIFY_THRESHOLD_AI = 0.6
NOTIFY_THRESHOLD_RULES = 0.55


def category_label(shop_category: str | None) -> str:
    return CATEGORY_LABELS.get((shop_category or "").lower(), (shop_category or "Other").replace("_", " ").title())


# ── consents & preferences ───────────────────────────────────────────────
async def current_consents(s: AsyncSession, install_id: uuid.UUID) -> dict[str, bool]:
    rows = (
        await s.execute(select(Consent.purpose).where(Consent.install_id == install_id, Consent.withdrawn_at.is_(None)))
    ).scalars().all()
    granted = set(rows)
    return {p: p in granted for p in PURPOSES}


async def has_consent(s: AsyncSession, install_id: uuid.UUID, purpose: str) -> bool:
    return (await current_consents(s, install_id)).get(purpose, False)


async def set_consents(s: AsyncSession, install_id: uuid.UUID, wanted: dict[str, bool], policy_version: str) -> dict[str, bool]:
    """Every change saves a row with the time it was given or withdrawn."""
    now = clock.now()
    current = await current_consents(s, install_id)
    for purpose in PURPOSES:
        if purpose not in wanted or bool(wanted[purpose]) == current[purpose]:
            continue
        if wanted[purpose]:
            s.add(Consent(install_id=install_id, purpose=purpose, granted_at=now, policy_version=policy_version))
        else:
            await s.execute(
                update(Consent)
                .where(Consent.install_id == install_id, Consent.purpose == purpose, Consent.withdrawn_at.is_(None))
                .values(withdrawn_at=now)
            )
    await s.flush()
    if current["list"] and wanted.get("list") is False:
        await s.execute(delete(ShoppingList).where(ShoppingList.install_id == install_id))
    if current["notifications"] and wanted.get("notifications") is False:
        await s.execute(delete(ShopperPushToken).where(ShopperPushToken.install_id == install_id))
    return await current_consents(s, install_id)


async def get_prefs(s: AsyncSession, install_id: uuid.UUID) -> dict[str, Any]:
    row = await s.get(ShopperPreference, install_id)
    return {**DEFAULT_PREFS, **(row.data if row else {})}


async def set_prefs(s: AsyncSession, install_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    row = await s.get(ShopperPreference, install_id)
    merged = {**DEFAULT_PREFS, **(row.data if row else {}), **data}
    if row is None:
        s.add(ShopperPreference(install_id=install_id, data=merged, updated_at=clock.now()))
    else:
        row.data, row.updated_at = merged, clock.now()
    shopper = await s.get(Shopper, install_id)
    if shopper is not None and data.get("languages"):
        shopper.languages = list(data["languages"])
    await s.flush()
    return merged


async def get_list(s: AsyncSession, install_id: uuid.UUID) -> list[str]:
    row = (await s.execute(select(ShoppingList).where(ShoppingList.install_id == install_id))).scalars().first()
    if row is None or (row.expires_at and row.expires_at <= clock.now()):
        return []
    return [str(x) for x in (row.items or [])]


async def set_list(s: AsyncSession, install_id: uuid.UUID, items: list[str]) -> tuple[list[str], datetime]:
    if not await has_consent(s, install_id, "list"):
        raise AppError(ErrorCode.consent_required, "Turn on 'Use my shopping list' to save a list.", 409)
    clean = [i.strip()[:60] for i in items if i and i.strip()][:50]
    expires = clock.now() + BEHAVIOUR_TTL
    row = (await s.execute(select(ShoppingList).where(ShoppingList.install_id == install_id))).scalars().first()
    if row is None:
        s.add(ShoppingList(install_id=install_id, items=clean, expires_at=expires))
    else:
        row.items, row.expires_at = clean, expires
    await s.flush()
    return clean, expires


# ── location ─────────────────────────────────────────────────────────────
async def set_location(s: AsyncSession, shopper: Shopper, lat: float | None, lng: float | None, market: str | None) -> tuple[str, str | None]:
    """Save only the area (geohash6 or market) and the time. Never raw coordinates or a history."""
    if market:
        area = (await s.execute(select(MarketArea).where(MarketArea.slug == market))).scalar_one_or_none()
        if area is None and market == "demo":
            from . import templates

            area = await templates.ensure_demo_market(s)
        if area is None:
            raise not_found("That market")
        shopper.geohash6 = geo.encode(area.center_lat, area.center_lng, 6)
        shopper.area_slug = area.slug
        name = area.name
    else:
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise AppError(ErrorCode.validation_error, "Send a location or a market.", 422)
        if not await has_consent(s, shopper.install_id, "location"):
            raise AppError(ErrorCode.consent_required, "Turn on location to see offers near you, or join a market.", 409)
        shopper.geohash6 = geo.encode(lat, lng, 6)
        shopper.area_slug = None
        name = None
    shopper.last_seen_at = clock.now()
    await s.flush()
    return shopper.geohash6, name


async def _origin(s: AsyncSession, shopper: Shopper, lat: float | None, lng: float | None) -> tuple[float, float] | None:
    """Where distances are measured from: the request's own position (not stored), the market centre, or the cell centre."""
    if lat is not None and lng is not None:
        return lat, lng
    if shopper.area_slug:
        area = (await s.execute(select(MarketArea).where(MarketArea.slug == shopper.area_slug))).scalar_one_or_none()
        if area is not None:
            return area.center_lat, area.center_lng
    if shopper.geohash6:
        return geo.decode(shopper.geohash6)
    return None


# ── offers as the shopper sees them ──────────────────────────────────────
def offer_prices(offer: Offer) -> tuple[int, int]:
    items = offer.items or []
    was = sum(int(i.get("was_minor", 0)) for i in items)
    now = sum(int(i.get("new_price_minor", 0)) for i in items)
    return was, now


def offer_title(offer: Offer) -> str:
    names = [str(i.get("name", "")) for i in (offer.items or []) if i.get("name")]
    if not names:
        return "Special offer"
    return names[0] if len(names) == 1 else f"{names[0]} + {len(names) - 1} more"


def remaining(offer: Offer) -> int:
    return max(offer.cap - offer.redeemed_count, 0)


def offer_view(offer: Offer, shop: Shop, lang: str, *, distance_m: int | None, why: str = "", source: str = "rules",
               score: float | None = None, reasons: list[str] | None = None) -> dict[str, Any]:
    was, now = offer_prices(offer)
    copy = offer.copy or {}
    copy_source = "ai" if offer.copy_source == "ai" else "shop"
    return {
        "offer": {
            "id": str(offer.id), "shop_id": str(offer.shop_id), "title": offer_title(offer),
            "description": copy.get(lang) or copy.get("en") or next(iter(copy.values()), ""),
            "category": category_label(shop.category), "discount_pct": offer.pct, "was_price": was, "now_price": now,
            "currency": shop.currency, "starts_at": offer.starts_at.isoformat(), "ends_at": offer.ends_at.isoformat(),
            "remaining": remaining(offer), "status": offer.status, "copy_source": copy_source, "tags": [],
            "items": [{"name": i.get("name"), "was_minor": i.get("was_minor"), "new_price_minor": i.get("new_price_minor")} for i in offer.items or []],
        },
        "shop": {"id": str(shop.id), "name": shop.name, "category": category_label(shop.category)},
        "distance_m": distance_m,
        "score": round(score, 3) if score is not None else None,
        "why": why,
        "reasons": reasons if reasons is not None else ([why] if why else []),
        "source": source,
        "copy_source": copy_source,
    }


@dataclass
class Candidate:
    offer: Offer
    shop: Shop
    distance_m: int | None  # rounded to 50 m
    rules_score: float = 0.0  # the prediction score (name kept for the AI fallback and older callers)
    why: str = ""
    reasons: list[str] = field(default_factory=list)
    parts: dict[str, float] = field(default_factory=dict)
    expires_in_h: float | None = None  # soonest-expiring item in the offer, if any


@dataclass
class Profile:
    """What ranking may know about a shopper. No install id, no coordinates, no names."""

    list_items: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    dietary: list[str] = field(default_factory=list)
    affinity: dict[str, float] = field(default_factory=dict)
    language: str = "en"
    personalised: bool = True
    max_distance_m: int = 800
    pp: predict.PredictProfile | None = None  # what we predict they want (built from their own data)
    ctx: context.Context = field(default_factory=context.Context)  # time of day, weather, payday
    market: predict.MarketIndex | None = None  # what people near them claim at this time of day


async def load_profile(s: AsyncSession, shopper: Shopper, lang: str | None = None, *, prefs: dict[str, Any] | None = None) -> Profile:
    prefs = prefs if prefs is not None else await get_prefs(s, shopper.install_id)
    pp = (await predict.build_profiles(s, [shopper.install_id]))[shopper.install_id]
    ctx = await context.resolve(prefs, shopper.geohash6)
    return Profile(
        list_items=[str(x) for x in (await get_list(s, shopper.install_id))] if pp.personalised else [],
        categories=list(prefs.get("categories") or []),
        dietary=list(prefs.get("dietary") or []),
        affinity={k: v for k, v in pp.cat.items() if v > 0},
        language=lang or (prefs.get("languages") or shopper.languages or ["en"])[0],
        personalised=pp.personalised,
        max_distance_m=int(prefs.get("max_distance_m") or 800),
        pp=pp,
        ctx=ctx,
        market=await predict.get_market(s) if pp.personalised else None,
    )


def distance_label(m: int | None) -> str:
    if m is None:
        return ""
    return f"{m} m" if m < 1000 else f"{m / 1000:.1f} km"


def rules_score(c: Candidate, p: Profile, now: datetime) -> tuple[float, str]:
    """The prediction for one offer: (score 0..1, plain-words reason). Also fills `c.reasons` and `c.parts`.

    Not personalised (no `personalisation` consent): sorted by distance only. Otherwise see `core/predict.py`.
    """
    max_d = max(p.max_distance_m, 1)
    dist_txt = distance_label(c.distance_m)
    if not p.personalised:
        dist = 1.0 - min((c.distance_m or 0) / max_d, 1.0)
        c.reasons, c.parts = ["Near you"], {}
        return round(dist, 4), f"Near you · {dist_txt}" if dist_txt else "Near you"
    pp = p.pp or predict.PredictProfile.basic(p.list_items, p.categories)
    f = predict.features_of(c.offer.items or [], category_label(c.shop.category), str(c.shop.id))
    pred = predict.predict(
        pp, f, shop_name=c.shop.name, distance_m=c.distance_m, max_distance_m=max_d,
        minutes_left=max((c.offer.ends_at - now).total_seconds() / 60, 0), discount_pct=c.offer.pct,
        claimed=c.offer.claimed_count, cap=c.offer.cap, expires_in_h=c.expires_in_h, now=now, tz=c.shop.timezone,
        ctx=p.ctx, market=p.market,
    )
    c.reasons, c.parts = pred.reasons, pred.parts
    why = f"{pred.why} · {dist_txt}" if dist_txt else pred.why
    return pred.score, why


async def candidates(s: AsyncSession, shopper: Shopper, *, lat: float | None = None, lng: float | None = None,
                     prefs: dict[str, Any] | None = None, offer_ids: list[uuid.UUID] | None = None) -> list[Candidate]:
    """Active offers in the shopper's cell and the 8 around it, after the hard filters (plain code, never AI)."""
    if not shopper.geohash6:
        return []
    now = clock.now()
    prefs = prefs or await get_prefs(s, shopper.install_id)
    cells = geo.neighbours(shopper.geohash6)
    # A shopper who joined a market sees every shop of that market, not only the 9 cells around them (demo shops are
    # spread over several cells). Everyone else gets the 9 cells.
    where_area = Offer.geohash6.in_(cells)
    if shopper.area_slug:
        area_id = (await s.execute(select(MarketArea.id).where(MarketArea.slug == shopper.area_slug))).scalar_one_or_none()
        if area_id is not None:
            where_area = or_(where_area, Shop.area_id == area_id)
    stmt = (
        select(Offer, Shop)
        .join(Shop, Shop.id == Offer.shop_id)
        .where(Offer.status == "active", Offer.ends_at > now, where_area)  # incl. windows starting soon
    )
    if offer_ids is not None:
        stmt = stmt.where(Offer.id.in_(offer_ids))
    rows = (await s.execute(stmt)).all()
    origin = await _origin(s, shopper, lat, lng)
    in_market = shopper.area_slug is not None
    muted_shops = {str(x) for x in prefs.get("muted_shops") or []}
    muted_cats = set(prefs.get("muted_categories") or [])
    max_d = int(prefs.get("max_distance_m") or 800)
    out: list[Candidate] = []
    for offer, shop in rows:
        if shop.is_demo and shopper.area_slug != "demo":
            continue  # demo shops only show to shoppers who joined the Demo Market
        if remaining(offer) <= 0:
            continue
        if str(shop.id) in muted_shops or category_label(shop.category) in muted_cats:
            continue
        d = None
        if origin is not None and shop.lat is not None and shop.lng is not None:
            d = geo.round_distance_m(geo.haversine_m(origin[0], origin[1], shop.lat, shop.lng))
        # A shopper who joined a market sees the whole market; a real location uses their distance limit.
        if not in_market and d is not None and d > max_d:
            continue
        out.append(Candidate(offer, shop, d))
    await _attach_expiry(s, out, now)
    return out


async def _attach_expiry(s: AsyncSession, cands: list[Candidate], now: datetime) -> None:
    """Hours until the soonest-expiring item in each offer (stock that must go today is worth sending to people)."""
    from .models import Item

    ids = {uuid.UUID(str(i["item_id"])) for c in cands for i in (c.offer.items or []) if i.get("item_id")}
    if not ids:
        return
    exp = {r[0]: r[1] for r in (await s.execute(select(Item.id, Item.expires_at).where(Item.id.in_(ids), Item.expires_at.is_not(None)))).all()}
    for c in cands:
        hours = [
            (exp[u] - now).total_seconds() / 3600
            for i in (c.offer.items or [])
            if i.get("item_id") and (u := uuid.UUID(str(i["item_id"]))) in exp and exp[u] > now
        ]
        c.expires_in_h = min(hours) if hours else None


# ── Matching Agent ───────────────────────────────────────────────────────
class MatchItem(BaseModel):
    offer_id: str
    score: float = Field(ge=0, le=1)
    reason: str = Field(max_length=90)


class MatchOut(BaseModel):
    items: list[MatchItem]


def _distance_band(m: int | None) -> str:
    if m is None:
        return "unknown"
    lo = (m // 50) * 50
    return f"{lo}–{lo + 50} m"


def matching_prompt(cands: list[Candidate], p: Profile, now: datetime) -> str:
    """Only what the agent needs. Never the install id, coordinates or names."""
    offers = [
        {
            "offer_id": str(c.offer.id),
            "category": category_label(c.shop.category),
            "items": [str(i.get("name", "")) for i in c.offer.items or []],
            "discount_pct": c.offer.pct,
            "distance_band": _distance_band(c.distance_m),
            "minutes_left": int(max((c.offer.ends_at - now).total_seconds() // 60, 0)),
            "prior_score": round(c.rules_score, 2),  # our own prediction, as a hint
            "signals": sorted(k for k, v in c.parts.items() if v >= 0.05 and k != "base"),
        }
        for c in cands
    ]
    shopper = {
        "shopping_list": p.list_items, "categories": p.categories, "dietary": p.dietary, "language": p.language,
        "hour": now.hour, "weekday": now.strftime("%A"), "weather": p.ctx.weather,
    }
    return json.dumps({"shopper": shopper, "offers": offers}, ensure_ascii=False)


MATCHING_INSTRUCTIONS = (
    "You rank local shop offers for one shopper. For every offer give a score from 0 to 1 (how useful it is to this "
    "shopper right now) and a short reason (max 90 characters) in the shopper's language. Use only the facts given. "
    "Never invent prices or claims. Each offer has a prior_score and the signals behind it (list, context, basket, market, "
    "learned...). Treat prior_score as a strong hint and adjust it with common sense about food and the weather: for "
    "example warm snacks on a rainy evening, or items that go together with the shopping list."
)


async def _ai_match(cands: list[Candidate], p: Profile, now: datetime) -> tuple[dict[str, MatchItem], bool]:
    """Returns ({offer_id: item}, ai_used). Falls back to the rules score on any problem (Plan 3 §0.9)."""
    settings = get_settings()

    def fallback() -> MatchOut:
        return MatchOut(items=[MatchItem(offer_id=str(c.offer.id), score=min(max(c.rules_score, 0), 1), reason=c.why[:90]) for c in cands])

    runner = None
    if settings.OPENAI_API_KEY:
        async def runner(trace: ai.RunTrace):
            from .agents.openai_runner import run_openai_agent

            return await run_openai_agent(
                trace, name="Matching Agent", instructions=MATCHING_INSTRUCTIONS,
                user_input=matching_prompt(cands, p, now), output_type=MatchOut, model=settings.OPENAI_MODEL_FAST,
            )

    res = await ai.run_structured(
        "matching", f"{len(cands)} offers, list={len(p.list_items)} items, lang={p.language}", MatchOut,
        runner=runner, fallback=fallback, timeout_s=4.0,
    )
    known = {str(c.offer.id) for c in cands}
    return {i.offer_id: i for i in res.output.items if i.offer_id in known}, not res.fallback_used


_feed_cache: dict[str, tuple[float, dict[str, Any]]] = {}


async def _cache_get(key: str) -> dict[str, Any] | None:
    from .redis_util import get_redis

    r = get_redis()
    if r is not None:
        try:
            raw = await r.get(f"feed:{key}")
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            pass
    hit = _feed_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    _feed_cache.pop(key, None)
    return None


async def _cache_set(key: str, value: dict[str, Any]) -> None:
    from .redis_util import get_redis

    r = get_redis()
    if r is not None:
        try:
            await r.set(f"feed:{key}", json.dumps(value), ex=FEED_CACHE_TTL_S)
            return
        except Exception:  # noqa: BLE001
            pass
    if len(_feed_cache) > 5000:
        _feed_cache.clear()
    _feed_cache[key] = (time.monotonic() + FEED_CACHE_TTL_S, value)


def clear_feed_cache() -> None:
    _feed_cache.clear()


async def rank(cands: list[Candidate], p: Profile, *, install_id: uuid.UUID | None = None) -> tuple[list[Candidate], dict[str, MatchItem], str]:
    """Score candidates. Returns (sorted candidates, AI items by offer id, source 'ai'|'rules')."""
    now = clock.now()
    for c in cands:
        c.rules_score, c.why = rules_score(c, p, now)
    if not cands or not p.personalised:
        return sorted(cands, key=lambda c: (c.distance_m is None, c.distance_m or 0)), {}, "rules"
    outage = await flags.get_flag(flags.AI_OUTAGE)
    key = None
    if install_id is not None:
        ids = ",".join(sorted(str(c.offer.id) for c in cands))
        lh = hashlib.sha256("|".join(p.list_items).encode()).hexdigest()[:12]
        rev = p.pp.rev if p.pp else 0
        key = hashlib.sha256(f"{install_id}|{ids}|{lh}|{p.language}|{outage}|{p.ctx.key}|{rev}".encode()).hexdigest()
        cached = await _cache_get(key)
        if cached is not None:
            items = {k: MatchItem(**v) for k, v in cached["items"].items()}
            source = cached["source"]
            return _sort(cands, items, source), items, source
    items, ai_used = await _ai_match(cands, p, now)
    source = "ai" if ai_used else "rules"
    if key is not None:
        await _cache_set(key, {"items": {k: v.model_dump() for k, v in items.items()}, "source": source})
    return _sort(cands, items, source), items, source


def _sort(cands: list[Candidate], items: dict[str, MatchItem], source: str) -> list[Candidate]:
    def score(c: Candidate) -> float:
        it = items.get(str(c.offer.id))
        return it.score if (it and source == "ai") else c.rules_score

    return sorted(cands, key=lambda c: (-score(c), c.distance_m or 0))


async def feed(s: AsyncSession, shopper: Shopper, *, lang: str | None, lat: float | None = None, lng: float | None = None) -> list[dict[str, Any]]:
    prefs = await get_prefs(s, shopper.install_id)
    p = await load_profile(s, shopper, lang)
    cands = await candidates(s, shopper, lat=lat, lng=lng, prefs=prefs)
    ranked, items, source = await rank(cands, p, install_id=shopper.install_id)
    out = []
    for c in ranked[:FEED_SIZE]:
        it = items.get(str(c.offer.id))
        if source == "ai" and it is not None:
            why = it.reason if not c.distance_m else f"{it.reason} · {distance_label(c.distance_m)}"
            out.append(offer_view(c.offer, c.shop, p.language, distance_m=c.distance_m, why=why, source="ai", score=it.score,
                                  reasons=[it.reason, *[r for r in c.reasons if r != it.reason]][:3]))
        else:
            out.append(offer_view(c.offer, c.shop, p.language, distance_m=c.distance_m, why=c.why, source="rules", score=c.rules_score,
                                  reasons=c.reasons))
    return out


async def offer_detail(s: AsyncSession, shopper: Shopper, offer_id: uuid.UUID, lang: str | None) -> dict[str, Any]:
    offer = await s.get(Offer, offer_id)
    shop = await s.get(Shop, offer.shop_id) if offer else None
    if offer is None or shop is None or (shop.is_demo and shopper.area_slug != "demo"):
        raise not_found("That offer")
    p = await load_profile(s, shopper, lang)
    origin = await _origin(s, shopper, None, None)
    d = None
    if origin and shop.lat is not None and shop.lng is not None:
        d = geo.round_distance_m(geo.haversine_m(origin[0], origin[1], shop.lat, shop.lng))
    c = Candidate(offer, shop, d)
    await _attach_expiry(s, [c], clock.now())
    c.rules_score, c.why = rules_score(c, p, clock.now())
    return offer_view(offer, shop, p.language, distance_m=d, why=c.why, source="rules", score=c.rules_score, reasons=c.reasons)


# ── claims ───────────────────────────────────────────────────────────────
def claim_view(claim: Claim, offer: Offer) -> dict[str, Any]:
    return {
        "claim_id": str(claim.id), "offer_id": str(offer.id), "qr_payload": tokens.issue_claim(claim, offer),
        "short_code": claim.short_code, "expires_at": claim.expires_at.isoformat(), "status": claim.status,
    }


async def _unique_short_code(s: AsyncSession, offer_id: uuid.UUID) -> str:
    """6 characters, unique per offer, no look-alike characters."""
    for _ in range(20):
        code = tokens.new_short_code()
        clash = (await s.execute(select(Claim.id).where(Claim.offer_id == offer_id, Claim.short_code == code))).first()
        if clash is None:
            return code
    raise AppError(ErrorCode.internal_error, "Could not make a code. Please try again.", 503, True)


async def create_claim(s: AsyncSession, install_id: uuid.UUID, offer_id: uuid.UUID) -> tuple[Claim, Offer, bool]:
    """One active claim per shopper per offer. Returns (claim, offer, created)."""
    now = clock.now()
    offer = (await s.execute(select(Offer).where(Offer.id == offer_id).with_for_update())).scalar_one_or_none()
    if offer is None:
        raise not_found("That offer")
    existing = (
        await s.execute(
            select(Claim).where(Claim.offer_id == offer_id, Claim.install_id == install_id, Claim.status == "issued", Claim.expires_at > now)
        )
    ).scalars().first()
    if existing is not None:
        return existing, offer, False
    if offer.status == "ended" or offer.ends_at <= now:
        raise AppError(ErrorCode.offer_ended, "This offer has ended.", 409)
    if offer.status == "sold_out" or remaining(offer) <= 0:
        raise AppError(ErrorCode.offer_sold_out, "This offer is sold out.", 409)
    claim = Claim(
        offer_id=offer.id, install_id=install_id, token_jti=tokens.new_jti(), short_code=await _unique_short_code(s, offer.id),
        status="issued", expires_at=min(now + CLAIM_TTL, offer.ends_at), created_at=now,
    )
    s.add(claim)
    offer.claimed_count += 1
    await s.flush()
    await outbox.emit(s, outbox.CLAIM_CREATED, {"claim_id": claim.id, "offer_id": offer.id, "shop_id": offer.shop_id})
    return claim, offer, True


async def claims_for(s: AsyncSession, install_id: uuid.UUID) -> list[dict[str, Any]]:
    now = clock.now()
    rows = (
        await s.execute(
            select(Claim, Offer, Shop, Redemption)
            .join(Offer, Offer.id == Claim.offer_id)
            .join(Shop, Shop.id == Offer.shop_id)
            .outerjoin(Redemption, Redemption.claim_id == Claim.id)
            .where(Claim.install_id == install_id)
            .order_by(Claim.created_at.desc())
        )
    ).all()
    out = []
    for claim, offer, shop, red in rows:
        status = claim.status
        if status == "issued" and (claim.expires_at <= now or offer.status == "ended"):
            status = "expired"
        out.append({
            **claim_view(claim, offer), "status": status, "saved_minor": red.discount_minor if red else 0,
            "offer": offer_view(offer, shop, "en", distance_m=None)["offer"], "shop": {"id": str(shop.id), "name": shop.name},
        })
    return out


async def claim_status(s: AsyncSession, install_id: uuid.UUID, claim_id: uuid.UUID) -> dict[str, Any]:
    claim = await s.get(Claim, claim_id)
    if claim is None or claim.install_id != install_id:
        raise not_found("That claim")
    offer = await s.get(Offer, claim.offer_id)
    red = (await s.execute(select(Redemption).where(Redemption.claim_id == claim.id))).scalar_one_or_none()
    status = claim.status
    if status == "issued" and (claim.expires_at <= clock.now() or (offer is not None and offer.status == "ended")):
        status = "expired"
    return {"claim_id": str(claim.id), "offer_id": str(claim.offer_id), "status": status,
            "saved_minor": red.discount_minor if red else 0, "redeemed_at": red.redeemed_at.isoformat() if red else None}


# ── events, savings, affinity ────────────────────────────────────────────
async def record_event(s: AsyncSession, install_id: uuid.UUID, type_: str, offer_id: uuid.UUID | None, reason: str | None) -> None:
    """Remember what the shopper did. The offer's features are copied into the event, so what we learned survives the
    offer being deleted, and the event expires with the other behaviour data after 30 days."""
    if type_ not in EVENT_TYPES:
        raise AppError(ErrorCode.validation_error, f"Unknown event type. Use one of: {', '.join(EVENT_TYPES)}.", 422)
    data: dict[str, Any] = {"offer_id": str(offer_id) if offer_id else None, "reason": (reason or "")[:120] or None}
    if offer_id is not None:
        offer = await s.get(Offer, offer_id)
        shop = await s.get(Shop, offer.shop_id) if offer else None
        if offer is not None and shop is not None:
            data["f"] = predict.features_of(offer.items or [], category_label(shop.category), str(shop.id)).to_json()
    s.add(ShopperEvent(install_id=install_id, type=type_, data=data, expires_at=clock.now() + BEHAVIOUR_TTL))
    await s.flush()
    _feed_cache.clear()  # what they just did should show in their very next feed


async def savings(s: AsyncSession, install_id: uuid.UUID, period: str) -> dict[str, Any]:
    stmt = select(func.coalesce(func.sum(Redemption.discount_minor), 0), func.count()).where(Redemption.install_id == install_id)
    if period == "month":
        now = clock.now()
        stmt = stmt.where(Redemption.redeemed_at >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    total, count = (await s.execute(stmt)).one()
    cur = (
        await s.execute(
            select(Shop.currency).join(Redemption, Redemption.shop_id == Shop.id).where(Redemption.install_id == install_id)
            .order_by(Redemption.redeemed_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return {"amount_minor": int(total or 0), "currency": cur or "PKR", "count": int(count or 0), "period": period}


async def get_affinity(s: AsyncSession, install_id: uuid.UUID) -> dict[str, Any]:
    """What we have learned about this shopper, live (not a nightly job): categories and items, 0..1, strongest first."""
    pp = (await predict.build_profiles(s, [install_id]))[install_id]
    top = max([v for v in pp.cat.values() if v > 0] + [0.0])
    cats = sorted(({"name": k, "score": round(v / top, 3)} for k, v in pp.cat.items() if v > 0.05 and top > 0), key=lambda x: -x["score"])
    ttop = max([v for v in pp.tok.values() if v > 0] + [0.0])
    items = sorted(
        ({"name": pp.disp.get(k, k), "score": round(v / ttop, 3)} for k, v in pp.tok.items() if v > 0.05 and ttop > 0 and len(k) > 2),
        key=lambda x: -x["score"],
    )
    return {"categories": cats[:5], "interests": items[:6], "updated_at": clock.now().isoformat()}


async def reset_learning(s: AsyncSession, install_id: uuid.UUID) -> None:
    """Reset what we learned: earlier behaviour stops counting. Their own choices (list, categories) stay."""
    await set_prefs(s, install_id, {"learning_reset_at": clock.now().isoformat()})
    await s.execute(delete(ShopperAffinity).where(ShopperAffinity.install_id == install_id))
    _feed_cache.clear()


async def recompute_affinity(s: AsyncSession, install_id: uuid.UUID) -> dict[str, float]:
    """Nightly: keep the stored category scores in step with the live prediction profile (used by data export)."""
    pp = (await predict.build_profiles(s, [install_id]))[install_id]
    await s.execute(delete(ShopperAffinity).where(ShopperAffinity.install_id == install_id))
    if not pp.personalised:
        return {}
    top = max([v for v in pp.cat.values() if v > 0] + [0.0])
    scores = {k: round(v / top, 4) for k, v in pp.cat.items() if v > 0 and top > 0}
    for cat, sc in scores.items():
        s.add(ShopperAffinity(install_id=install_id, category=cat, score=sc, expires_at=clock.now() + BEHAVIOUR_TTL))
    await s.flush()
    return scores


# ── privacy rights ───────────────────────────────────────────────────────
def _row(obj, *fields_: str) -> dict[str, Any]:
    out = {}
    for f in fields_:
        v = getattr(obj, f)
        out[f] = v.isoformat() if isinstance(v, datetime) else (str(v) if isinstance(v, uuid.UUID) else v)
    return out


async def export(s: AsyncSession, shopper: Shopper) -> dict[str, Any]:
    """Everything we hold about this shopper (GDPR access / portability)."""
    iid = shopper.install_id

    async def all_(model, *cols):
        return [_row(r, *cols) for r in (await s.execute(select(model).where(model.install_id == iid))).scalars().all()]

    return {
        "generated_at": clock.now().isoformat(),
        "shopper": _row(shopper, "install_id", "platform", "languages", "geohash6", "area_slug", "created_at", "last_seen_at"),
        "consents": await all_(Consent, "purpose", "granted_at", "withdrawn_at", "policy_version"),
        "preferences": await get_prefs(s, iid),
        "shopping_list": await get_list(s, iid),
        "events": await all_(ShopperEvent, "type", "data", "created_at", "expires_at"),
        "notifications": await all_(Notification, "offer_id", "title", "body", "why", "created_at"),
        "affinity": await all_(ShopperAffinity, "category", "score"),
        "push_tokens": [{"kind": r["kind"]} for r in await all_(ShopperPushToken, "kind")],
        "claims": await all_(Claim, "offer_id", "short_code", "status", "created_at", "expires_at"),
        "redemptions": await all_(Redemption, "offer_id", "discount_minor", "redeemed_at"),
    }


async def delete_shopper(s: AsyncSession, install_id: uuid.UUID) -> dict[str, int]:
    """Hard-delete every shopper row. Redemptions and claims stay for billing, with install_id set to null."""
    counts: dict[str, int] = {}
    for model in (Consent, ShopperPreference, ShoppingList, ShopperPushToken, Notification, ShopperEvent, ShopperAffinity):
        res = await s.execute(delete(model).where(model.install_id == install_id))
        counts[model.__tablename__] = res.rowcount or 0
    counts["redemptions_anonymised"] = (await s.execute(update(Redemption).where(Redemption.install_id == install_id).values(install_id=None))).rowcount or 0
    counts["claims_anonymised"] = (await s.execute(update(Claim).where(Claim.install_id == install_id).values(install_id=None))).rowcount or 0
    await s.execute(delete(Shopper).where(Shopper.install_id == install_id))
    return counts


async def retention_sweep(s: AsyncSession) -> dict[str, int]:
    """Nightly: behaviour data older than 30 days, expired lists, installs not seen in 180 days."""
    now = clock.now()
    out = {
        "events": (await s.execute(delete(ShopperEvent).where(ShopperEvent.created_at < now - BEHAVIOUR_TTL))).rowcount or 0,
        "notifications": (await s.execute(delete(Notification).where(Notification.created_at < now - BEHAVIOUR_TTL))).rowcount or 0,
        "lists": (await s.execute(delete(ShoppingList).where(ShoppingList.expires_at.is_not(None), ShoppingList.expires_at <= now))).rowcount or 0,
        "affinity": (await s.execute(delete(ShopperAffinity).where(ShopperAffinity.expires_at.is_not(None), ShopperAffinity.expires_at <= now))).rowcount or 0,
    }
    stale = (
        await s.execute(
            select(Shopper.install_id).where(
                Shopper.is_simulated.is_(False),
                func.coalesce(Shopper.last_seen_at, Shopper.created_at) < now - timedelta(days=180),
            )
        )
    ).scalars().all()
    for iid in stale:
        await delete_shopper(s, iid)
    out["installs"] = len(stale)
    return out


# ── quiet hours / daily limit (used by matching) ─────────────────────────
def in_quiet_hours(prefs: dict[str, Any], tz: str, now: datetime) -> bool:
    try:
        local = now.astimezone(ZoneInfo(tz))
    except Exception:  # noqa: BLE001
        local = now
    start, end = str(prefs.get("quiet_start") or "21:00"), str(prefs.get("quiet_end") or "08:00")
    cur = local.strftime("%H:%M")
    if start == end:
        return False
    return (start <= cur or cur < end) if start > end else (start <= cur < end)


def local_midnight_utc(tz: str, now: datetime) -> datetime:
    try:
        zone = ZoneInfo(tz)
    except Exception:  # noqa: BLE001
        zone = ZoneInfo("UTC")
    local = now.astimezone(zone)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(now.tzinfo)
