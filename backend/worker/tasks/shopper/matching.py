"""Match a newly published offer to nearby shoppers and notify the right ones (Plan 1 Phase 5).

Who can be notified: shoppers in the offer's cell + the 8 around it who gave the `notifications` consent, were seen
in the last 7 days, haven't muted the shop or category, are under their daily limit, are outside their quiet hours
and weren't already notified about this offer. They are ranked in batches of 20 in parallel.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from shopnod_core import ai, clock, context, flags, geo, outbox, predict, sse
from shopnod_core import shopper as sh
from shopnod_core.db import session_scope
from shopnod_core.models import (
    Consent,
    Notification,
    Offer,
    OfferReachStat,
    Shop,
    Shopper,
    ShopperPreference,
    ShopperPushToken,
)
from shopnod_core.settings import get_settings

log = logging.getLogger("shopnod.matching")
BATCH = 20
SEEN_WITHIN = timedelta(days=7)
SHOPPER_PUSH = "shopper.push"


class NotifyItem(BaseModel):
    ref: int
    score: float = Field(ge=0, le=1)


class NotifyOut(BaseModel):
    items: list[NotifyItem]


def _push_text(offer: Offer, shop: Shop, distance_m: int | None) -> tuple[str, str]:
    names = [str(i.get("name", "")) for i in offer.items or [] if i.get("name")]
    what = names[0].lower() if names else "your shopping"
    where = f" · {sh.distance_label(distance_m)}" if distance_m is not None else ""
    return shop.name, f"{offer.pct}% on {what} at {shop.name}{where}"


async def _score_batch(batch: list[tuple[Shopper, sh.Profile, sh.Candidate]], use_ai: bool) -> list[tuple[float, str]]:
    """(score, source) per shopper. AI when configured, rules otherwise (and on any AI problem)."""
    if not use_ai:
        return [(c.rules_score, "rules") for _, _, c in batch]
    settings = get_settings()
    now = clock.now()
    c0 = batch[0][2]
    payload = {
        "offer": json.loads(sh.matching_prompt([c0], batch[0][1], now))["offers"][0],
        "shoppers": [
            {"ref": i, "shopping_list": p.list_items, "categories": p.categories, "dietary": p.dietary,
             "distance_band": sh._distance_band(c.distance_m)}
            for i, (_, p, c) in enumerate(batch)
        ],
    }

    async def runner(trace: ai.RunTrace):
        from shopnod_core.agents.openai_runner import run_openai_agent

        return await run_openai_agent(
            trace, name="Matching Agent (notify)",
            instructions="Score from 0 to 1 how much each shopper (by ref) would want this offer right now. Use only the facts given.",
            user_input=json.dumps(payload, ensure_ascii=False), output_type=NotifyOut, model=settings.OPENAI_MODEL_FAST,
        )

    def fallback() -> NotifyOut:
        return NotifyOut(items=[NotifyItem(ref=i, score=min(max(c.rules_score, 0), 1)) for i, (_, _, c) in enumerate(batch)])

    res = await ai.run_structured("matching", f"notify batch of {len(batch)}", NotifyOut, runner=runner, fallback=fallback, timeout_s=4.0)
    by_ref = {it.ref: it.score for it in res.output.items}
    src = "rules" if res.fallback_used else "ai"
    return [(by_ref.get(i, c.rules_score), src) for i, (_, _, c) in enumerate(batch)]


async def match_and_notify(offer_id: uuid.UUID) -> dict[str, int]:
    now = clock.now()
    async with session_scope() as s:
        offer = await s.get(Offer, offer_id)
        shop = await s.get(Shop, offer.shop_id) if offer else None
        if offer is None or shop is None or offer.status != "active" or not offer.geohash6:
            return {"reach": 0, "notified": 0}
        cells = geo.neighbours(offer.geohash6)
        stmt = select(Shopper).where(Shopper.geohash6.in_(cells))
        if shop.is_demo:
            stmt = stmt.where(Shopper.area_slug == "demo")
        area = (await s.execute(stmt)).scalars().all()
        ids = [x.install_id for x in area]
        if not ids:
            await _save_reach(s, offer.id, 0)
            return {"reach": 0, "notified": 0}
        consents: dict[uuid.UUID, set[str]] = {}
        for iid, purpose in (await s.execute(select(Consent.install_id, Consent.purpose).where(Consent.install_id.in_(ids), Consent.withdrawn_at.is_(None)))).all():
            consents.setdefault(iid, set()).add(purpose)
        prefs = {r.install_id: {**sh.DEFAULT_PREFS, **(r.data or {})} for r in (await s.execute(select(ShopperPreference).where(ShopperPreference.install_id.in_(ids)))).scalars()}
        pps = await predict.build_profiles(s, ids, now)  # what each of them probably wants, from their own data
        market = await predict.get_market(s, now)
        expires_in_h = await _expires_in_h(s, offer, now)
        already = set((await s.execute(select(Notification.install_id).where(Notification.offer_id == offer.id))).scalars().all())
        since = sh.local_midnight_utc(shop.timezone, now)
        today = dict((await s.execute(
            select(Notification.install_id, func.count()).where(Notification.install_id.in_(ids), Notification.created_at >= since).group_by(Notification.install_id)
        )).all())
        tokens: set[uuid.UUID] = set((await s.execute(select(ShopperPushToken.install_id).where(ShopperPushToken.install_id.in_(ids)))).scalars().all())
        label = sh.category_label(shop.category)
        eligible: list[tuple[Shopper, sh.Profile, sh.Candidate]] = []
        for x in area:
            granted = consents.get(x.install_id, set())
            p = prefs.get(x.install_id, dict(sh.DEFAULT_PREFS))
            if "notifications" not in granted or x.install_id in already:
                continue
            if not x.last_seen_at or now - x.last_seen_at > SEEN_WITHIN:
                continue
            if str(shop.id) in {str(m) for m in p.get("muted_shops") or []} or label in set(p.get("muted_categories") or []):
                continue
            if today.get(x.install_id, 0) >= int(p.get("daily_limit") or 3):
                continue
            if sh.in_quiet_hours(p, shop.timezone, now):
                continue
            pp = pps[x.install_id]
            prof = sh.Profile(
                list_items=list(dict.fromkeys(pp.list_toks.values())) if pp.personalised else [],
                categories=list(p.get("categories") or []), dietary=list(p.get("dietary") or []),
                affinity={k: v for k, v in pp.cat.items() if v > 0},
                language=(p.get("languages") or x.languages or ["en"])[0], personalised=pp.personalised,
                max_distance_m=int(p.get("max_distance_m") or 800),
                pp=pp, ctx=await context.resolve(p, x.geohash6), market=market if pp.personalised else None,
            )
            origin = await sh._origin(s, x, None, None)
            d = None
            if origin and shop.lat is not None and shop.lng is not None:
                d = geo.round_distance_m(geo.haversine_m(origin[0], origin[1], shop.lat, shop.lng))
            if x.area_slug is None and d is not None and d > prof.max_distance_m:
                continue
            c = sh.Candidate(offer, shop, d, expires_in_h=expires_in_h)
            c.rules_score, c.why = sh.rules_score(c, prof, now)
            eligible.append((x, prof, c))
        reach = len(area)

    use_ai = bool(get_settings().OPENAI_API_KEY) and not await flags.get_flag(flags.AI_OUTAGE)
    batches = [eligible[i:i + BATCH] for i in range(0, len(eligible), BATCH)]
    scored = await asyncio.gather(*(_score_batch(b, use_ai) for b in batches))

    picked: list[tuple[Shopper, sh.Candidate]] = []
    for batch, scores in zip(batches, scored, strict=True):
        for (x, _, c), (score, src) in zip(batch, scores, strict=True):
            if score >= (NOTIFY_THRESHOLD(src)):
                picked.append((x, c))

    sent_sse: list[tuple[uuid.UUID, dict[str, Any]]] = []
    async with session_scope() as s:
        offer = await s.get(Offer, offer_id)
        shop = await s.get(Shop, offer.shop_id)
        for x, c in picked:
            exists = (await s.execute(select(Notification.id).where(Notification.install_id == x.install_id, Notification.offer_id == offer.id))).first()
            if exists:
                continue  # safe to run twice
            title, body = _push_text(offer, shop, c.distance_m)
            s.add(Notification(install_id=x.install_id, offer_id=offer.id, title=title, body=body, why=c.why, created_at=now, expires_at=now + sh.BEHAVIOUR_TTL))
            if not x.is_simulated and x.install_id in tokens:
                await outbox.emit(s, SHOPPER_PUSH, {"install_id": x.install_id, "offer_id": offer.id, "title": title, "body": body})
            if not x.is_simulated:
                sent_sse.append((x.install_id, {"offer_id": str(offer.id), "title": title, "body": body, "why": c.why}))
        await s.flush()
        notified = await _save_reach(s, offer.id, reach)
    for iid, data in sent_sse:
        await sse.publish(sse.shopper_channel(iid), "offer.matched", data)
    log.info("matched offer", extra={"offer_id": str(offer_id), "reach": reach, "notified": notified})
    return {"reach": reach, "notified": notified}


def NOTIFY_THRESHOLD(source: str) -> float:  # noqa: N802 - reads like the constant it wraps
    return sh.NOTIFY_THRESHOLD_AI if source == "ai" else sh.NOTIFY_THRESHOLD_RULES


async def _save_reach(s, offer_id: uuid.UUID, reach: int) -> int:
    notified = (await s.execute(select(func.count()).select_from(Notification).where(Notification.offer_id == offer_id))).scalar_one()
    row = await s.get(OfferReachStat, offer_id)
    if row is None:
        try:
            async with s.begin_nested():  # another worker may create it at the same moment
                s.add(OfferReachStat(offer_id=offer_id, reach=reach, notified=notified, updated_at=clock.now()))
            return int(notified)
        except IntegrityError:
            row = await s.get(OfferReachStat, offer_id, populate_existing=True)
    row.reach, row.notified, row.updated_at = max(row.reach, reach), max(row.notified, notified), clock.now()
    await s.flush()
    return int(notified)


async def _expires_in_h(s, offer: Offer, now) -> float | None:
    """Hours until the soonest-expiring item in the offer (stock that must go today is worth sending to people)."""
    c = sh.Candidate(offer, None, None)  # type: ignore[arg-type]
    await sh._attach_expiry(s, [c], now)
    return c.expires_in_h
