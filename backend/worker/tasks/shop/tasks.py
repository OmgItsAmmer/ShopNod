"""Plan 2 background tasks: Shop Agent, signals, sweeps, learning. Each has a Celery task and an inline twin."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from shopnod_core import dispatch, learning, proposals, signals
from shopnod_core.agents.shop_agent import run_shop_agent
from shopnod_core.db import session_scope
from shopnod_core.models import Shop
from shopnod_worker.celery_app import celery_app, run_async

from . import handlers  # noqa: F401  (registers outbox handlers)


@dispatch.inline("shop.run_shop_agent")
async def run_shop_agent_async(shop_id: str, signal_id: str | None = None):
    return await run_shop_agent(uuid.UUID(shop_id), uuid.UUID(signal_id) if signal_id else None)


@celery_app.task(name="shop.run_shop_agent", bind=True, max_retries=2, default_retry_delay=5)
def run_shop_agent_task(self, shop_id: str, signal_id: str | None = None):
    return run_async(run_shop_agent_async(shop_id, signal_id))


@dispatch.inline("shop.detect_quiet")
async def detect_quiet_async():
    return [str(x) for x in await signals.detect_quiet()]


@celery_app.task(name="shop.detect_quiet")
def detect_quiet_task():
    return run_async(detect_quiet_async())


@dispatch.inline("shop.expiry_sweep")
async def expiry_sweep_async():
    return [str(x) for x in await signals.expiry_sweep()]


@celery_app.task(name="shop.expiry_sweep")
def expiry_sweep_task():
    return run_async(expiry_sweep_async())


@dispatch.inline("shop.expire_proposals")
async def expire_proposals_async():
    return await proposals.expire_proposals()


@celery_app.task(name="shop.expire_proposals")
def expire_proposals_task():
    return run_async(expire_proposals_async())


@dispatch.inline("shop.end_offers")
async def end_offers_async():
    return await proposals.end_offers()


@celery_app.task(name="shop.end_offers")
def end_offers_task():
    return run_async(end_offers_async())


@dispatch.inline("shop.update_learning")
async def update_learning_async(proposal_id: str):
    async with session_scope() as s:
        return await learning.update_learning(s, uuid.UUID(proposal_id))


@celery_app.task(name="shop.update_learning")
def update_learning_task(proposal_id: str):
    return run_async(update_learning_async(proposal_id))


@dispatch.inline("shop.recompute_learning")
async def recompute_learning_async():
    n = 0
    async with session_scope() as s:
        for sid in (await s.execute(select(Shop.id).where(Shop.onboarding_status == "complete"))).scalars().all():
            await learning.recompute_learning(s, sid)
            n += 1
    return n


@celery_app.task(name="shop.recompute_learning")
def recompute_learning_task():
    return run_async(recompute_learning_async())
