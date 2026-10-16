from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import OkOut
from shopnod_core import auth, demo, outbox
from shopnod_core.db import DB
from shopnod_core.models import Shop

router = APIRouter()


@router.post("/demo/reset", response_model=OkOut)
async def demo_reset(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    """Put a demo shop back to its template state (offers, claims, proposals and notifications are removed)."""
    shop = await db.get(Shop, su.shop_required.id)
    await demo.reset_demo_shop(db, shop, su.user.id)
    await db.commit()
    outbox.kick()
    return OkOut()
