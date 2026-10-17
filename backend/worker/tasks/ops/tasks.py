"""Operational tasks shared by both sides (Phase 0)."""
from __future__ import annotations

from shopnod_core import db, dispatch, outbox
from shopnod_core.idempotency import purge_expired
from shopnod_worker.celery_app import celery_app, run_async


@dispatch.inline("ops.process_outbox")
async def process_outbox_async() -> int:
    return await outbox.process_outbox()


@celery_app.task(name="ops.process_outbox")
def process_outbox_task() -> int:
    return run_async(process_outbox_async())


async def _purge() -> int:
    async with db.session_scope() as s:
        return await purge_expired(s)


@celery_app.task(name="ops.purge_idempotency")
def purge_idempotency_task() -> int:
    return run_async(_purge())
