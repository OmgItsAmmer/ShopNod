"""Loads shop data from the database into the pure objects the guardrail validator uses."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .guardrails import Context, ItemFacts, Limits, PricePoint, parse_hhmm
from .guardrails.validator import per_redemption_discount
from .guardrails.windows import local_day_bounds
from .models import Guardrail, Item, ItemPriceHistory, Offer, Proposal, Redemption, Shop


def limits_from(g: Guardrail | None, shop: Shop) -> Limits:
    if g is None:
        return Limits(tz=shop.timezone)
    ah = g.allowed_hours or {}
    return Limits(
        min_price_minor=g.min_price_minor or 0,
        max_discount_pct=g.max_discount_pct,
        never_discount_item_ids=frozenset(str(x) for x in (g.never_discount_item_ids or [])),
        blocked_categories=frozenset(str(x).lower() for x in (g.blocked_categories or [])),
        daily_budget_minor=g.daily_budget_minor,
        weekly_budget_minor=g.weekly_budget_minor,
        max_offers_per_day=g.max_offers_per_day,
        max_redemptions_per_offer=g.max_redemptions_per_offer,
        allowed_start_min=parse_hhmm(ah.get("start", "08:00")),
        allowed_end_min=parse_hhmm(ah.get("end", "21:00")),
        tz=shop.timezone,
    )


def _since_dt(d: date | None) -> datetime | None:
    return datetime.combine(d, time(0), tzinfo=timezone.utc) if d else None


def item_facts(item: Item, history: list[ItemPriceHistory]) -> ItemFacts:
    return ItemFacts(
        id=str(item.id),
        name=item.name,
        category=item.category,
        regular_price_minor=item.regular_price_minor,
        regular_price_since=_since_dt(item.regular_price_since),
        min_price_minor=item.min_price_minor,
        cost_minor=item.cost_minor,
        history=tuple(PricePoint(h.changed_at, h.price_minor) for h in history),
    )


async def load_guardrail(session: AsyncSession, shop_id: uuid.UUID) -> Guardrail | None:
    return (await session.execute(select(Guardrail).where(Guardrail.shop_id == shop_id))).scalar_one_or_none()


async def load_items(session: AsyncSession, shop_id: uuid.UUID, active_only: bool = True) -> list[Item]:
    stmt = select(Item).where(Item.shop_id == shop_id)
    if active_only:
        stmt = stmt.where(Item.active.is_(True))
    return list((await session.execute(stmt.order_by(Item.name))).scalars().all())


async def load_item_facts(session: AsyncSession, shop_id: uuid.UUID) -> dict[str, ItemFacts]:
    items = await load_items(session, shop_id)
    if not items:
        return {}
    ids = [i.id for i in items]
    hist_rows = (
        await session.execute(select(ItemPriceHistory).where(ItemPriceHistory.item_id.in_(ids)).order_by(ItemPriceHistory.changed_at))
    ).scalars().all()
    by_item: dict[uuid.UUID, list[ItemPriceHistory]] = {}
    for h in hist_rows:
        by_item.setdefault(h.item_id, []).append(h)
    return {str(i.id): item_facts(i, by_item.get(i.id, [])) for i in items}


def estimate_offer_cost(offer: Offer) -> int:
    refs = [int(i.get("was_minor", 0)) for i in (offer.items or []) if i.get("was_minor")]
    if not refs:
        return 0
    return per_redemption_discount(refs, offer.pct) * offer.cap


async def committed_cost(session: AsyncSession, shop: Shop, since: datetime) -> int:
    """Realised discount for offers since `since`, plus the estimate for offers still running."""
    offers = (
        await session.execute(select(Offer).where(Offer.shop_id == shop.id, Offer.created_at >= since))
    ).scalars().all()
    total = 0
    for o in offers:
        realised = (
            await session.execute(select(func.coalesce(func.sum(Redemption.discount_minor), 0)).where(Redemption.offer_id == o.id))
        ).scalar_one()
        total += max(int(realised), estimate_offer_cost(o)) if o.status == "active" else int(realised)
    return total


async def offers_published_today(session: AsyncSession, shop: Shop, now: datetime) -> int:
    start, end = local_day_bounds(now, shop.timezone)
    return int(
        (
            await session.execute(
                select(func.count()).select_from(Offer).where(Offer.shop_id == shop.id, Offer.created_at >= start, Offer.created_at < end)
            )
        ).scalar_one()
    )


async def build_context(session: AsyncSession, shop: Shop, now: datetime) -> Context:
    g = await load_guardrail(session, shop.id)
    limits = limits_from(g, shop)
    day_start, _ = local_day_bounds(now, shop.timezone)
    return Context(
        now=now,
        limits=limits,
        items=await load_item_facts(session, shop.id),
        is_eu=shop.is_eu,
        offers_today=await offers_published_today(session, shop, now),
        committed_today_minor=await committed_cost(session, shop, day_start) if limits.daily_budget_minor is not None else 0,
        committed_week_minor=await committed_cost(session, shop, now - timedelta(days=7)) if limits.weekly_budget_minor is not None else 0,
    )


async def pending_proposal(session: AsyncSession, shop_id: uuid.UUID) -> Proposal | None:
    return (
        await session.execute(
            select(Proposal).where(Proposal.shop_id == shop_id, Proposal.status.in_(("pending", "awaiting_confirmation")))
        )
    ).scalars().first()


async def overlapping_active_offer(session: AsyncSession, shop_id: uuid.UUID, now: datetime) -> Offer | None:
    return (
        await session.execute(select(Offer).where(Offer.shop_id == shop_id, Offer.status == "active", Offer.ends_at > now))
    ).scalars().first()
