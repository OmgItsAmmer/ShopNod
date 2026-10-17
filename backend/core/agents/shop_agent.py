"""The Shop Agent flow (Plan 2 Phase 3).

signal → run_shop_agent → lock → stop checks → AI via MCP tools (agent:propose token; its only write
tool is submit_proposal) → on any failure the rules fallback → validator → pending proposal → SSE + push.
The agent has NO way to publish an offer.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from .. import ai, auth, clock, learning, proposals, shop_tools
from ..db import session_scope
from ..guardrails import RuleItem, rules_proposal
from ..guardrails.validator import remaining_budget
from ..ids import uuid7
from ..models import Proposal, Shop, Signal
from ..redis_util import try_lock
from ..settings import get_settings
from ..shop_data import build_context, item_facts, load_items, overlapping_active_offer, pending_proposal
from .openai_runner import run_openai_agent

log = logging.getLogger("shopnod.shop_agent")

AGENT_TOOLS = [
    "get_shop_profile", "get_guardrails", "get_activity", "get_expiring_items", "get_decision_history", "submit_proposal",
]

INSTRUCTIONS = """You are the ShopNod Shop Agent for one local shop. Draft ONE discount proposal for the shopkeeper to review.
You can only read data and call submit_proposal. You cannot publish anything: the shopkeeper decides.
Steps: call get_shop_profile, get_guardrails, get_activity, get_expiring_items and get_decision_history, then call
submit_proposal exactly once with item_ids (from the shop's items), pct, window_start/window_end (ISO times, inside
allowed hours, in the future), cap and a plain 1-2 sentence reason using only real numbers from the tools.
Respect the guardrails: max discount %, never-discount items, allowed hours, and learn from the decision history
(use the learned % for the category when there is one). Prefer items that expire soon. Be conservative.
Reason example: "Quiet for 40 min, 38% below a normal Tuesday. 12 croissants expire tonight." """


class ShopAgentOutput(BaseModel):
    proposal_submitted: bool
    proposal_id: str | None = None
    summary: str = ""


async def stop_reason(session, shop: Shop, now: datetime) -> str | None:
    """Reasons to not even try: pending proposal, overlapping active offer, budget used up, max offers reached."""
    if await pending_proposal(session, shop.id) is not None:
        return "proposal_already_pending"
    if await overlapping_active_offer(session, shop.id, now) is not None:
        return "active_offer_overlaps"
    ctx = await build_context(session, shop, now)
    rem = remaining_budget(ctx)
    if rem is not None and rem <= 0:
        return "budget_used_up"
    if ctx.offers_today >= ctx.limits.max_offers_per_day:
        return "max_offers_reached"
    return None


def _quiet_note(sig: Signal | None) -> str | None:
    if sig is None:
        return None
    if sig.type == "manual":
        return "You said it's quiet right now."
    if sig.type in ("quiet", "simulated") and sig.baseline and sig.observed is not None:
        below = max(0, round((1 - sig.observed / sig.baseline) * 100)) if sig.baseline else 0
        return f"Quiet: {below}% below a normal hour."
    if sig.type == "quiet":
        return "This hour is marked quiet."
    return None


async def rules_fallback(shop_id: uuid.UUID, signal_id: uuid.UUID | None, run_id: uuid.UUID) -> ShopAgentOutput:
    """Rule-based proposal, still validated and still pending for the human."""
    now = clock.now()
    async with session_scope() as s:
        shop = await s.get(Shop, shop_id)
        # The AI may have already submitted before timing out: do not create a second proposal.
        existing = (await s.execute(select(Proposal).where(Proposal.agent_run_id == run_id))).scalars().first()
        if existing is not None:
            return ShopAgentOutput(proposal_submitted=True, proposal_id=str(existing.id), summary="ai")
        sig = await s.get(Signal, signal_id) if signal_id else None
        trace = ai.current_trace.get()
        if trace is not None:  # same read tools the AI would call, so the trace shows what the proposal was based on
            agent_p = auth.Principal("agent", shop_id, frozenset({auth.SCOPE_AGENT_PROPOSE}))
            for name in ("get_shop_profile", "get_guardrails", "get_activity", "get_expiring_items", "get_decision_history"):
                trace.tool(name, {"via": "rules fallback"}, await getattr(shop_tools, name)(s, agent_p))
        items = await load_items(s, shop_id)
        rule_items = [RuleItem(item_facts(i, []), i.expires_at, i.quantity) for i in items]
        ctx = await build_context(s, shop, now)
        result = rules_proposal(
            rule_items, await learning.learned_pct(s, shop_id), now, ctx.limits,
            lead_minutes=get_settings().PROPOSAL_LEAD_MINUTES, quiet_note=_quiet_note(sig),
        )
        if result is None:
            return ShopAgentOutput(proposal_submitted=False, summary="nothing eligible to offer")
        created = await proposals.create_proposal(
            s, shop, result.draft, reason=result.reason, source="rules", signal_id=signal_id,
            agent_run_id=run_id, actor_kind="system", now=now,
        )
        if created.proposal is None:
            return ShopAgentOutput(proposal_submitted=False, summary=f"blocked by guardrails: {created.rejected_reason}")
        if trace is not None:
            trace.tool("submit_proposal", {"via": "rules fallback", "pct": result.draft.pct}, {"status": "pending", "proposal_id": str(created.proposal.id)})
        return ShopAgentOutput(proposal_submitted=True, proposal_id=str(created.proposal.id), summary="rules")


async def run_shop_agent(shop_id: uuid.UUID, signal_id: uuid.UUID | None) -> dict[str, Any]:
    settings = get_settings()
    async with try_lock(f"agent:shop:{shop_id}", 60) as got:
        if not got:
            return {"skipped": "locked"}
        now = clock.now()
        async with session_scope() as s:
            shop = await s.get(Shop, shop_id)
            if shop is None or shop.onboarding_status != "complete":
                return {"skipped": "shop_not_ready"}
            why = await stop_reason(s, shop, now)
            sig = await s.get(Signal, signal_id) if signal_id else None
        if why:
            log.info("shop agent stopped", extra={"shop_id": str(shop_id), "reason": why})
            return {"skipped": why}

        run_id = uuid7()
        sig_desc = f"{sig.type} signal" if sig else "manual run"
        summary = f"{sig_desc} for shop {shop.name}"

        async def runner(trace: ai.RunTrace):
            token = auth.create_agent_token(shop_id, run_id=str(run_id))
            out = await run_openai_agent(
                trace,
                name="ShopAgent",
                instructions=INSTRUCTIONS,
                user_input=(
                    f"Signal: {sig.type if sig else 'manual'} "
                    f"(baseline={sig.baseline if sig else None}, observed={sig.observed if sig else None}). "
                    f"Current UTC time: {now.isoformat()}. Draft one proposal."
                ),
                output_type=ShopAgentOutput,
                model=settings.OPENAI_MODEL_AGENT,
                mcp_token=token,
                allowed_tools=AGENT_TOOLS,
                max_tool_calls=6,
            )
            async with session_scope() as s2:  # trust the database, not the model's claim
                made = (await s2.execute(select(Proposal).where(Proposal.agent_run_id == run_id))).scalars().first()
            if made is None:
                raise RuntimeError("agent did not submit a proposal")
            return ShopAgentOutput(proposal_submitted=True, proposal_id=str(made.id), summary=out.summary)

        result = await ai.run_structured(
            "shop_agent", summary, ShopAgentOutput, runner=runner,
            fallback=lambda: rules_fallback(shop_id, signal_id, run_id),
            timeout_s=settings.AGENT_TIMEOUT_S, shop_id=shop_id, run_id=run_id,
        )
        return {
            "run_id": str(run_id),
            "fallback_used": result.fallback_used,
            "proposal_id": result.output.proposal_id,
            "reason": result.reason,
        }
