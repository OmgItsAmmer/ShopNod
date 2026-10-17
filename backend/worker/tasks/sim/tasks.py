"""Plan 3 simulated shoppers: outbox handlers and the delayed redeem task."""
from __future__ import annotations

import uuid

from shopnod_core import dispatch, outbox
from shopnod_worker.celery_app import celery_app, run_async

from . import sim


@outbox.handler(outbox.OFFER_PUBLISHED, "sim_react")
async def on_offer_published(p: dict) -> None:
    await sim.react(uuid.UUID(str(p["offer_id"])))


@outbox.handler("sim.burst", "sim_burst")
async def on_burst(p: dict) -> None:
    await sim.burst(uuid.UUID(str(p["shop_id"])) if p.get("shop_id") else None)


@dispatch.inline("sim.redeem")
async def redeem_async(claim_id: str):
    return await sim.redeem_claim(uuid.UUID(claim_id))


@celery_app.task(name="sim.redeem")
def redeem_task(claim_id: str):
    return run_async(redeem_async(claim_id))


@dispatch.inline("sim.seed_shoppers")
async def seed_async(n: int | None = None):
    return await sim.seed_shoppers(n)


@celery_app.task(name="sim.seed_shoppers")
def seed_task(n: int | None = None):
    return run_async(seed_async(n))
