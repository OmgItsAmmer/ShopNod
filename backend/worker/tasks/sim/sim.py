"""Simulated shoppers (Plan 3 Phase 2): one judge alone can watch the full loop.

- `seed_shoppers` creates fake shoppers in the Demo Market, all opted in, flagged `is_simulated`. They never get
  real pushes, but they do count toward the "at least 10 people" minimum.
- When a demo shop publishes an offer (and `sim_enabled` is on), each fake shopper claims it with a chance based on
  its match score, then redeems 30–120 s later through `shopnod_core.redeem(..., is_simulated=True)`.
  Simulated redemptions are billable, so Stripe test mode shows real numbers.
- `burst` creates 5 redemptions in 20 s for one shop (the admin page's "burst" button).
"""
from __future__ import annotations

import logging
import random
import uuid
from typing import Any

from sqlalchemy import func, select

from shopnod_core import clock, dispatch, flags, geo, redeem, templates
from shopnod_core import shopper as sh
from shopnod_core.db import session_scope
from shopnod_core.models import (
    Claim,
    Consent,
    MarketArea,
    Offer,
    Shop,
    Shopper,
    ShopperPreference,
    ShoppingList,
)
from shopnod_core.settings import get_settings

log = logging.getLogger("shopnod.sim")
LIST_WORDS = [
    "Bread", "Croissant", "Cake", "Cookies", "Milk", "Eggs", "Rice", "Cooking oil", "Tea", "Coffee", "Samosa",
    "Bananas", "Apples", "Tomatoes", "Onions", "Mangoes", "Soap", "Biscuits", "Yogurt", "Sourdough",
]
CATEGORIES = ["Bakery", "Groceries", "Fruit & veg", "Café", "Household"]
DIETARY = ["Halal", "Vegetarian", "Vegan", "Gluten-free"]
BURST_SIZE = 5
CLAIM_FACTOR = 0.5  # chance to claim = match score × this
rng = random.Random()


async def seed_shoppers(n: int | None = None, market: str = "demo") -> int:
    """Create fake shoppers until the market has `n` of them. Idempotent. Returns how many were created."""
    n = n if n is not None else get_settings().SIM_SHOPPERS
    now = clock.now()
    async with session_scope() as s:
        area = (await s.execute(select(MarketArea).where(MarketArea.slug == market))).scalar_one_or_none()
        if area is None:
            area = await templates.ensure_demo_market(s)
        have = (await s.execute(select(func.count()).select_from(Shopper).where(Shopper.is_simulated.is_(True), Shopper.area_slug == market))).scalar_one()
        created = 0
        for i in range(int(have), n):
            r = random.Random(i)  # the same fake shoppers every time
            iid = uuid.uuid4()
            s.add(Shopper(install_id=iid, is_simulated=True, geohash6=geo.encode(area.center_lat, area.center_lng, 6), area_slug=market,
                          languages=["en"], platform="sim", last_seen_at=now, created_at=now))
            for purpose in sh.PURPOSES:
                s.add(Consent(install_id=iid, purpose=purpose, granted_at=now, policy_version=sh.POLICY_VERSION))
            s.add(ShopperPreference(install_id=iid, updated_at=now, data={
                **sh.DEFAULT_PREFS, "categories": r.sample(CATEGORIES, k=r.randint(1, 3)),
                "dietary": r.sample(DIETARY, k=r.randint(0, 1)), "daily_limit": 10, "quiet_start": "00:00", "quiet_end": "00:00",
            }))
            s.add(ShoppingList(install_id=iid, items=r.sample(LIST_WORDS, k=r.randint(2, 5)), expires_at=now + sh.BEHAVIOUR_TTL * 12))
            created += 1
    return created


async def _sim_shoppers(s, market: str = "demo") -> list[Shopper]:
    return list((await s.execute(select(Shopper).where(Shopper.is_simulated.is_(True), Shopper.area_slug == market))).scalars().all())


