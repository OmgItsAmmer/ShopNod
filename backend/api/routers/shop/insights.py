"""Insights, billing, audit log and the agent trace."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import AgentRunOut, AuditOut, BillingOut, SummaryOut
from shopnod_core import auth, billing, insights
from shopnod_core.db import DB
from shopnod_core.errors import not_found
from shopnod_core.models import AgentRun, AuditLog, Proposal

router = APIRouter()


@router.get("/insights/summary", response_model=SummaryOut)
async def insights_summary(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    return await insights.summary(db, su.shop_required)


@router.get("/insights/learning-curve")
async def learning_curve(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB) -> dict:
    """Data for the learning chart: approval rate per week, average edit, 'next proposal starts at X%'."""
    return await insights.learning_curve(db, su.shop_required)


@router.get("/billing", response_model=BillingOut)
async def get_billing(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    return await billing.overview(db, su.shop_required)



@router.get("/audit", response_model=list[AuditOut])
async def audit_log(limit: int = Query(default=100, le=500), action: str | None = None, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    stmt = select(AuditLog).where(AuditLog.shop_id == su.shop_required.id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    rows = (await db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit))).scalars().all()
    return [AuditOut.model_validate(r, from_attributes=True) for r in rows]


def _run_out(r: AgentRun, proposal_id: uuid.UUID | None = None) -> AgentRunOut:
    return AgentRunOut(
        id=r.id, agent=r.agent, shop_id=r.shop_id, input_summary=r.input_summary, tool_calls=r.tool_calls or [], output=r.output,
        latency_ms=r.latency_ms, tokens=r.tokens, cost_micro_usd=r.cost_micro_usd, fallback_used=r.fallback_used,
        fallback_reason=r.fallback_reason, error=r.error, created_at=r.created_at, proposal_id=proposal_id,
    )


@router.get("/agent-runs", response_model=list[AgentRunOut])
async def agent_runs(limit: int = Query(default=50, le=200), agent: str | None = None, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    stmt = select(AgentRun).where(AgentRun.shop_id == su.shop_required.id)
    if agent:
        stmt = stmt.where(AgentRun.agent == agent)
    rows = (await db.execute(stmt.order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(limit))).scalars().all()
    return [_run_out(r) for r in rows]


@router.get("/agent-runs/{run_id}", response_model=AgentRunOut)
async def agent_run(run_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    r = await db.get(AgentRun, run_id)
    if r is None or r.shop_id != su.shop_required.id:
        raise not_found("That run")
    pid = (await db.execute(select(Proposal.id).where(Proposal.agent_run_id == r.id))).scalars().first()
    return _run_out(r, pid)
