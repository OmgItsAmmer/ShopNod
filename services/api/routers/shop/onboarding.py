"""Phase 1: templates, the 3-step wizard, and the shop profile."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import (
    ApplyTemplateIn,
    CompleteOut,
    LocationIn,
    ShopCreateIn,
    ShopOut,
    ShopUpdateIn,
    TemplateItemOut,
    TemplateOut,
)
from shopnod_core import audit, auth, geo, outbox, templates
from shopnod_core.db import DB
from shopnod_core.errors import AppError, ErrorCode, forbidden, not_found
from shopnod_core.models import Item, MarketArea, Shop

router = APIRouter()


async def _own_shop(db: AsyncSession, su: auth.ShopUser, shop_id: uuid.UUID) -> Shop:
    shop = await db.get(Shop, shop_id)
    if shop is None:
        raise not_found("That shop")
    if shop.owner_id != su.user.id:
        raise forbidden("That's not your shop.")
    return shop


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(_: auth.ShopUser = Depends(auth.shop_user)):
    out = []
    for key, t in templates.TEMPLATES.items():
        out.append(
            TemplateOut(
                key=key, name=t["name"], item_count=len(t["items"]), max_discount_pct=t["guardrails"]["max_discount_pct"],
                sample_items=[TemplateItemOut(name=i["name"], category=i["category"], price=i["price"]) for i in t["items"][:3]],
            )
        )
    return out


@router.post("/shops", response_model=ShopOut, status_code=201)
async def create_shop(body: ShopCreateIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    """Step 1: name + category. A user has one shop; calling again while it is a draft updates it."""
    shop = su.shop and await db.get(Shop, su.shop.id)
    if shop is not None:
        if shop.onboarding_status == "complete":
            raise AppError(ErrorCode.conflict, "You already set up your shop.", 409)
        shop.name, shop.category = body.name.strip(), body.category
    else:
        shop = Shop(
            owner_id=su.user.id, name=body.name.strip(), category=body.category, is_demo=su.user.is_demo,
            languages=["en"], timezone="UTC", currency="USD", hours=dict(templates.DEFAULT_HOURS),
            quiet_grid=templates.default_quiet_grid(), onboarding_status="draft",
        )
        db.add(shop)
    await db.flush()
    return ShopOut.model_validate(shop)


@router.put("/shops/{shop_id}/location", response_model=ShopOut)
async def set_location(shop_id: uuid.UUID, body: LocationIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    """Step 2: a map pin / 'use my location', or the Demo Market."""
    shop = await _own_shop(db, su, shop_id)
    if body.market:
        area = (await db.execute(select(MarketArea).where(MarketArea.slug == body.market))).scalar_one_or_none()
        if area is None:
            if body.market != "demo":
                raise not_found("That market")
            area = await templates.ensure_demo_market(db)
        n = int((await db.execute(select(func.count()).select_from(Shop).where(Shop.area_id == area.id))).scalar_one())
        lat, lng = templates.demo_spot(n + 7) if area.slug == "demo" else (area.center_lat, area.center_lng)
        templates.set_location(shop, lat, lng, area)
        if area.slug == "demo":
            shop.timezone, shop.currency = body.timezone or templates.DEMO_TZ, body.currency or templates.DEMO_CURRENCY
    elif body.lat is not None and body.lng is not None:
        templates.set_location(shop, body.lat, body.lng)
        nearest, best = None, 5000.0
        for a in (await db.execute(select(MarketArea))).scalars().all():
            d = geo.haversine_m(body.lat, body.lng, a.center_lat, a.center_lng)
            if d < best:
                nearest, best = a, d
        shop.area_id = nearest.id if nearest else None
        if body.timezone:
            shop.timezone = body.timezone
        if body.currency:
            shop.currency = body.currency.upper()
    else:
        raise AppError(ErrorCode.validation_error, "Send a map pin (lat and lng) or choose the Demo Market.", 422)
    if body.is_eu is not None:
        shop.is_eu = body.is_eu
    await db.flush()
    return ShopOut.model_validate(shop)


@router.post("/shops/{shop_id}/apply-template", response_model=CompleteOut)
async def apply_template(shop_id: uuid.UUID, body: ApplyTemplateIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    """Step 3: pre-fill items and guardrails from the category template."""
    shop = await _own_shop(db, su, shop_id)
    key = body.template_key or shop.category
    if key not in templates.TEMPLATES:
        key = "general"
    n = await templates.apply_template(db, shop, key)
    return CompleteOut(shop=ShopOut.model_validate(shop), items=n)


@router.post("/shops/{shop_id}/complete", response_model=CompleteOut)
async def complete(shop_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    shop = await _own_shop(db, su, shop_id)
    n = int((await db.execute(select(func.count()).select_from(Item).where(Item.shop_id == shop.id, Item.active.is_(True)))).scalar_one())
    if not shop.geohash6:
        raise AppError(ErrorCode.onboarding_incomplete, "Choose your shop's location first.", 409)
    if n == 0:
        raise AppError(ErrorCode.onboarding_incomplete, "Add at least one item first.", 409)
    if shop.onboarding_status != "complete":
        shop.onboarding_status = "complete"
        await audit.record(db, shop_id=shop.id, action="shop.completed", actor_user_id=su.user.id, entity_type="shop", entity_id=shop.id, channel="dashboard")
        await outbox.emit(db, outbox.SHOP_COMPLETED, {"shop_id": shop.id})
        await db.flush()
        outbox_kick_after_commit()
    return CompleteOut(shop=ShopOut.model_validate(shop), items=n)


def outbox_kick_after_commit() -> None:
    """The request transaction commits after the handler returns; kick shortly after so the row is visible."""
    import asyncio

    async def _later():
        await asyncio.sleep(0.2)
        outbox.kick()

    try:
        asyncio.get_running_loop().create_task(_later())
    except RuntimeError:
        pass


@router.get("/shop", response_model=ShopOut)
async def get_shop(su: auth.ShopUser = Depends(auth.shop_user)):
    return ShopOut.model_validate(su.shop_required)


@router.put("/shop", response_model=ShopOut)
async def update_shop(body: ShopUpdateIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    shop = await db.get(Shop, su.shop_required.id)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        if k == "currency":
            v = v.upper()
        setattr(shop, k, v)
    if changes:
        await audit.record(db, shop_id=shop.id, action="shop.updated", actor_user_id=su.user.id, entity_type="shop", entity_id=shop.id, channel="dashboard", data={"fields": sorted(changes)})
    await db.flush()
    return ShopOut.model_validate(shop)
