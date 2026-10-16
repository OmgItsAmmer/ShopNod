"""MCP tool implementations (architecture.md §4.1). The MCP server wraps these; tests call them directly.

Scope rules:
  agent:propose      - the Shop Agent. Reads + `submit_proposal` (creates a PENDING proposal). Cannot approve.
  shopkeeper:read    - the shopkeeper's own assistant: read tools.
  shopkeeper:approve - may *request* approval; the offer only goes live after a dashboard confirmation.
Every tool is tied to the principal's single shop; an id from another shop is "not found".
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock, insights, learning, proposals, signals
from .auth import SCOPE_AGENT_PROPOSE, SCOPE_APPROVE, SCOPE_READ, Principal
from .errors import AppError, ErrorCode, not_found
from .guardrails import Draft
from .jsonutil import jsonable
from .models import ApprovalConfirmation, Item, Offer, Proposal, Shop, Signal
from .shop_data import load_guardrail

READERS = (SCOPE_AGENT_PROPOSE, SCOPE_READ, SCOPE_APPROVE)


def _require_any(p: Principal, scopes: tuple[str, ...]) -> None:
    if not (p.scopes & set(scopes)):
        raise AppError(ErrorCode.scope_missing, f"This token needs one of: {', '.join(scopes)}.", 403)


async def _shop(session: AsyncSession, p: Principal) -> Shop:
    shop = await session.get(Shop, p.shop_id)
    if shop is None:
        raise not_found("That shop")
    return shop


async def get_shop_profile(session: AsyncSession, p: Principal) -> dict[str, Any]:
    _require_any(p, READERS)
    s = await _shop(session, p)
    return jsonable(
        {
            "shop_id": s.id, "name": s.name, "category": s.category, "hours": s.hours, "languages": s.languages,
            "timezone": s.timezone, "currency": s.currency, "plan": s.plan, "quiet_hours_grid": s.quiet_grid,
        }
    )


async def get_guardrails(session: AsyncSession, p: Principal) -> dict[str, Any]:
    _require_any(p, READERS)
    s = await _shop(session, p)
    g = await load_guardrail(session, s.id)
    if g is None:
        return {}
    return jsonable(
        {
            "min_price_minor": g.min_price_minor, "max_discount_pct": g.max_discount_pct,
            "never_discount_item_ids": g.never_discount_item_ids, "blocked_categories": g.blocked_categories,
            "daily_budget_minor": g.daily_budget_minor, "weekly_budget_minor": g.weekly_budget_minor,
            "max_offers_per_day": g.max_offers_per_day, "max_redemptions_per_offer": g.max_redemptions_per_offer,
            "allowed_hours": g.allowed_hours, "read_only": True,
        }
    )


async def get_activity(session: AsyncSession, p: Principal, window_minutes: int = 60) -> dict[str, Any]:
    _require_any(p, READERS)
    s = await _shop(session, p)
    now = clock.now()
    st = await signals.activity_stats(session, s, now)
    recent = (
        await session.execute(select(Signal).where(Signal.shop_id == s.id, Signal.created_at >= now - timedelta(hours=6)).order_by(Signal.created_at.desc()).limit(5))
    ).scalars().all()
    return jsonable(
        {
            **st, "now_utc": now,
            "recent_signals": [{"type": g.type, "baseline": g.baseline, "observed": g.observed, "at": g.created_at} for g in recent],
        }
    )


async def get_expiring_items(session: AsyncSession, p: Principal) -> dict[str, Any]:
    _require_any(p, READERS)
    s = await _shop(session, p)
    now = clock.now()
    rows = (
        await session.execute(
            select(Item).where(Item.shop_id == s.id, Item.active.is_(True), Item.quantity > 0, Item.expires_at.is_not(None), Item.expires_at <= now + timedelta(hours=48)).order_by(Item.expires_at)
        )
    ).scalars().all()
    return jsonable(
        {
            "items": [
                {"item_id": i.id, "name": i.name, "category": i.category, "quantity": i.quantity, "expires_at": i.expires_at,
                 "hours_left": round((i.expires_at - now).total_seconds() / 3600, 1), "regular_price_minor": i.regular_price_minor}
                for i in rows
            ]
        }
    )


async def list_items(session: AsyncSession, p: Principal) -> list[dict[str, Any]]:
    _require_any(p, READERS)
    rows = (await session.execute(select(Item).where(Item.shop_id == p.shop_id, Item.active.is_(True)))).scalars().all()
    return jsonable([{"item_id": i.id, "name": i.name, "category": i.category, "price_minor": i.regular_price_minor} for i in rows])


async def get_decision_history(session: AsyncSession, p: Principal) -> dict[str, Any]:
    _require_any(p, (SCOPE_AGENT_PROPOSE,))
    s = await _shop(session, p)
    rows = (
        await session.execute(
            select(Proposal).where(Proposal.shop_id == s.id, Proposal.status.in_(("approved", "rejected", "expired"))).order_by(Proposal.created_at.desc()).limit(15)
        )
    ).scalars().all()
    learned = await learning.learned_pct(session, s.id)
    row = await session.get(learning.ShopLearning, s.id)
    return jsonable(
        {
            "learned_pct_by_category": learned,
            "accepted_hours_local": row.accepted_hours if row else {},
            "reject_counts": row.reject_counts if row else {},
            "recent": [
                {
                    "proposed_pct": r.proposed_pct, "final_pct": r.final_pct, "status": r.status, "reject_reason": r.reject_reason,
                    "categories": sorted({i.get("category") for i in r.items if i.get("category")}),
                    "window_start": r.window_start,
                }
                for r in rows
            ],
        }
    )


async def submit_proposal(
    session: AsyncSession, p: Principal, item_ids: list[str], pct: int, window_start: str, window_end: str,
    cap: int, reason: str,
) -> dict[str, Any]:
    """The ONLY write tool of the Shop Agent. Creates a PENDING proposal after validation. Cannot publish."""
    p.require(SCOPE_AGENT_PROPOSE)
    s = await _shop(session, p)
    try:
        ws, we = datetime.fromisoformat(window_start), datetime.fromisoformat(window_end)
    except ValueError:
        raise AppError(ErrorCode.validation_error, "window_start/window_end must be ISO 8601 times.", 422) from None
    run_id = None
    try:
        run_id = uuid.UUID(p.extra["run"]) if p.extra.get("run") else None
    except ValueError:
        run_id = None
    draft = Draft(tuple(str(i) for i in item_ids), int(pct), ws, we, int(cap))
    created = await proposals.create_proposal(session, s, draft, reason=reason, source="ai", agent_run_id=run_id, actor_kind="agent")
    if created.proposal is None:
        return {"status": "blocked", "reason": created.rejected_reason, "guardrail_saves": [x.to_dict() for x in created.saves]}
    return jsonable({"status": "pending", "proposal_id": created.proposal.id, "guardrail_saves": [x.to_dict() for x in created.saves],
                     "note": "Waiting for the shopkeeper to decide. You cannot publish."})


async def list_pending_proposals(session: AsyncSession, p: Principal) -> dict[str, Any]:
    _require_any(p, (SCOPE_READ, SCOPE_APPROVE))
    rows = (
        await session.execute(
            select(Proposal).where(Proposal.shop_id == p.shop_id, Proposal.status.in_(("pending", "awaiting_confirmation"))).order_by(Proposal.created_at)
        )
    ).scalars().all()
    return jsonable({"proposals": [proposals.proposal_dict(r) for r in rows]})


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        raise AppError(ErrorCode.validation_error, "Times must be ISO 8601.", 422) from None


async def approve_proposal(
    session: AsyncSession, p: Principal, proposal_id: str, final_pct: int | None = None,
    window_start: str | None = None, window_end: str | None = None, cap: int | None = None,
) -> dict[str, Any]:
    """Does NOT publish. It validates, creates a confirmation and asks the shopkeeper to confirm on the dashboard."""
    p.require(SCOPE_APPROVE)
    pid = _uuid(proposal_id)
    await session.commit()  # release before the proposals module opens its own transactions
    params = proposals.ApproveParams(final_pct, _parse_dt(window_start), _parse_dt(window_end), cap)
    conf = await proposals.request_confirmation(p.shop_id, pid, params, token_id=p.token_id)
    return jsonable(
        {
            "status": "awaiting_confirmation", "confirmation_id": conf.id, "expires_at": conf.expires_at,
            "message": "Waiting for you to confirm in the ShopNod dashboard.",
        }
    )


async def reject_proposal(session: AsyncSession, p: Principal, proposal_id: str, reason: str, note: str | None = None) -> dict[str, Any]:
    p.require(SCOPE_APPROVE)
    pid = _uuid(proposal_id)
    await session.commit()
    prop = await proposals.reject_proposal(p.shop_id, pid, user_id=p.user_id, reason=reason, note=note, channel="mcp", actor_kind="mcp")
    return jsonable({"status": prop.status, "proposal_id": prop.id})


async def get_offer_stats(session: AsyncSession, p: Principal, offer_id: str) -> dict[str, Any]:
    _require_any(p, (SCOPE_READ, SCOPE_APPROVE))
    o = await session.get(Offer, _uuid(offer_id))
    if o is None or o.shop_id != p.shop_id:
        raise not_found("That offer")
    return jsonable(await insights.offer_stats(session, o))


async def get_confirmation_status(session: AsyncSession, p: Principal, confirmation_id: str) -> dict[str, Any]:
    _require_any(p, (SCOPE_READ, SCOPE_APPROVE))
    c = await session.get(ApprovalConfirmation, _uuid(confirmation_id))
    if c is None or c.shop_id != p.shop_id:
        raise not_found("That confirmation")
    status = c.status
    if status == "awaiting" and c.expires_at <= clock.now():
        status = "expired"
    return jsonable({"confirmation_id": c.id, "proposal_id": c.proposal_id, "status": status, "expires_at": c.expires_at})


def _uuid(v: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(v))
    except ValueError:
        raise not_found("That id") from None


# Tool names each scope may call (used by tests to prove the agent token cannot approve)
AGENT_TOOLS = {
    "get_shop_profile", "get_guardrails", "get_activity", "get_expiring_items", "get_decision_history",
    "submit_proposal", "list_items",
}
SHOPKEEPER_TOOLS = {
    "get_shop_profile", "get_guardrails", "get_activity", "get_expiring_items", "list_items", "list_pending_proposals",
    "approve_proposal", "reject_proposal", "get_offer_stats", "get_confirmation_status",
}

