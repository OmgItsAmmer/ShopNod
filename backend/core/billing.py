"""Billing, without a payment provider: shops pay per redemption ("no customer, no fee").

Each billable redemption is written once to the usage ledger (`meter_events`), and the billing page shows the month's
count and the estimated amount. No card is taken and no money moves; a payment provider can be plugged in later by
reading this ledger.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .db import session_scope
from .guardrails.windows import local_day_bounds
from .models import MeterEvent, Redemption, Shop
from .settings import get_settings

PRO_UNLOCKS = ["Unlimited offers", "Auto-approve rules", "WhatsApp alerts", "Multi-language copy", "Analytics"]


async def meter_redemption(redemption_id: uuid.UUID) -> str:
    """Record one billable redemption in the usage ledger. Safe to run twice (one row per redemption)."""
    async with session_scope() as s:
        red = await s.get(Redemption, redemption_id)
        if red is None or not red.billable:
            return "skipped"
        ev = (await s.execute(select(MeterEvent).where(MeterEvent.redemption_id == redemption_id))).scalar_one_or_none()
        if ev is None:
            s.add(MeterEvent(shop_id=red.shop_id, redemption_id=redemption_id, identifier=str(redemption_id), status="recorded", sent_at=clock.now()))
    return "recorded"


async def overview(session: AsyncSession, shop: Shop, now: datetime | None = None) -> dict[str, Any]:
    now = now or clock.now()
    local = now.astimezone(UTC)
    month_start = datetime(local.year, local.month, 1, tzinfo=UTC)
    billable = int(
        (await session.execute(select(func.count()).select_from(Redemption).where(Redemption.shop_id == shop.id, Redemption.billable.is_(True), Redemption.redeemed_at >= month_start))).scalar_one()
    )
    recorded = int(
        (await session.execute(select(func.count()).select_from(MeterEvent).where(MeterEvent.shop_id == shop.id, MeterEvent.created_at >= month_start))).scalar_one()
    )
    today_start, today_end = local_day_bounds(now, shop.timezone)
    today = int(
        (await session.execute(select(func.count()).select_from(Redemption).where(Redemption.shop_id == shop.id, Redemption.redeemed_at >= today_start, Redemption.redeemed_at < today_end))).scalar_one()
    )
    fee = get_settings().REDEMPTION_FEE_USD_CENTS
    return {
        "plan": shop.plan,
        "month": month_start.strftime("%Y-%m"),
        "billable_redemptions": billable,
        "usage_recorded": recorded,
        "redemptions_today": today,
        "fee_per_redemption_usd_cents": fee,
        "upcoming_invoice_usd_cents": 0 if shop.plan == "pro" else billable * fee,
        "pro_unlocks": PRO_UNLOCKS,
        "demo": True,  # no card is taken and no money moves
    }
