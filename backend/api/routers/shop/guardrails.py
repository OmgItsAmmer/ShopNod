"""Guardrails: read, preview ("this would have blocked 2 of last week's proposals") and save (audited)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import GuardrailIn, GuardrailOut
from shopnod_core import audit, auth, clock
from shopnod_core.db import DB
from shopnod_core.errors import AppError, ErrorCode
from shopnod_core.guardrails import BANNED_CATEGORIES, Context, Draft, Limits, parse_hhmm, validate_for_human
from shopnod_core.models import Guardrail, Item, Proposal, Shop
from shopnod_core.shop_data import limits_from, load_guardrail, load_item_facts

router = APIRouter(prefix="/guardrails")
IGNORED_RULES = {"max_offers_per_day", "budget", "window_in_past", "window_invalid"}


def _limits_from_body(body: GuardrailIn, shop: Shop) -> Limits:
    return Limits(
        min_price_minor=body.min_price_minor,
        max_discount_pct=body.max_discount_pct,
        never_discount_item_ids=frozenset(str(x) for x in body.never_discount_item_ids),
        blocked_categories=frozenset(c.strip().lower() for c in body.blocked_categories),
        daily_budget_minor=body.daily_budget_minor,
        weekly_budget_minor=body.weekly_budget_minor,
        max_offers_per_day=body.max_offers_per_day,
        max_redemptions_per_offer=body.max_redemptions_per_offer,
        allowed_start_min=parse_hhmm(body.allowed_hours.start),
        allowed_end_min=parse_hhmm(body.allowed_hours.end),
        tz=shop.timezone,
    )


async def would_block(db: AsyncSession, shop: Shop, limits: Limits) -> int:
    """How many of last week's proposals the NEW limits would have refused."""
    since = clock.now() - timedelta(days=7)
    props = (await db.execute(select(Proposal).where(Proposal.shop_id == shop.id, Proposal.created_at >= since))).scalars().all()
    if not props:
        return 0
    items = await load_item_facts(db, shop.id)
    blocked = 0
    for p in props:
        ctx = Context(now=p.created_at, limits=limits, items=items, is_eu=shop.is_eu)
        draft = Draft(tuple(i["item_id"] for i in p.items), p.proposed_pct, p.window_start, p.window_end, p.cap)
        out = validate_for_human(draft, ctx)
        if any(v.rule not in IGNORED_RULES for v in out.violations):
            blocked += 1
    return blocked


def _hint(n: int) -> str | None:
    if n <= 0:
        return None
    return f"This would have blocked {n} of last week's proposal{'s' if n != 1 else ''}."


def _out(g: Guardrail, hint_n: int = 0) -> GuardrailOut:
    return GuardrailOut(
        min_price_minor=g.min_price_minor, max_discount_pct=g.max_discount_pct,
        never_discount_item_ids=[str(x) for x in (g.never_discount_item_ids or [])],
        blocked_categories=list(g.blocked_categories or []), daily_budget_minor=g.daily_budget_minor,
        weekly_budget_minor=g.weekly_budget_minor, max_offers_per_day=g.max_offers_per_day,
        max_redemptions_per_offer=g.max_redemptions_per_offer, allowed_hours=dict(g.allowed_hours or {}),
        always_blocked_categories=sorted(BANNED_CATEGORIES), hint=_hint(hint_n), would_block=hint_n,
    )


@router.get("", response_model=GuardrailOut)
async def get_guardrails(su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    shop = su.shop_required
    g = await load_guardrail(db, shop.id)
    if g is None:
        g = Guardrail(shop_id=shop.id)
        db.add(g)
        await db.flush()
    return _out(g)


async def _validate_body(db: AsyncSession, shop: Shop, body: GuardrailIn) -> None:
    if parse_hhmm(body.allowed_hours.start) >= parse_hhmm(body.allowed_hours.end):
        raise AppError(ErrorCode.validation_error, "Allowed hours must end after they start.", 422)
    ids = [str(x) for x in body.never_discount_item_ids]
    if ids:
        found = {str(i) for i in (await db.execute(select(Item.id).where(Item.shop_id == shop.id, Item.id.in_(body.never_discount_item_ids)))).scalars().all()}
        if set(ids) - found:
            raise AppError(ErrorCode.validation_error, "One of the never-discount items isn't in your shop.", 422)


@router.post("/preview", response_model=GuardrailOut)
async def preview(body: GuardrailIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    """Not saved. Shows how many of last week's proposals the new limits would have blocked."""
    shop = su.shop_required
    await _validate_body(db, shop, body)
    g = Guardrail(shop_id=shop.id, **{k: v for k, v in body.model_dump().items()})
    g.never_discount_item_ids = [str(x) for x in body.never_discount_item_ids]
    return _out(g, await would_block(db, shop, _limits_from_body(body, shop)))


@router.put("", response_model=GuardrailOut)
async def put_guardrails(body: GuardrailIn, su: auth.ShopUser = Depends(auth.shop_user), db: AsyncSession = DB):
    shop = su.shop_required
    await _validate_body(db, shop, body)
    g = await load_guardrail(db, shop.id)
    if g is None:
        g = Guardrail(shop_id=shop.id)
        db.add(g)
    before = _snapshot(g)
    new = body.model_dump(mode="json")
    new["blocked_categories"] = sorted({c.strip().lower() for c in body.blocked_categories if c.strip()})
    new["never_discount_item_ids"] = [str(x) for x in body.never_discount_item_ids]
    n_blocked = await would_block(db, shop, _limits_from_body(body, shop))
    for k, v in new.items():
        setattr(g, k, v)
    g.updated_at = clock.now()
    await db.flush()
    after = _snapshot(g)
    changed = {k: {"before": before.get(k), "after": after[k]} for k in after if before.get(k) != after[k]}
    if changed:
        await audit.record(db, shop_id=shop.id, action="guardrails.updated", actor_user_id=su.user.id, entity_type="guardrails", entity_id=g.id, channel="dashboard", data={"changes": changed})
    return _out(g, n_blocked)


def _snapshot(g: Guardrail) -> dict[str, Any]:
    keys = ("min_price_minor", "max_discount_pct", "never_discount_item_ids", "blocked_categories", "daily_budget_minor",
            "weekly_budget_minor", "max_offers_per_day", "max_redemptions_per_offer", "allowed_hours")
    return {k: getattr(g, k, None) for k in keys}


_ = limits_from
