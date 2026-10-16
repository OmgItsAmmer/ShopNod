"""Items. A change of the regular price also writes item_price_history (needed for the 30-day 'was' price rule)."""
from __future__ import annotations

import uuid
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import ItemIn, ItemOut
from shopnod_core import audit, auth, clock
from shopnod_core.db import DB
from shopnod_core.errors import not_found
from shopnod_core.models import Guardrail, Item, ItemPriceHistory

router = APIRouter(prefix="/items")


def _out(i: Item) -> ItemOut:
    return ItemOut(
        id=i.id, name=i.name, category=i.category, price_minor=i.price_minor, regular_price_minor=i.regular_price_minor,
        regular_price_since=datetime.combine(i.regular_price_since, time(0), tzinfo=timezone.utc) if i.regular_price_since else None,
        cost_minor=i.cost_minor, min_price_minor=i.min_price_minor, expires_at=i.expires_at, quantity=i.quantity, active=i.active,
    )


async def _get(db: AsyncSession, shop_id: uuid.UUID, item_id: uuid.UUID) -> Item:
    it = await db.get(Item, item_id)
    if it is None or it.shop_id != shop_id:
        raise not_found("That item")
    return it


@router.get("", response_model=list[ItemOut])
async def list_items(su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    shop = su.shop_required
    rows = (await db.execute(select(Item).where(Item.shop_id == shop.id).order_by(Item.name))).scalars().all()
    return [_out(i) for i in rows]


@router.post("", response_model=ItemOut, status_code=201)
async def create_item(body: ItemIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    shop = su.shop_required
    regular = body.regular_price_minor if body.regular_price_minor is not None else body.price_minor
    it = Item(
        shop_id=shop.id, name=body.name.strip(), category=body.category.strip().lower() or "general", price_minor=body.price_minor,
        regular_price_minor=regular, regular_price_since=clock.now().date(), cost_minor=body.cost_minor,
        min_price_minor=body.min_price_minor, expires_at=body.expires_at, quantity=body.quantity, active=body.active,
    )
    db.add(it)
    await db.flush()
    db.add(ItemPriceHistory(item_id=it.id, price_minor=regular, changed_at=clock.now()))
    await db.flush()
    return _out(it)


@router.put("/{item_id}", response_model=ItemOut)
async def update_item(item_id: uuid.UUID, body: ItemIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    it = await _get(db, su.shop_required.id, item_id)
    regular = body.regular_price_minor if body.regular_price_minor is not None else it.regular_price_minor
    if regular != it.regular_price_minor:
        db.add(ItemPriceHistory(item_id=it.id, price_minor=regular, changed_at=clock.now()))
        it.regular_price_since = clock.now().date()
        it.regular_price_minor = regular
    it.name, it.category = body.name.strip(), body.category.strip().lower() or "general"
    it.price_minor, it.cost_minor, it.min_price_minor = body.price_minor, body.cost_minor, body.min_price_minor
    it.expires_at, it.quantity, it.active = body.expires_at, body.quantity, body.active
    await db.flush()
    return _out(it)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    shop = su.shop_required
    it = await _get(db, shop.id, item_id)
    await db.execute(delete(ItemPriceHistory).where(ItemPriceHistory.item_id == it.id))
    g = (await db.execute(select(Guardrail).where(Guardrail.shop_id == shop.id))).scalar_one_or_none()
    if g and str(it.id) in [str(x) for x in (g.never_discount_item_ids or [])]:
        g.never_discount_item_ids = [x for x in g.never_discount_item_ids if str(x) != str(it.id)]
    await db.delete(it)
    await audit.record(db, shop_id=shop.id, action="item.deleted", actor_user_id=su.user.id, entity_type="item", entity_id=item_id, channel="dashboard", data={"name": it.name})
    return Response(status_code=204)
