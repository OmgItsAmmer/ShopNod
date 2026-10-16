"""Celery app + beat schedule. Run: `celery -A shopnod_worker.celery_app worker -B` (beat in exactly 1 replica)."""
from __future__ import annotations

import asyncio
import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from shopnod_core.logging_setup import setup_logging
from shopnod_core.settings import get_settings

log = logging.getLogger("shopnod.worker")
_s = get_settings()

celery_app = Celery("shopnod", broker=_s.REDIS_URL or "memory://", backend=None, include=[
    "shopnod_worker.tasks.ops.tasks",
    "shopnod_worker.tasks.shop.tasks",
])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "process-outbox": {"task": "ops.process_outbox", "schedule": 5.0},
        "end-offers": {"task": "shop.end_offers", "schedule": 60.0},
        "expire-proposals": {"task": "shop.expire_proposals", "schedule": 300.0},
        "detect-quiet": {"task": "shop.detect_quiet", "schedule": 300.0},
        "expiry-sweep": {"task": "shop.expiry_sweep", "schedule": 900.0},
        "recompute-learning": {"task": "shop.recompute_learning", "schedule": crontab(hour=2, minute=0)},
        "purge-idempotency": {"task": "ops.purge_idempotency", "schedule": crontab(hour=3, minute=30)},
    },
)


@worker_process_init.connect
def _init(**_):
    setup_logging(get_settings().LOG_LEVEL)


def run_async(coro):
    """Run a coroutine from a sync Celery task with a fresh engine per call (event loops are per task)."""
    from shopnod_core import db

    async def _wrapped():
        try:
            return await coro
        finally:
            await db.dispose_engine()

    return asyncio.run(_wrapped())
