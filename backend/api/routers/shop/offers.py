"""Offers, per-offer stats, 'End now', and the counter scan (redemptions)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import OfferOut, OfferStatsOut, RedeemIn, RedeemOut
from shopnod_core import auth, idempotency, insights, proposals, redeem
from shopnod_core.db import DB
from shopnod_core.errors import AppError, ErrorCode, not_found
from shopnod_core.models import Offer

from .proposals import offer_out

router = APIRouter()


@router.get("/offers", response_model=list[OfferOut])
async def list_offers(status: str | None = Query(default=None, description="comma separated"), limit: int = Query(default=100, le=200), su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    stmt = select(Offer).where(Offer.shop_id == su.shop_required.id)
    if status:
        stmt = stmt.where(Offer.status.in_([x.strip() for x in status.split(",") if x.strip()]))
    rows = (await db.execute(stmt.order_by(Offer.created_at.desc(), Offer.id.desc()).limit(limit))).scalars().all()
    return [offer_out(o) for o in rows]


async def _offer(db: AsyncSession, shop_id: uuid.UUID, offer_id: uuid.UUID) -> Offer:
    o = await db.get(Offer, offer_id)
    if o is None or o.shop_id != shop_id:
        raise not_found("That offer")
    return o


@router.get("/offers/{offer_id}", response_model=OfferOut)
async def get_offer(offer_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    return offer_out(await _offer(db, su.shop_required.id, offer_id))


@router.get("/offers/{offer_id}/stats", response_model=OfferStatsOut)
async def offer_stats(offer_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    """Reach and notified come from offer_reach_stats and are shown only when there are at least 10 people."""
    return await insights.offer_stats(db, await _offer(db, su.shop_required.id, offer_id))


@router.post("/offers/{offer_id}/end", response_model=OfferOut)
async def end_offer(offer_id: uuid.UUID, key: str = Depends(idempotency.require_key), su: auth.ShopUser = Depends(auth.shop_user_complete)):
    shop = su.shop_required

    async def work():
        o = await proposals.end_offer_now(shop.id, offer_id, user_id=su.user.id)
        return 200, offer_out(o).model_dump(mode="json")

    status, payload = await idempotency.run_idempotent(f"end-offer:{shop.id}:{offer_id}", key, work)
    return JSONResponse(payload, status_code=status)


@router.post("/redemptions", response_model=RedeemOut)
async def redemptions(body: RedeemIn, key: str = Depends(idempotency.require_key), su: auth.ShopUser = Depends(auth.shop_user_complete)):
    """Scan at the counter: QR text or the 6-character short code."""
    if not body.payload and not body.short_code:
        raise AppError(ErrorCode.validation_error, "Scan the QR code or type the 6-character code.", 422)
    shop = su.shop_required

    async def work():
        res = await redeem.redeem(
            shop.id, payload=body.payload, short_code=body.short_code, idempotency_key=key, actor_user_id=su.user.id
        )
        return 200, res

    status, payload = await idempotency.run_idempotent(f"redeem:{shop.id}", key, work)
    return JSONResponse(payload, status_code=status)