def _redeem_delay() -> float:
    st = get_settings()
    lo, hi = st.SIM_REDEEM_MIN_S, max(st.SIM_REDEEM_MAX_S, st.SIM_REDEEM_MIN_S)
    return lo if hi <= lo else rng.uniform(lo, hi)


async def react(offer_id: uuid.UUID) -> dict[str, int]:
    """Fake shoppers claim a new demo offer with a chance based on their match score, then redeem later."""
    if not await flags.get_flag(flags.SIM_ENABLED):
        return {"claimed": 0}
    now = clock.now()
    picks: list[uuid.UUID] = []
    async with session_scope() as s:
        offer = await s.get(Offer, offer_id)
        shop = await s.get(Shop, offer.shop_id) if offer else None
        if offer is None or shop is None or not shop.is_demo or offer.status != "active":
            return {"claimed": 0}
        sims = await _sim_shoppers(s)
    if not sims:
        await seed_shoppers()
        async with session_scope() as s:
            sims = await _sim_shoppers(s)
    for x in sims:
        async with session_scope() as s:
            offer = await s.get(Offer, offer_id)
            shop = await s.get(Shop, offer.shop_id)
            if offer.status != "active" or sh.remaining(offer) <= 0:
                break
            prof = await sh.load_profile(s, x)
            c = sh.Candidate(offer, shop, None)
            score, _ = sh.rules_score(c, prof, now)
            if rng.random() >= score * CLAIM_FACTOR:
                continue
            try:
                claim, _, created = await sh.create_claim(s, x.install_id, offer.id)
            except Exception:  # noqa: BLE001 - sold out / ended while we were looping
                break
            if created:
                picks.append(claim.id)
    for cid in picks:
        dispatch.enqueue_in(_redeem_delay(), "sim.redeem", str(cid))
    log.info("simulated shoppers reacted", extra={"offer_id": str(offer_id), "claimed": len(picks)})
    return {"claimed": len(picks)}


async def redeem_claim(claim_id: uuid.UUID) -> dict[str, Any]:
    """Redeem a simulated claim at its shop, exactly as the counter would (QR text through `redeem`)."""
    from shopnod_core import tokens

    async with session_scope() as s:
        claim = await s.get(Claim, claim_id)
        offer = await s.get(Offer, claim.offer_id) if claim else None
        if claim is None or offer is None or claim.status != "issued":
            return {"result": "skipped"}
        payload = tokens.issue_claim(claim, offer)
        shop_id = offer.shop_id
    return await redeem.redeem(shop_id, payload=payload, idempotency_key=f"sim:{claim_id}", is_simulated=True)


async def burst(shop_id: uuid.UUID | None) -> dict[str, int]:
    """5 simulated redemptions in about 20 s on the shop's newest active offer."""
    async with session_scope() as s:
        stmt = select(Offer).join(Shop, Shop.id == Offer.shop_id).where(Offer.status == "active", Shop.is_demo.is_(True))
        if shop_id is not None:
            stmt = stmt.where(Offer.shop_id == shop_id)
        offer = (await s.execute(stmt.order_by(Offer.created_at.desc()))).scalars().first()
        if offer is None:
            return {"queued": 0}
        sims = await _sim_shoppers(s)
    if len(sims) < BURST_SIZE:
        await seed_shoppers()
        async with session_scope() as s:
            sims = await _sim_shoppers(s)
    queued = 0
    for x in rng.sample(sims, k=len(sims)):  # shuffled
        if queued >= BURST_SIZE:
            break
        async with session_scope() as s:
            try:
                claim, _, created = await sh.create_claim(s, x.install_id, offer.id)
            except Exception:  # noqa: BLE001
                break
        if not created:
            continue
        dispatch.enqueue_in(queued * (get_settings().SIM_BURST_SPAN_S / BURST_SIZE), "sim.redeem", str(claim.id))
        queued += 1
    return {"queued": queued}
