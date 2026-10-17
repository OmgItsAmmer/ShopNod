"""Plan 1 background tasks: nightly retention sweep and affinity recompute. Each has a Celery task and an inline twin."""
from __future__ import annotations

from sqlalchemy import select

from shopnod_core import dispatch
from shopnod_core import shopper as sh
from shopnod_core.db import session_scope
from shopnod_core.models import Shopper
from shopnod_worker.celery_app import celery_app, run_async

from . import handlers  # noqa: F401  (registers outbox handlers)
from .matching import match_and_notify


@dispatch.inline("shopper.match_and_notify")
async def match_and_notify_async(offer_id: str):
    import uuid

    return await match_and_notify(uuid.UUID(offer_id))


@celery_app.task(name="shopper.match_and_notify")
def match_and_notify_task(offer_id: str):
    return run_async(match_and_notify_async(offer_id))


@dispatch.inline("shopper.retention_sweep")
async def retention_sweep_async():
    async with session_scope() as s:
        return await sh.retention_sweep(s)


@celery_app.task(name="shopper.retention_sweep")
def retention_sweep_task():
    return run_async(retention_sweep_async())


@dispatch.inline("shopper.recompute_affinity")
async def recompute_affinity_async():
    n = 0
    async with session_scope() as s:
        ids = (await s.execute(select(Shopper.install_id).where(Shopper.is_simulated.is_(False)))).scalars().all()
    for iid in ids:
        async with session_scope() as s:
            await sh.recompute_affinity(s, iid)
        n += 1
    return n


@celery_app.task(name="shopper.recompute_affinity")
def recompute_affinity_task():
    return run_async(recompute_affinity_async())
