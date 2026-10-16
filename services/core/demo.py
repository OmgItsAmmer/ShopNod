"""Put a demo shop back to its template state ("Reset my demo shop")."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import audit, outbox, templates
from .errors import AppError, ErrorCode
from .models import (
    AgentRun, ApprovalConfirmation, Claim, MeterEvent, Notification, Offer, OfferReachStat, Proposal, Redemption, Shop,
    ShopLearning, Signal,
)


async def reset_demo_shop(session: AsyncSession, shop: Shop, user_id: uuid.UUID | None = None) -> dict[str, int]:
    if not shop.is_demo:
        raise AppError(ErrorCode.demo_only, "Only demo shops can be reset.", 403)
    offers = (await session.execute(select(Offer).where(Offer.shop_id == shop.id))).scalars().all()
    offer_ids = [o.id for o in offers]
    for o in offers:
        if o.status == "active":
            await outbox.emit(session, outbox.OFFER_ENDED, {"offer_id": o.id, "shop_id": shop.id, "reason": "demo_reset"})
    counts = {"offers": len(offers)}
    if offer_ids:
        red_ids = (await session.execute(select(Redemption.id).where(Redemption.offer_id.in_(offer_ids)))).scalars().all()
        if red_ids:
            await session.execute(delete(MeterEvent).where(MeterEvent.redemption_id.in_(red_ids)))
        await session.execute(delete(Redemption).where(Redemption.offer_id.in_(offer_ids)))
        await session.execute(delete(Claim).where(Claim.offer_id.in_(offer_ids)))
        await session.execute(delete(Notification).where(Notification.offer_id.in_(offer_ids)))
        await session.execute(delete(OfferReachStat).where(OfferReachStat.offer_id.in_(offer_ids)))
        await session.execute(delete(Offer).where(Offer.id.in_(offer_ids)))
    await session.execute(delete(ApprovalConfirmation).where(ApprovalConfirmation.shop_id == shop.id))
    counts["proposals"] = len((await session.execute(select(Proposal.id).where(Proposal.shop_id == shop.id))).scalars().all())
    await session.execute(delete(Proposal).where(Proposal.shop_id == shop.id))
    await session.execute(delete(Signal).where(Signal.shop_id == shop.id))
    await session.execute(delete(AgentRun).where(AgentRun.shop_id == shop.id))
    await session.execute(delete(ShopLearning).where(ShopLearning.shop_id == shop.id))
    await templates.apply_template(session, shop, shop.template_key or shop.category)
    await audit.record(session, shop_id=shop.id, action="demo.reset", actor_user_id=user_id, entity_type="shop", entity_id=shop.id, channel="dashboard", data=counts)
    return counts
