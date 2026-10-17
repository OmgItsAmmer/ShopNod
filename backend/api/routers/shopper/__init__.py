"""Shopper app API (Plan 1): `/v1/shopper/*`. Every route except `POST /installs` needs the install token."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_core import auth, clock, context, idempotency, sse
from shopnod_core import shopper as sh
from shopnod_core.db import DB, session_scope
from shopnod_core.errors import AppError, ErrorCode, unauthorized
from shopnod_core.models import Shopper, ShopperPushToken
from shopnod_core.redis_util import rate_limit
from shopnod_core.settings import get_settings

router = APIRouter()
INSTALLS_PER_MINUTE = 30


# ── schemas ──────────────────────────────────────────────────────────────
class InstallIn(BaseModel):
    platform: str = Field(default="web", max_length=16)
    languages: list[str] = Field(default_factory=lambda: ["en"], max_length=10)
    age_confirmed: bool = False


class InstallOut(BaseModel):
    install_id: uuid.UUID
    install_token: str


class ConsentsIn(BaseModel):
    location: bool | None = None
    notifications: bool | None = None
    list: bool | None = None
    personalisation: bool | None = None
    analytics: bool | None = None
    policy_version: str = Field(default=sh.POLICY_VERSION, max_length=16)


class ConsentsOut(BaseModel):
    location: bool
    notifications: bool
    list: bool
    personalisation: bool
    analytics: bool
    policy_version: str = sh.POLICY_VERSION


class PreferencesIn(BaseModel):
    categories: list[str] | None = Field(default=None, max_length=30)
    dietary: list[str] | None = Field(default=None, max_length=10)
    languages: list[str] | None = Field(default=None, max_length=10)
    max_distance_m: int | None = Field(default=None, ge=100, le=20000)
    daily_limit: int | None = Field(default=None, ge=0, le=20)
    quiet_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quiet_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    muted_shops: list[str] | None = Field(default=None, max_length=200)
    muted_categories: list[str] | None = Field(default=None, max_length=50)


class LocationIn(BaseModel):
    lat: float | None = None
    lng: float | None = None
    market: str | None = Field(default=None, max_length=64)


class LocationOut(BaseModel):
    geohash6: str
    market_name: str | None = None


class FeedOffer(BaseModel):
    id: str
    shop_id: str
    title: str
    description: str
    category: str
    discount_pct: int
    was_price: int
    now_price: int
    currency: str
    starts_at: str
    ends_at: str
    remaining: int
    status: str
    copy_source: str
    tags: list[str]
    items: list[dict[str, Any]]


class FeedShop(BaseModel):
    id: str
    name: str
    category: str


class FeedItem(BaseModel):
    offer: FeedOffer
    shop: FeedShop
    distance_m: int | None
    score: float | None
    why: str
    reasons: list[str] = Field(default_factory=list)  # up to 3, strongest first: why this offer is shown to you
    source: Literal["ai", "rules"]
    copy_source: str


class ClaimOut(BaseModel):
    claim_id: str
    offer_id: str
    qr_payload: str
    short_code: str
    expires_at: str
    status: str


class ClaimListItem(ClaimOut):
    saved_minor: int
    offer: FeedOffer
    shop: dict[str, str]


class ClaimStatusOut(BaseModel):
    claim_id: str
    offer_id: str
    status: str
    saved_minor: int
    redeemed_at: str | None


class ListIn(BaseModel):
    items: list[str] = Field(default_factory=list, max_length=50)


class ListOut(BaseModel):
    items: list[str]
    expires_at: datetime | None = None


class EventIn(BaseModel):
    type: str = Field(max_length=20)
    offer_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=120)


class SavingsOut(BaseModel):
    amount_minor: int
    currency: str
    count: int
    period: str


class AffinityOut(BaseModel):
    categories: list[dict[str, Any]]
    interests: list[dict[str, Any]] = Field(default_factory=list)  # items, e.g. "pastry", 0..1
    updated_at: str


class ContextOut(BaseModel):
    """What the app knows about the moment: shown as 'Rainy evening · 24°C' above the feed."""

    weather: str  # rain|hot|cold|clear|unknown
    temp_c: float | None
    daypart: str  # morning|midday|evening|night
    summary: str
    demo_mode: bool  # the "pretend it's…" switch is available
    pretend: dict[str, str | None]  # what this shopper is pretending, if anything


class DemoContextIn(BaseModel):
    weather: Literal["rain", "hot", "cold", "clear"] | None = None
    daypart: Literal["morning", "midday", "evening", "night"] | None = None


class PushTokenIn(BaseModel):
    kind: Literal["fcm", "webpush"]
    token: str | None = Field(default=None, max_length=4096)
    subscription: dict[str, Any] | None = None


class TicketOut(BaseModel):
    ticket: str
    expires_in_s: int


class OkOut(BaseModel):
    ok: bool = True


# ── install ──────────────────────────────────────────────────────────────
@router.post("/installs", response_model=InstallOut, status_code=201)
async def create_install(body: InstallIn, request: Request, db: AsyncSession = DB):
    """No account: a random install id and a 180-day token. Shoppers must confirm they are 18 or older."""
    ip = request.client.host if request.client else "unknown"
    if not await rate_limit(f"installs:{ip}", INSTALLS_PER_MINUTE, 60):
        raise AppError(ErrorCode.rate_limited, "Too many new installs from here. Please wait a minute.", 429, True)
    if not body.age_confirmed:
        raise AppError(ErrorCode.age_required, "ShopNod is for people aged 18 or older.", 422)
    row = Shopper(languages=[x[:8] for x in body.languages] or ["en"], platform=body.platform, last_seen_at=clock.now(), created_at=clock.now())
    db.add(row)
    await db.flush()
    return InstallOut(install_id=row.install_id, install_token=auth.create_install_token(row.install_id))


# ── consents, preferences, location ──────────────────────────────────────
@router.get("/consents", response_model=ConsentsOut)
async def get_consents(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    return ConsentsOut(**await sh.current_consents(db, me.install_id))


@router.put("/consents", response_model=ConsentsOut)
async def put_consents(body: ConsentsIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    wanted = {k: v for k, v in body.model_dump().items() if k in sh.PURPOSES and v is not None}
    return ConsentsOut(**await sh.set_consents(db, me.install_id, wanted, body.policy_version), policy_version=body.policy_version)


@router.get("/preferences")
async def get_preferences(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB) -> dict[str, Any]:
    return await sh.get_prefs(db, me.install_id)


@router.put("/preferences")
async def put_preferences(body: PreferencesIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB) -> dict[str, Any]:
    out = await sh.set_prefs(db, me.install_id, body.model_dump(exclude_none=True))
    sh.clear_feed_cache()
    return out


@router.post("/location", response_model=LocationOut)
async def post_location(body: LocationIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """Saves only the last area (geohash6) and the time. Never raw coordinates or a history."""
    row = await db.get(Shopper, me.install_id)
    gh, name = await sh.set_location(db, row, body.lat, body.lng, body.market)
    return LocationOut(geohash6=gh, market_name=name)


# ── feed & offers ────────────────────────────────────────────────────────
@router.get("/feed", response_model=list[FeedItem])
async def get_feed(
    lang: str | None = Query(default=None, max_length=8),
    lat: float | None = Query(default=None, ge=-90, le=90, description="optional, only for distance; never stored"),
    lng: float | None = Query(default=None, ge=-180, le=180),
    me: Shopper = Depends(auth.shopper),
    db: AsyncSession = DB,
):
    """Top 10 offers near you, ranked for you, each with 'why you see this'."""
    return await sh.feed(db, me, lang=lang, lat=lat, lng=lng)


@router.get("/offers/{offer_id}", response_model=FeedItem)
async def get_offer(offer_id: uuid.UUID, lang: str | None = Query(default=None, max_length=8), me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    return await sh.offer_detail(db, me, offer_id, lang)


@router.post("/offers/{offer_id}/claim", response_model=ClaimOut)
async def claim_offer(offer_id: uuid.UUID, me: Shopper = Depends(auth.shopper), key: str = Depends(idempotency.require_key)):
    """One active claim per shopper per offer. The same Idempotency-Key returns the same claim."""

    async def run() -> tuple[int, dict[str, Any]]:
        async with session_scope() as s:
            claim, offer, _ = await sh.create_claim(s, me.install_id, offer_id)
            return 200, sh.claim_view(claim, offer)

    status, body = await idempotency.run_idempotent(f"claim:{me.install_id}", key, run)
    return JSONResponse(body, status_code=status)


@router.get("/claims", response_model=list[ClaimListItem])
async def list_claims(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    return await sh.claims_for(db, me.install_id)


@router.get("/claims/{claim_id}", response_model=ClaimStatusOut)
async def get_claim(claim_id: uuid.UUID, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """Poll fallback for the live 'Redeemed' event."""
    return await sh.claim_status(db, me.install_id, claim_id)


# ── list, events, savings, affinity ──────────────────────────────────────
@router.get("/list", response_model=ListOut)
async def get_list(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    if not await sh.has_consent(db, me.install_id, "list"):
        raise AppError(ErrorCode.consent_required, "Turn on 'Use my shopping list' to save a list.", 409)
    return ListOut(items=await sh.get_list(db, me.install_id))


@router.put("/list", response_model=ListOut)
async def put_list(body: ListIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """Deleted after 30 days."""
    items, expires = await sh.set_list(db, me.install_id, body.items)
    sh.clear_feed_cache()
    return ListOut(items=items, expires_at=expires)


@router.post("/events", response_model=OkOut, status_code=201)
async def post_event(body: EventIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """open / dismiss / save / why_up / why_down. Kept 30 days."""
    await sh.record_event(db, me.install_id, body.type, body.offer_id, body.reason)
    return OkOut()


@router.get("/savings", response_model=SavingsOut)
async def get_savings(period: Literal["month", "all"] = "month", me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    return await sh.savings(db, me.install_id, period)


@router.get("/affinity", response_model=AffinityOut)
async def get_affinity(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """What the app learned about you (category interest)."""
    return await sh.get_affinity(db, me.install_id)


@router.delete("/affinity", response_model=OkOut)
async def reset_affinity(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """Forget what we learned from your activity. Your own choices (list, categories) stay."""
    await sh.reset_learning(db, me.install_id)
    return OkOut()


async def _context_out(db: AsyncSession, me: Shopper) -> ContextOut:
    prefs = await sh.get_prefs(db, me.install_id)
    ctx = await context.resolve(prefs, me.geohash6)
    _, part, _, _ = ctx.local(clock.now(), "Asia/Karachi")  # the market's clock; see Context.local
    ov = context.demo_override(prefs)
    return ContextOut(
        weather=ctx.weather, temp_c=ctx.temp_c, daypart=part, summary=ctx.summary(clock.now(), "Asia/Karachi"),
        demo_mode=get_settings().DEMO_MODE, pretend=ov,
    )


@router.get("/context", response_model=ContextOut)
async def get_context(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """The time of day and weather for your area (no permission needed): they shape what we show first."""
    return await _context_out(db, me)


@router.put("/demo-context", response_model=ContextOut)
async def set_demo_context(body: DemoContextIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """Demo only: pretend it is a different time of day or weather, for this shopper only."""
    if not get_settings().DEMO_MODE:
        raise AppError(ErrorCode.demo_only, "This is only available in the demo.", 403)
    await sh.set_prefs(db, me.install_id, {"demo_ctx": {"weather": body.weather, "daypart": body.daypart}})
    sh.clear_feed_cache()
    return await _context_out(db, me)


# ── push & live updates ──────────────────────────────────────────────────
def _push_value(body: PushTokenIn) -> str:
    if body.kind == "webpush":
        sub = body.subscription or {}
        if not sub.get("endpoint") or not (sub.get("keys") or {}).get("p256dh"):
            raise AppError(ErrorCode.validation_error, "Send the browser's push subscription.", 422)
        return json.dumps({"endpoint": sub["endpoint"], "keys": sub["keys"]}, sort_keys=True)
    if not body.token:
        raise AppError(ErrorCode.validation_error, "Send the device token.", 422)
    return body.token


@router.post("/push-tokens", response_model=OkOut, status_code=201)
async def add_push_token(body: PushTokenIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """Only allowed with the `notifications` consent."""
    if not await sh.has_consent(db, me.install_id, "notifications"):
        raise AppError(ErrorCode.consent_required, "Turn on notifications first.", 409)
    value = _push_value(body)
    exists = (await db.execute(select(ShopperPushToken.id).where(ShopperPushToken.install_id == me.install_id, ShopperPushToken.token == value))).first()
    if exists is None:
        db.add(ShopperPushToken(install_id=me.install_id, kind=body.kind, token=value))
    return OkOut()


@router.delete("/push-tokens", response_model=OkOut)
async def remove_push_token(body: PushTokenIn, me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    await db.execute(delete(ShopperPushToken).where(ShopperPushToken.install_id == me.install_id, ShopperPushToken.token == _push_value(body)))
    return OkOut()


@router.post("/stream-ticket", response_model=TicketOut)
async def stream_ticket(me: Shopper = Depends(auth.shopper)):
    """`EventSource` can't send headers, so open the stream with this short-lived ticket."""
    return TicketOut(ticket=auth.create_stream_ticket(me.install_id), expires_in_s=int(auth.STREAM_TICKET_TTL.total_seconds()))


@router.get("/stream")
async def stream(ticket: str = Query(..., max_length=2000)):
    """Live updates: offer.matched, claim.redeemed, offer.ended. Heartbeat every 15 s."""
    install_id = auth.decode_stream_ticket(ticket)
    if install_id is None:
        raise unauthorized("That stream ticket has expired. Ask for a new one.")
    return StreamingResponse(
        sse.event_stream(sse.shopper_channel(install_id)), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── privacy rights ───────────────────────────────────────────────────────
@router.get("/me/export")
async def export_me(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB) -> dict[str, Any]:
    """Everything we hold about you, as JSON."""
    return await sh.export(db, await db.get(Shopper, me.install_id))


@router.delete("/me", response_model=OkOut)
async def delete_me(me: Shopper = Depends(auth.shopper), db: AsyncSession = DB):
    """Deletes everything about you. Redemptions stay for the shop's billing, without your install id."""
    await sh.delete_shopper(db, me.install_id)
    sh.clear_feed_cache()
    return OkOut()
