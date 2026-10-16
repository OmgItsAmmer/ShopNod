"""Numbers shown to the shopkeeper: offer stats, impact tiles, the learning chart. All estimates are labelled."""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock, learning
from .guardrails.windows import local_day_bounds
from .models import AuditLog, Claim, Offer, OfferReachStat, Proposal, Redemption, Shop, ShopLearning
from .settings import get_settings

MIN_GROUP = 10  # audience numbers are shown only when at least 10 people are behind them
BASKET_ITEMS_ESTIMATE = 2


def audience(n: int | None) -> dict[str, Any]:
    if n is None or n < MIN_GROUP:
        return {"value": None, "label": "fewer than 10"}
    return {"value": int(n), "label": str(int(n))}


async def offer_stats(session: AsyncSession, offer: Offer) -> dict[str, Any]:
    reds = (await session.execute(select(Redemption).where(Redemption.offer_id == offer.id).order_by(Redemption.redeemed_at))).scalars().all()
    claims = int((await session.execute(select(func.count()).select_from(Claim).where(Claim.offer_id == offer.id))).scalar_one())
    reach = await session.get(OfferReachStat, offer.id)
    reach_a = audience(reach.reach if reach else None)
    notified_a = audience(reach.notified if reach else None)
    discount = sum(r.discount_minor for r in reds)
    first = reds[0].redeemed_at - offer.starts_at if reds else None
    conv = None
    if notified_a["value"]:
        conv = round(len(reds) / notified_a["value"], 3)
    return {
        "offer_id": str(offer.id),
        "status": offer.status,
        "pct": offer.pct,
        "cap": offer.cap,
        "claims": claims,
        "redemptions": len(reds),
        "discount_given_minor": discount,
        "reach": reach_a,
        "notified": notified_a,
        "conversion": conv,
        "time_to_first_redemption_s": int(first.total_seconds()) if first and first.total_seconds() >= 0 else None,
        "waste_units": sum(r.waste_units for r in reds),
    }


async def summary(session: AsyncSession, shop: Shop, now: datetime | None = None) -> dict[str, Any]:
    now = now or clock.now()
    start, end = local_day_bounds(now, shop.timezone)
    reds = (
        await session.execute(select(Redemption).where(Redemption.shop_id == shop.id, Redemption.redeemed_at >= start, Redemption.redeemed_at < end))
    ).scalars().all()
    offer_ids = {r.offer_id for r in reds}
    offers = {o.id: o for o in (await session.execute(select(Offer).where(Offer.id.in_(offer_ids)))).scalars().all()} if offer_ids else {}

    discount = sum(r.discount_minor for r in reds)
    waste = sum(r.waste_units for r in reds)
    margin_kept = 0
    revenue = 0
    for r in reds:
        o = offers.get(r.offer_id)
        if o is None or not o.items:
            continue
        news = [i.get("new_price_minor", 0) for i in o.items]
        costs = [i.get("cost_minor") for i in o.items if i.get("cost_minor") is not None]
        avg_new = sum(news) // max(len(news), 1)
        revenue += avg_new * BASKET_ITEMS_ESTIMATE
        if costs:
            avg_cost = sum(costs) // len(costs)
            margin_kept += (avg_new - avg_cost) * BASKET_ITEMS_ESTIMATE
    billable = sum(1 for r in reds if r.billable)
    fees = billable * get_settings().REDEMPTION_FEE_MINOR
    roi = round((revenue - discount - fees) / (discount + fees), 2) if (discount + fees) else None
    return {
        "currency": shop.currency,
        "redemptions_today": len(reds),
        "extra_customers": len(reds),
        "extra_customers_is_estimate": True,
        "discount_given_minor": discount,
        "waste_avoided_units": waste,
        "margin_kept_minor": margin_kept,
        "estimated_extra_revenue_minor": revenue,
        "roi": roi,
        "roi_is_estimate": True,
        "fees_minor": fees,
    }


async def learning_curve(session: AsyncSession, shop: Shop) -> dict[str, Any]:
    weeks = await learning.weekly_curve(session, shop.id)
    row = await session.get(ShopLearning, shop.id)
    pcts = {k: float(v) for k, v in (row.category_pct if row else {}).items()}
    proposals = (await session.execute(select(Proposal).where(Proposal.shop_id == shop.id).order_by(Proposal.created_at))).scalars().all()
    decided = [p for p in proposals if p.status in ("approved", "rejected")]
    approved = [p for p in decided if p.status == "approved"]
    edited = [p for p in approved if p.final_pct is not None and p.final_pct != p.proposed_pct]
    channels = Counter(p.channel or "dashboard" for p in decided)
    reject_reasons = Counter(p.reject_reason or "other" for p in proposals if p.status == "rejected")
    times = [(p.decided_at - p.created_at).total_seconds() for p in decided if p.decided_at]
    saves = sum(1 for p in proposals if p.guardrail_saves)
    blocked = int(
        (await session.execute(select(func.count()).select_from(AuditLog).where(AuditLog.shop_id == shop.id, AuditLog.action == "guardrail.proposal_blocked"))).scalar_one()
    )
    latest_cat = None
    for p in reversed(proposals):
        if p.items:
            latest_cat = learning.dominant_category(p.items)
            break
    next_pct = round(pcts[latest_cat]) if latest_cat in pcts else (round(sum(pcts.values()) / len(pcts)) if pcts else 10)
    return {
        "weeks": weeks,
        "totals": {
            "proposals": len(proposals),
            "decided": len(decided),
            "approval_rate": round(len(approved) / len(decided), 3) if decided else None,
            "edit_rate": round(len(edited) / len(approved), 3) if approved else None,
            "avg_edit": round(sum(p.final_pct - p.proposed_pct for p in edited) / len(edited), 2) if edited else None,
            "expired": sum(1 for p in proposals if p.status == "expired"),
            "median_time_to_decision_s": int(statistics.median(times)) if times else None,
        },
        "reject_reasons": dict(reject_reasons),
        "approval_channels": dict(channels),
        "guardrail_saves": {"clamped": saves, "blocked": blocked},
        "learned_pct_by_category": pcts,
        "next_proposal_pct": next_pct,
    }

