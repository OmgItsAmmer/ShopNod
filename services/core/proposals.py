"""Proposal lifecycle (Plan 3 §0.5): create (agent/rules) → approve | reject | expire, plus the MCP
confirmation step. Publishing an offer is only possible through `approve_proposal`, which needs a
human decision (dashboard session, or an MCP request the shopkeeper confirmed on the dashboard)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import audit, clock, outbox
from .copyagent import facts_for, generate_copy, template_copy
from .db import session_scope
from .errors import AppError, ErrorCode, not_found
from .guardrails import Draft, Save, Validated
from .guardrails import validate_for_agent, validate_for_human
from .models import ApprovalConfirmation, Offer, Proposal, Shop
from .shop_data import build_context, pending_proposal

CONFIRMATION_TTL = timedelta(minutes=10)
REJECT_REASONS = ("wrong_items", "wrong_time", "too_generous", "other")
CHANNEL_DASHBOARD = "dashboard"
CHANNEL_MCP = "mcp_confirmed"


def _items_json(v: Validated) -> list[dict[str, Any]]:
    return [i.to_dict(v.pct) for i in v.items]


@dataclass
class CreateResult:
    proposal: Proposal | None
    saves: list[Save] = field(default_factory=list)
    rejected_reason: str | None = None


async def create_proposal(
    session: AsyncSession,
    shop: Shop,
    draft: Draft,
    *,
    reason: str,
    source: str,
    signal_id: uuid.UUID | None = None,
    agent_run_id: uuid.UUID | None = None,
    actor_kind: str = "agent",
    now: datetime | None = None,
) -> CreateResult:
    """Validate (strict with the AI) and store a PENDING proposal. Never publishes."""
    now = now or clock.now()
    if await pending_proposal(session, shop.id) is not None:
        raise AppError(ErrorCode.conflict, "There is already a proposal waiting for your decision.", 409)
    ctx = await build_context(session, shop, now)
    outcome = validate_for_agent(draft, ctx)
    if not outcome.ok or outcome.proposal is None:
        await audit.record(
            session, shop_id=shop.id, action="guardrail.proposal_blocked", actor_kind=actor_kind,
            data={"reason": outcome.rejected_reason, "saves": [s.to_dict() for s in outcome.saves], "source": source},
        )
        return CreateResult(None, outcome.saves, outcome.rejected_reason)
    v = outcome.proposal
    prop = Proposal(
        shop_id=shop.id,
        signal_id=signal_id,
        items=_items_json(v),
        proposed_pct=v.pct,
        original_pct=draft.pct,
        window_start=v.window_start,
        window_end=v.window_end,
        cap=v.cap,
        reason=reason.strip()[:600],
        source=source,
        status="pending",
        agent_run_id=agent_run_id,
        guardrail_saves=[s.to_dict() for s in outcome.saves],
        expires_at=v.window_start,
        created_at=now,
    )
    session.add(prop)
    await session.flush()
    await audit.record(
        session, shop_id=shop.id, action="proposal.created", actor_kind=actor_kind, entity_type="proposal",
        entity_id=prop.id, data={"source": source, "pct": v.pct, "original_pct": draft.pct, "saves": len(outcome.saves)},
    )
    await outbox.emit(session, outbox.PROPOSAL_CREATED, {"proposal_id": prop.id, "shop_id": shop.id, "source": source})
    return CreateResult(prop, outcome.saves)


def proposal_dict(p: Proposal) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "shop_id": str(p.shop_id),
        "status": p.status,
        "source": p.source,
        "items": p.items,
        "proposed_pct": p.proposed_pct,
        "original_pct": p.original_pct,
        "final_pct": p.final_pct,
        "window_start": p.window_start,
        "window_end": p.window_end,
        "cap": p.cap,
        "reason": p.reason,
        "channel": p.channel,
        "reject_reason": p.reject_reason,
        "guardrail_saves": p.guardrail_saves,
        "agent_run_id": str(p.agent_run_id) if p.agent_run_id else None,
        "created_at": p.created_at,
        "decided_at": p.decided_at,
    }


# ── approve ──────────────────────────────────────────────────────────────
@dataclass
class ApproveParams:
    final_pct: int | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    cap: int | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "final_pct": self.final_pct,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "cap": self.cap,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "ApproveParams":
        def dt(v):
            return datetime.fromisoformat(v) if v else None

        return cls(d.get("final_pct"), dt(d.get("window_start")), dt(d.get("window_end")), d.get("cap"))


def _draft_for(p: Proposal, params: ApproveParams) -> Draft:
    return Draft(
        item_ids=tuple(i["item_id"] for i in p.items),
        pct=params.final_pct if params.final_pct is not None else p.proposed_pct,
        window_start=params.window_start or p.window_start,
        window_end=params.window_end or p.window_end,
        cap=params.cap if params.cap is not None else p.cap,
    )


def _violation_error(outcome) -> AppError:
    first = outcome.violations[0]
    return AppError(
        ErrorCode.guardrail_violation,
        first.message,
        422,
        details={
            "rule": first.rule,
            "limit": first.limit,
            "got": first.got,
            "violations": [v.to_dict() for v in outcome.violations],
        },
    )


def _check_status(p: Proposal, allowed: tuple[str, ...], now: datetime, has_window_override: bool) -> None:
    if p.status not in allowed:
        raise AppError(ErrorCode.proposal_not_pending, f"This proposal is already {p.status.replace('_', ' ')}.", 409)
    if not has_window_override and p.window_start < now - timedelta(seconds=60):
        raise AppError(ErrorCode.proposal_expired, "This proposal's time has already started, so it expired.", 409)


async def _prevalidate(shop_id: uuid.UUID, proposal_id: uuid.UUID, params: ApproveParams, allowed: tuple[str, ...]):
    async with session_scope() as s:
        p = await s.get(Proposal, proposal_id)
        if p is None or p.shop_id != shop_id:
            raise not_found("That proposal")
        shop = await s.get(Shop, shop_id)
        now = clock.now()
        _check_status(p, allowed, now, params.window_start is not None)
        ctx = await build_context(s, shop, now)
        outcome = validate_for_human(_draft_for(p, params), ctx)
        if not outcome.ok or outcome.proposal is None:
            raise _violation_error(outcome)
        return shop, outcome.proposal


async def approve_proposal(
    shop_id: uuid.UUID,
    proposal_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None,
    channel: str,
    params: ApproveParams | None = None,
    allowed_statuses: tuple[str, ...] = ("pending",),
    confirmation_id: uuid.UUID | None = None,
) -> tuple[Offer, Proposal]:
    """Publish a proposal as an offer. The human's numbers are never changed: out-of-range → 422.

    Order: lock row → re-check guardrails → create offer → Copy Agent (≤5 s) → offer.published.
    The copy is generated before the short locked transaction so the lock is never held during AI calls.
    """
    params = params or ApproveParams()
    shop, validated = await _prevalidate(shop_id, proposal_id, params, allowed_statuses)
    languages = list(shop.languages or ["en"])
    facts = facts_for(
        shop.name, [i.to_dict() for i in validated.items], validated.pct, validated.window_start, validated.window_end,
        shop.timezone, shop.currency,
    )
    copy, copy_source = await generate_copy(shop_id=shop.id, facts=facts, languages=languages)
    if not copy:
        copy, copy_source = template_copy(facts, languages), "template"

    async with session_scope() as s:
        stmt = select(Proposal).where(Proposal.id == proposal_id).with_for_update()
        p = (await s.execute(stmt)).scalar_one_or_none()
        if p is None or p.shop_id != shop_id:
            raise not_found("That proposal")
        shop_row = await s.get(Shop, shop_id)
        now = clock.now()
        _check_status(p, allowed_statuses, now, params.window_start is not None)
        conf: ApprovalConfirmation | None = None
        if confirmation_id is not None:
            conf = (
                await s.execute(select(ApprovalConfirmation).where(ApprovalConfirmation.id == confirmation_id).with_for_update())
            ).scalar_one_or_none()
            if conf is None or conf.status != "awaiting":
                raise AppError(ErrorCode.confirmation_not_awaiting, "This confirmation is no longer waiting.", 409)
        ctx = await build_context(s, shop_row, now)
        outcome = validate_for_human(_draft_for(p, params), ctx)  # re-check under the lock
        if not outcome.ok or outcome.proposal is None:
            raise _violation_error(outcome)
        v = outcome.proposal
        offer = Offer(
            proposal_id=p.id,
            shop_id=p.shop_id,
            area_id=shop_row.area_id,
            geohash6=shop_row.geohash6,
            items=_items_json(v),
            pct=v.pct,
            starts_at=v.window_start,
            ends_at=v.window_end,
            cap=v.cap,
            status="active",
            copy=copy,
            copy_source=copy_source,
            created_at=now,
        )
        s.add(offer)
        p.status = "approved"
        p.final_pct = v.pct
        p.decided_by = user_id
        p.decided_at = now
        p.channel = channel
        p.items = _items_json(v)
        p.window_start, p.window_end, p.cap = v.window_start, v.window_end, v.cap
        if conf is not None:
            conf.status = "confirmed"
            conf.decided_at = now
        await s.flush()
        edited = v.pct != p.proposed_pct
        await audit.record(
            s, shop_id=p.shop_id, action="proposal.edited" if edited else "proposal.approved", actor_user_id=user_id,
            entity_type="proposal", entity_id=p.id, channel=channel,
            data={"offer_id": offer.id, "proposed_pct": p.proposed_pct, "final_pct": v.pct, "copy_source": copy_source},
        )
        await outbox.emit(
            s, outbox.PROPOSAL_DECIDED,
            {"proposal_id": p.id, "shop_id": p.shop_id, "decision": "edited" if edited else "approved",
             "proposed_pct": p.proposed_pct, "final_pct": v.pct, "channel": channel},
        )
        await outbox.emit(
            s, outbox.OFFER_PUBLISHED,
            {"offer_id": offer.id, "shop_id": offer.shop_id, "geohash6": offer.geohash6, "ends_at": offer.ends_at},
        )
    outbox.kick()
    return offer, p


# ── reject ───────────────────────────────────────────────────────────────
async def reject_proposal(
    shop_id: uuid.UUID,
    proposal_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None,
    reason: str,
    note: str | None = None,
    channel: str = CHANNEL_DASHBOARD,
    actor_kind: str = "user",
) -> Proposal:
    if reason not in REJECT_REASONS:
        raise AppError(ErrorCode.validation_error, f"Reason must be one of {', '.join(REJECT_REASONS)}.", 422)
    async with session_scope() as s:
        p = (await s.execute(select(Proposal).where(Proposal.id == proposal_id).with_for_update())).scalar_one_or_none()
        if p is None or p.shop_id != shop_id:
            raise not_found("That proposal")
        if p.status not in ("pending", "awaiting_confirmation"):
            raise AppError(ErrorCode.proposal_not_pending, f"This proposal is already {p.status.replace('_', ' ')}.", 409)
        now = clock.now()
        was_awaiting = p.status == "awaiting_confirmation"
        p.status = "rejected"
        p.reject_reason = reason
        p.reject_note = (note or "")[:500] or None
        p.decided_by, p.decided_at, p.channel = user_id, now, channel
        if was_awaiting:
            for c in (await s.execute(select(ApprovalConfirmation).where(ApprovalConfirmation.proposal_id == p.id, ApprovalConfirmation.status == "awaiting"))).scalars():
                c.status, c.decided_at = "declined", now
        await audit.record(
            s, shop_id=shop_id, action="proposal.rejected", actor_user_id=user_id, actor_kind=actor_kind,
            entity_type="proposal", entity_id=p.id, channel=channel, data={"reason": reason, "note": note},
        )
        await outbox.emit(
            s, outbox.PROPOSAL_DECIDED,
            {"proposal_id": p.id, "shop_id": shop_id, "decision": "rejected", "proposed_pct": p.proposed_pct,
             "final_pct": None, "channel": channel, "reason": reason},
        )
    outbox.kick()
    return p


# ── MCP confirmation flow ────────────────────────────────────────────────
async def request_confirmation(
    shop_id: uuid.UUID, proposal_id: uuid.UUID, params: ApproveParams, *, token_id: uuid.UUID | None
) -> ApprovalConfirmation:
    """An MCP client asked to approve. Validates now, then waits for a dashboard click."""
    await _prevalidate(shop_id, proposal_id, params, ("pending", "awaiting_confirmation"))
    async with session_scope() as s:
        p = (await s.execute(select(Proposal).where(Proposal.id == proposal_id).with_for_update())).scalar_one()
        now = clock.now()
        existing = (
            await s.execute(
                select(ApprovalConfirmation).where(
                    ApprovalConfirmation.proposal_id == p.id, ApprovalConfirmation.status == "awaiting", ApprovalConfirmation.expires_at > now
                )
            )
        ).scalars().first()
        if existing is not None and p.status == "awaiting_confirmation":
            return existing
        if p.status != "pending":
            raise AppError(ErrorCode.proposal_not_pending, f"This proposal is already {p.status.replace('_', ' ')}.", 409)
        final = params.final_pct if params.final_pct is not None else p.proposed_pct
        conf = ApprovalConfirmation(
            proposal_id=p.id, shop_id=shop_id, final_pct=final, params=params.as_json(), status="awaiting",
            requested_via_token_id=token_id, expires_at=now + CONFIRMATION_TTL, created_at=now,
        )
        s.add(conf)
        p.status = "awaiting_confirmation"
        await s.flush()
        await audit.record(
            s, shop_id=shop_id, action="approval.confirmation_requested", actor_kind="mcp", entity_type="proposal",
            entity_id=p.id, channel="mcp", data={"confirmation_id": conf.id, "final_pct": final},
        )
        await outbox.emit(
            s, outbox.CONFIRMATION_REQUESTED,
            {"confirmation_id": conf.id, "proposal_id": p.id, "shop_id": shop_id, "final_pct": final},
        )
    outbox.kick()
    return conf


async def confirm_confirmation(shop_id: uuid.UUID, confirmation_id: uuid.UUID, *, user_id: uuid.UUID) -> tuple[Offer, Proposal]:
    """Needs a dashboard session. This click is what publishes an MCP-requested approval."""
    async with session_scope() as s:
        conf = await s.get(ApprovalConfirmation, confirmation_id)
        if conf is None or conf.shop_id != shop_id:
            raise not_found("That confirmation")
        if conf.status != "awaiting":
            raise AppError(ErrorCode.confirmation_not_awaiting, "This confirmation is no longer waiting.", 409)
        if conf.expires_at <= clock.now():
            await _expire_confirmation(s, conf)
            await s.commit()
            raise AppError(ErrorCode.confirmation_expired, "That confirmation expired. Ask again from your assistant.", 409)
        proposal_id, params = conf.proposal_id, ApproveParams.from_json(conf.params)
    return await approve_proposal(
        shop_id, proposal_id, user_id=user_id, channel=CHANNEL_MCP, params=params,
        allowed_statuses=("awaiting_confirmation",), confirmation_id=confirmation_id,
    )


async def decline_confirmation(shop_id: uuid.UUID, confirmation_id: uuid.UUID, *, user_id: uuid.UUID) -> Proposal:
    async with session_scope() as s:
        conf = (await s.execute(select(ApprovalConfirmation).where(ApprovalConfirmation.id == confirmation_id).with_for_update())).scalar_one_or_none()
        if conf is None or conf.shop_id != shop_id:
            raise not_found("That confirmation")
        if conf.status != "awaiting":
            raise AppError(ErrorCode.confirmation_not_awaiting, "This confirmation is no longer waiting.", 409)
        p = (await s.execute(select(Proposal).where(Proposal.id == conf.proposal_id).with_for_update())).scalar_one()
        conf.status, conf.decided_at = "declined", clock.now()
        if p.status == "awaiting_confirmation":
            p.status = "pending"
        await audit.record(
            s, shop_id=shop_id, action="approval.confirmation_declined", actor_user_id=user_id, entity_type="proposal",
            entity_id=p.id, channel=CHANNEL_DASHBOARD, data={"confirmation_id": conf.id},
        )
        await outbox.emit(s, outbox.PROPOSAL_CREATED, {"proposal_id": p.id, "shop_id": shop_id, "source": p.source, "resurfaced": True})
    outbox.kick()
    return p


async def _expire_confirmation(s: AsyncSession, conf: ApprovalConfirmation) -> None:
    conf.status, conf.decided_at = "expired", clock.now()
    p = (await s.execute(select(Proposal).where(Proposal.id == conf.proposal_id).with_for_update())).scalar_one_or_none()
    if p is not None and p.status == "awaiting_confirmation":
        p.status = "pending"
    await audit.record(
        s, shop_id=conf.shop_id, action="approval.confirmation_expired", actor_kind="system", entity_type="proposal",
        entity_id=conf.proposal_id, channel="mcp", data={"confirmation_id": conf.id},
    )


# ── time-based sweeps ────────────────────────────────────────────────────
async def expire_proposals(now: datetime | None = None) -> dict[str, int]:
    """Pending proposals whose window has started → expired. Unconfirmed MCP approvals (10 min) → pending."""
    now = now or clock.now()
    counts = {"proposals": 0, "confirmations": 0}
    async with session_scope() as s:
        confs = (
            await s.execute(select(ApprovalConfirmation).where(ApprovalConfirmation.status == "awaiting", ApprovalConfirmation.expires_at <= now))
        ).scalars().all()
        for c in confs:
            await _expire_confirmation(s, c)
            counts["confirmations"] += 1
        await s.flush()
        props = (
            await s.execute(
                select(Proposal).where(Proposal.status.in_(("pending", "awaiting_confirmation")), Proposal.window_start <= now)
            )
        ).scalars().all()
        for p in props:
            p.status = "expired"
            p.decided_at = now
            await audit.record(s, shop_id=p.shop_id, action="proposal.expired", actor_kind="system", entity_type="proposal", entity_id=p.id)
            await outbox.emit(
                s, "proposal.expired", {"proposal_id": p.id, "shop_id": p.shop_id}
            )
            counts["proposals"] += 1
    if counts["proposals"] or counts["confirmations"]:
        outbox.kick()
    return counts


async def end_offers(now: datetime | None = None) -> int:
    """Offers past their end time → ended + offer.ended."""
    now = now or clock.now()
    n = 0
    async with session_scope() as s:
        rows = (await s.execute(select(Offer).where(Offer.status == "active", Offer.ends_at <= now).with_for_update())).scalars().all()
        for o in rows:
            o.status, o.ended_reason = "ended", "time_up"
            await outbox.emit(s, outbox.OFFER_ENDED, {"offer_id": o.id, "shop_id": o.shop_id, "reason": "time_up"})
            n += 1
    if n:
        outbox.kick()
    return n


async def end_offer_now(shop_id: uuid.UUID, offer_id: uuid.UUID, *, user_id: uuid.UUID | None) -> Offer:
    async with session_scope() as s:
        o = (await s.execute(select(Offer).where(Offer.id == offer_id).with_for_update())).scalar_one_or_none()
        if o is None or o.shop_id != shop_id:
            raise not_found("That offer")
        if o.status in ("active", "sold_out"):
            o.status, o.ended_reason = "ended", "shopkeeper"
            await audit.record(s, shop_id=shop_id, action="offer.ended", actor_user_id=user_id, entity_type="offer", entity_id=o.id, channel=CHANNEL_DASHBOARD, data={"reason": "shopkeeper"})
            await outbox.emit(s, outbox.OFFER_ENDED, {"offer_id": o.id, "shop_id": shop_id, "reason": "shopkeeper"})
    outbox.kick()
    return o
