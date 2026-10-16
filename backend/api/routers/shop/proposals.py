"""Phases 2-4 and 6: signals, the inbox, approve / edit / reject, and MCP confirmations."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import (
    ApproveIn,
    ApproveOut,
    ConfirmationOut,
    OfferOut,
    ProposalOut,
    RejectIn,
    SignalOut,
)
from shopnod_core import auth, clock, idempotency, proposals, signals
from shopnod_core.agents.shop_agent import stop_reason
from shopnod_core.db import DB
from shopnod_core.errors import AppError, ErrorCode, not_found
from shopnod_core.jsonutil import jsonable
from shopnod_core.models import ApprovalConfirmation, Offer, Proposal

router = APIRouter()
DEMO_BASELINE, DEMO_OBSERVED = 12.0, 4.0  # a made-up "usual hour" for the demo button


def proposal_out(p: Proposal, confirmation_id: uuid.UUID | None = None) -> ProposalOut:
    d = proposals.proposal_dict(p)
    d["confirmation_id"] = confirmation_id
    return ProposalOut.model_validate(d)


def offer_out(o: Offer) -> OfferOut:
    return OfferOut(
        id=o.id, shop_id=o.shop_id, proposal_id=o.proposal_id, items=o.items, pct=o.pct, starts_at=o.starts_at, ends_at=o.ends_at,
        cap=o.cap, redeemed_count=o.redeemed_count, status=o.status, ended_reason=o.ended_reason, copy_text=o.copy or {},
        copy_source=o.copy_source, created_at=o.created_at,
    )


async def _signal(db: AsyncSession, su: auth.ShopUser, type_: str, baseline: float | None = None, observed: float | None = None) -> SignalOut:
    shop = su.shop_required
    sig = await signals.create_signal(db, shop, type_, window={"via": "button"}, baseline=baseline, observed=observed)
    why = await stop_reason(db, shop, clock.now())
    await db.commit()  # the agent task reads the signal, so it must be visible first
    if why is None:
        signals.trigger_agent(shop.id, sig.id)
    return SignalOut(signal_id=sig.id, agent_queued=why is None, skipped_reason=why)


@router.post("/signals/quiet", response_model=SignalOut, status_code=202)
async def quiet(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    """The "I'm quiet" button. The proposal arrives over SSE."""
    return await _signal(db, su, "manual")


@router.post("/demo/simulate-quiet", response_model=SignalOut, status_code=202)
async def simulate_quiet(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    if not su.shop_required.is_demo:
        raise AppError(ErrorCode.demo_only, "This button is only for demo shops.", 403)
    return await _signal(db, su, "simulated", DEMO_BASELINE, DEMO_OBSERVED)


@router.get("/proposals", response_model=list[ProposalOut])
async def list_proposals(status: str | None = Query(default=None, description="comma separated"), limit: int = Query(default=100, le=200), su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    shop = su.shop_required
    stmt = select(Proposal).where(Proposal.shop_id == shop.id)
    wanted = [x.strip() for x in status.split(",") if x.strip()] if status else ["pending", "awaiting_confirmation"]
    stmt = stmt.where(Proposal.status.in_(wanted)).order_by(Proposal.created_at.desc(), Proposal.id.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    confs = {}
    ids = [r.id for r in rows if r.status == "awaiting_confirmation"]
    if ids:
        for c in (await db.execute(select(ApprovalConfirmation).where(ApprovalConfirmation.proposal_id.in_(ids), ApprovalConfirmation.status == "awaiting"))).scalars():
            confs[c.proposal_id] = c.id
    return [proposal_out(r, confs.get(r.id)) for r in rows]


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
async def get_proposal(proposal_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    p = await db.get(Proposal, proposal_id)
    if p is None or p.shop_id != su.shop_required.id:
        raise not_found("That proposal")
    return proposal_out(p)


@router.post("/proposals/{proposal_id}/approve", response_model=ApproveOut)
async def approve(
    proposal_id: uuid.UUID, body: ApproveIn | None = None, key: str = Depends(idempotency.require_key),
    su: auth.ShopUser = Depends(auth.shop_user_complete),
):
    """Approve or edit. Re-checks guardrails and NEVER changes the human's numbers (422 guardrail_violation)."""
    body = body or ApproveIn()
    shop = su.shop_required
    params = proposals.ApproveParams(
        body.final_pct, body.window.start if body.window else None, body.window.end if body.window else None, body.cap
    )

    async def work():
        offer, prop = await proposals.approve_proposal(
            shop.id, proposal_id, user_id=su.user.id, channel=proposals.CHANNEL_DASHBOARD, params=params
        )
        out = ApproveOut(offer=offer_out(offer), proposal=proposal_out(prop))
        return 200, jsonable(out.model_dump(mode="json"))

    status, payload = await idempotency.run_idempotent(f"approve:{shop.id}:{proposal_id}", key, work)
    return _json(status, payload)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalOut)
async def reject(proposal_id: uuid.UUID, body: RejectIn, su: auth.ShopUser = Depends(auth.shop_user_complete)):
    p = await proposals.reject_proposal(su.shop_required.id, proposal_id, user_id=su.user.id, reason=body.reason, note=body.note)
    return proposal_out(p)


def _json(status: int, payload: dict):
    from fastapi.responses import JSONResponse

    return JSONResponse(payload, status_code=status)


# ── MCP confirmations (a dashboard session is required) ─────────────────
@router.get("/confirmations", response_model=list[ConfirmationOut])
async def list_confirmations(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    shop = su.shop_required
    rows = (
        await db.execute(
            select(ApprovalConfirmation).where(
                ApprovalConfirmation.shop_id == shop.id, ApprovalConfirmation.status == "awaiting", ApprovalConfirmation.expires_at > clock.now()
            ).order_by(ApprovalConfirmation.created_at)
        )
    ).scalars().all()
    out = []
    for c in rows:
        p = await db.get(Proposal, c.proposal_id)
        out.append(
            ConfirmationOut(
                id=c.id, proposal_id=c.proposal_id, final_pct=c.final_pct, status=c.status, expires_at=c.expires_at,
                created_at=c.created_at, proposal=proposal_out(p, c.id) if p else None,
            )
        )
    return out


@router.post("/confirmations/{confirmation_id}/confirm", response_model=ApproveOut)
async def confirm(confirmation_id: uuid.UUID, key: str = Depends(idempotency.require_key), su: auth.ShopUser = Depends(auth.shop_user_complete)):
    shop = su.shop_required

    async def work():
        offer, prop = await proposals.confirm_confirmation(shop.id, confirmation_id, user_id=su.user.id)
        return 200, jsonable(ApproveOut(offer=offer_out(offer), proposal=proposal_out(prop)).model_dump(mode="json"))

    status, payload = await idempotency.run_idempotent(f"confirm:{shop.id}:{confirmation_id}", key, work)
    return _json(status, payload)


@router.post("/confirmations/{confirmation_id}/decline", response_model=ProposalOut)
async def decline(confirmation_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user_complete)):
    p = await proposals.decline_confirmation(su.shop_required.id, confirmation_id, user_id=su.user.id)
    return proposal_out(p)
