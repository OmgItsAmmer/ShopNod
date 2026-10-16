"""Learning from the human: per-category EWMA of the final %, accepted hours, rejection counts.

`update_learning` runs right after each decision, so the very next proposal already changes
(one edit from 25% to 10% moves the next proposal to about 10-15%).
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .guardrails import local_hour
from .models import Proposal, Shop, ShopLearning

ALPHA = 0.5
TOO_GENEROUS_FACTOR = 0.6  # "too generous" rejection implies the target was well below what was proposed
DECIDED = ("approved", "rejected")


def dominant_category(items: list[dict]) -> str | None:
    cats = [i.get("category") for i in items or [] if i.get("category")]
    return Counter(cats).most_common(1)[0][0] if cats else None


def ewma(prev: float | None, value: float, alpha: float = ALPHA) -> float:
    return value if prev is None else alpha * value + (1 - alpha) * prev


def decision_of(p: Proposal) -> str:
    if p.status == "rejected":
        return "rejected"
    if p.status == "approved":
        return "edited" if p.final_pct is not None and p.final_pct != p.proposed_pct else "approved"
    return p.status


async def get_or_create(session: AsyncSession, shop_id: uuid.UUID) -> ShopLearning:
    row = await session.get(ShopLearning, shop_id)
    if row is None:
        row = ShopLearning(shop_id=shop_id, category_pct={}, accepted_hours={}, reject_counts={}, weekly=[], applied_ids=[])
        session.add(row)
        await session.flush()
    return row


async def learned_pct(session: AsyncSession, shop_id: uuid.UUID) -> dict[str, float]:
    row = await session.get(ShopLearning, shop_id)
    return {k: float(v) for k, v in (row.category_pct or {}).items()} if row else {}


async def update_learning(session: AsyncSession, proposal_id: uuid.UUID) -> bool:
    """Apply one decision. Safe to run twice (tracked in applied_ids). Returns True if applied."""
    p = await session.get(Proposal, proposal_id)
    if p is None or p.status not in DECIDED:
        return False
    shop = await session.get(Shop, p.shop_id)
    row = await get_or_create(session, p.shop_id)
    if str(p.id) in (row.applied_ids or []):
        return False
    cat = dominant_category(p.items)
    pcts = dict(row.category_pct or {})
    hours = dict(row.accepted_hours or {})
    rejects = dict(row.reject_counts or {})
    if p.status == "approved":
        final = p.final_pct if p.final_pct is not None else p.proposed_pct
        if cat:
            pcts[cat] = round(ewma(pcts.get(cat), float(final)), 2)
        h = str(local_hour(p.window_start, shop.timezone if shop else "UTC"))
        hours[h] = int(hours.get(h, 0)) + 1
    else:
        reason = p.reject_reason or "other"
        rejects[reason] = int(rejects.get(reason, 0)) + 1
        if reason == "too_generous" and cat:
            pcts[cat] = round(ewma(pcts.get(cat), max(1.0, p.proposed_pct * TOO_GENEROUS_FACTOR)), 2)
    row.category_pct, row.accepted_hours, row.reject_counts = pcts, hours, rejects
    row.decisions = int(row.decisions or 0) + 1
    row.applied_ids = ([str(p.id)] + list(row.applied_ids or []))[:300]
    row.updated_at = clock.now()
    await session.flush()
    return True


def _week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


async def weekly_curve(session: AsyncSession, shop_id: uuid.UUID, weeks: int = 8) -> list[dict]:
    """Approval rate per ISO week plus the average edit (final % - proposed %)."""
    since = clock.now() - timedelta(weeks=weeks)
    rows = (
        await session.execute(
            select(Proposal).where(Proposal.shop_id == shop_id, Proposal.created_at >= since, Proposal.status.in_(("approved", "rejected", "expired")))
        )
    ).scalars().all()
    buckets: dict[str, dict] = {}
    for p in rows:
        b = buckets.setdefault(_week_key(p.created_at), {"week": _week_key(p.created_at), "proposals": 0, "approved": 0, "edited": 0, "edit_sum": 0.0})
        b["proposals"] += 1
        if p.status == "approved":
            b["approved"] += 1
            if p.final_pct is not None and p.final_pct != p.proposed_pct:
                b["edited"] += 1
                b["edit_sum"] += p.final_pct - p.proposed_pct
    out = []
    for key in sorted(buckets):
        b = buckets[key]
        out.append(
            {
                "week": key,
                "proposals": b["proposals"],
                "approved": b["approved"],
                "approval_rate": round(b["approved"] / b["proposals"], 3) if b["proposals"] else 0.0,
                "edit_rate": round(b["edited"] / b["approved"], 3) if b["approved"] else 0.0,
                "avg_edit": round(b["edit_sum"] / b["edited"], 2) if b["edited"] else 0.0,
            }
        )
    return out


async def recompute_learning(session: AsyncSession, shop_id: uuid.UUID) -> ShopLearning:
    """Rebuild everything from the decision history (nightly)."""
    row = await get_or_create(session, shop_id)
    shop = await session.get(Shop, shop_id)
    proposals = (
        await session.execute(
            select(Proposal).where(Proposal.shop_id == shop_id, Proposal.status.in_(DECIDED)).order_by(Proposal.decided_at, Proposal.created_at)
        )
    ).scalars().all()
    pcts: dict[str, float] = {}
    hours: dict[str, int] = {}
    rejects: dict[str, int] = {}
    for p in proposals:
        cat = dominant_category(p.items)
        if p.status == "approved":
            final = p.final_pct if p.final_pct is not None else p.proposed_pct
            if cat:
                pcts[cat] = round(ewma(pcts.get(cat), float(final)), 2)
            h = str(local_hour(p.window_start, shop.timezone if shop else "UTC"))
            hours[h] = hours.get(h, 0) + 1
        else:
            reason = p.reject_reason or "other"
            rejects[reason] = rejects.get(reason, 0) + 1
            if reason == "too_generous" and cat:
                pcts[cat] = round(ewma(pcts.get(cat), max(1.0, p.proposed_pct * TOO_GENEROUS_FACTOR)), 2)
    row.category_pct, row.accepted_hours, row.reject_counts = pcts, hours, rejects
    row.weekly = await weekly_curve(session, shop_id)
    row.decisions = len(proposals)
    row.applied_ids = [str(p.id) for p in proposals][-300:]
    row.updated_at = clock.now()
    await session.flush()
    return row
