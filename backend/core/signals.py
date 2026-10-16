"""Signals that wake the Shop Agent: the "I'm quiet" button, quiet-hour detection and the expiry sweep."""
from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock, dispatch
from .db import session_scope
from .guardrails import local_hour, local_weekday_key, parse_hhmm
from .models import Item, Offer, Proposal, Redemption, Shop, Signal

QUIET_THRESHOLD = 0.6  # below 60% of the usual number of redemptions
BASELINE_WEEKS = 4
EXPIRY_HORIZON = timedelta(hours=24)
EXPIRY_COOLDOWN = timedelta(hours=3)
QUIET_COOLDOWN = timedelta(minutes=60)


async def create_signal(
    session: AsyncSession, shop: Shop, type_: str, *, window: dict | None = None,
    baseline: float | None = None, observed: float | None = None, now: datetime | None = None,
) -> Signal:
    sig = Signal(shop_id=shop.id, type=type_, window=window or {}, baseline=baseline, observed=observed, created_at=now or clock.now())
    session.add(sig)
    await session.flush()
    return sig


def trigger_agent(shop_id: uuid.UUID, signal_id: uuid.UUID) -> None:
    dispatch.enqueue("shop.run_shop_agent", str(shop_id), str(signal_id))


def is_open(shop: Shop, now: datetime) -> bool:
    """Open per the shop's hours (no hours set = treated as open)."""
    if not shop.hours:
        return True
    rng = shop.hours.get(local_weekday_key(now, shop.timezone))
    if not rng:
        return False
    try:
        lo, hi = parse_hhmm(rng[0]), parse_hhmm(rng[1])
    except Exception:  # noqa: BLE001
        return True
    local = now.astimezone(_tz(shop.timezone))
    m = local.hour * 60 + local.minute
    return lo <= m < hi


def _tz(name: str):
    from zoneinfo import ZoneInfo

    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def grid_says_quiet(shop: Shop, now: datetime) -> bool:
    day = (shop.quiet_grid or {}).get(local_weekday_key(now, shop.timezone))
    if not day:
        return False
    h = local_hour(now, shop.timezone)
    return h < len(day) and day[h] == "quiet"


async def _count_redemptions(session: AsyncSession, shop_id: uuid.UUID, start: datetime, end: datetime) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(Redemption).where(
                    Redemption.shop_id == shop_id, Redemption.redeemed_at >= start, Redemption.redeemed_at < end
                )
            )
        ).scalar_one()
    )


async def activity_stats(session: AsyncSession, shop: Shop, now: datetime) -> dict[str, Any]:
    """Redemptions in the last 60 min vs the usual (median of the same weekday/hour for the last 4 weeks)."""
    observed = await _count_redemptions(session, shop.id, now - timedelta(minutes=60), now)
    weekly = [
        await _count_redemptions(session, shop.id, now - timedelta(weeks=k, minutes=60), now - timedelta(weeks=k))
        for k in range(1, BASELINE_WEEKS + 1)
    ]
    has_history = shop.created_at <= now - timedelta(days=7) and sum(weekly) > 0
    usual = float(statistics.median(weekly)) if has_history else None
    pct_of_usual = round(observed / usual, 2) if usual else None
    return {
        "redemptions_last_60_min": observed,
        "usual_for_this_hour": usual,
        "pct_of_usual": pct_of_usual,
        "grid_says_quiet": grid_says_quiet(shop, now),
        "weekday": local_weekday_key(now, shop.timezone),
        "local_hour": local_hour(now, shop.timezone),
        "baseline_weeks": weekly,
    }


async def _blocked(session: AsyncSession, shop: Shop, now: datetime) -> bool:
    pending = (
        await session.execute(select(Proposal.id).where(Proposal.shop_id == shop.id, Proposal.status.in_(("pending", "awaiting_confirmation"))).limit(1))
    ).first()
    live = (await session.execute(select(Offer.id).where(Offer.shop_id == shop.id, Offer.status == "active", Offer.ends_at > now).limit(1))).first()
    return bool(pending or live)


async def detect_quiet(now: datetime | None = None) -> list[uuid.UUID]:
    """Every 5 min: open shops with no pending proposal and no live offer that are quieter than usual."""
    now = now or clock.now()
    created: list[tuple[uuid.UUID, uuid.UUID]] = []
    async with session_scope() as s:
        shops = (await s.execute(select(Shop).where(Shop.onboarding_status == "complete"))).scalars().all()
        for shop in shops:
            if not is_open(shop, now) or await _blocked(s, shop, now):
                continue
            recent = (
                await s.execute(
                    select(Signal.id).where(Signal.shop_id == shop.id, Signal.type == "quiet", Signal.created_at >= now - QUIET_COOLDOWN).limit(1)
                )
            ).first()
            if recent:
                continue
            st = await activity_stats(s, shop, now)
            below = st["usual_for_this_hour"] is not None and st["redemptions_last_60_min"] < QUIET_THRESHOLD * st["usual_for_this_hour"]
            if below or st["grid_says_quiet"]:
                sig = await create_signal(
                    s, shop, "quiet", window={"minutes": 60, "via": "baseline" if below else "grid"},
                    baseline=st["usual_for_this_hour"], observed=float(st["redemptions_last_60_min"]), now=now,
                )
                created.append((shop.id, sig.id))
    for shop_id, sig_id in created:
        trigger_agent(shop_id, sig_id)
    return [sid for _, sid in created]


async def expiry_sweep(now: datetime | None = None) -> list[uuid.UUID]:
    """Every 15 min: items expiring in under 24 h (quantity > 0) create an `expiry` signal (max one per 3 h per shop)."""
    now = now or clock.now()
    created: list[tuple[uuid.UUID, uuid.UUID]] = []
    async with session_scope() as s:
        shop_ids = (
            await s.execute(
                select(Item.shop_id).where(Item.active.is_(True), Item.quantity > 0, Item.expires_at.is_not(None), Item.expires_at > now, Item.expires_at <= now + EXPIRY_HORIZON).distinct()
            )
        ).scalars().all()
        for shop_id in shop_ids:
            shop = await s.get(Shop, shop_id)
            if shop is None or shop.onboarding_status != "complete":
                continue
            recent = (
                await s.execute(select(Signal.id).where(Signal.shop_id == shop_id, Signal.type == "expiry", Signal.created_at >= now - EXPIRY_COOLDOWN).limit(1))
            ).first()
            if recent or await _blocked(s, shop, now):
                continue
            n = int(
                (
                    await s.execute(
                        select(func.count()).select_from(Item).where(
                            Item.shop_id == shop_id, Item.active.is_(True), Item.quantity > 0, Item.expires_at > now, Item.expires_at <= now + EXPIRY_HORIZON
                        )
                    )
                ).scalar_one()
            )
            sig = await create_signal(s, shop, "expiry", window={"items": n}, now=now)
            created.append((shop_id, sig.id))
    for shop_id, sig_id in created:
        trigger_agent(shop_id, sig_id)
    return [sid for _, sid in created]
