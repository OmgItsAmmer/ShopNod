"""Admin / demo controls (shop users with is_admin; demo logins are admins when DEMO_MODE is on)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import AdminStatusOut, AgentRunOut, FlagIn, OkOut, SimIn
from shopnod_core import audit, auth, breaker, flags, outbox
from shopnod_core.db import DB
from shopnod_core.models import AgentRun, Outbox
from shopnod_core.redis_util import get_redis

router = APIRouter()


@router.post("/ai-outage", response_model=OkOut)
async def ai_outage(body: FlagIn, su: auth.ShopUser = Depends(auth.admin_user), db: AsyncSession = DB):
    """Turn the 'simulate AI outage' flag on or off. Both agents then use their rules fallback."""
    await flags.set_flag(db, flags.AI_OUTAGE, body.enabled)
    await audit.record(db, shop_id=su.shop.id if su.shop else None, action="admin.ai_outage", actor_user_id=su.user.id, channel="dashboard", data={"enabled": body.enabled})
    return OkOut()


@router.post("/sim", response_model=OkOut)
async def sim(body: SimIn, su: auth.ShopUser = Depends(auth.admin_user), db: AsyncSession = DB):
    """Simulated shoppers on/off (they are built in Plan 3). 'burst' asks for 5 redemptions in 20 s."""
    if body.enabled is not None:
        await flags.set_flag(db, flags.SIM_ENABLED, body.enabled)
    if body.burst:
        await outbox.emit(db, "sim.burst", {"shop_id": su.shop.id if su.shop else None})
    await audit.record(db, shop_id=su.shop.id if su.shop else None, action="admin.sim", actor_user_id=su.user.id, channel="dashboard", data={"enabled": body.enabled, "burst": body.burst})
    return OkOut()


@router.get("/status", response_model=AdminStatusOut)
async def status(su: auth.ShopUser = Depends(auth.admin_user), db: AsyncSession = DB):
    rows = (await db.execute(select(Outbox.status, func.count()).group_by(Outbox.status))).all()
    counts = {"pending": 0, "sent": 0, "dead": 0} | {s: int(n) for s, n in rows}
    qlen = None
    r = get_redis()
    if r is not None:
        try:
            qlen = int(await r.llen("celery"))
        except Exception:  # noqa: BLE001
            qlen = None
    runs = (await db.execute(select(AgentRun).order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(10))).scalars().all()
    return AdminStatusOut(
        outbox=counts,
        breakers=breaker.all_states(),
        queue_length=qlen,
        flags={"ai_outage": await flags.get_flag(flags.AI_OUTAGE, db), "sim_enabled": await flags.get_flag(flags.SIM_ENABLED, db)},
        last_agent_runs=[
            AgentRunOut(
                id=x.id, agent=x.agent, shop_id=x.shop_id, input_summary=x.input_summary, tool_calls=x.tool_calls or [], output=x.output,
                latency_ms=x.latency_ms, tokens=x.tokens, cost_micro_usd=x.cost_micro_usd, fallback_used=x.fallback_used,
                fallback_reason=x.fallback_reason, error=x.error, created_at=x.created_at,
            )
            for x in runs
        ],
    )
