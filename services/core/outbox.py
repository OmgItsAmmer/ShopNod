"""Transactional outbox: events are written in the same transaction as the change,
then a worker sends them to their handlers (Plan 3 §0.6).

Handlers must be safe to run twice. Each handler's completion is tracked per row
(`_done`), so a retry only re-runs the handlers that failed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .db import session_scope
from .jsonutil import jsonable
from .models import Outbox
from .settings import get_settings

log = logging.getLogger("shopnod.outbox")

Handler = Callable[[dict[str, Any]], Awaitable[None]]
_handlers: dict[str, list[tuple[str, Handler]]] = {}
MAX_ATTEMPTS = 5

# Topics (see Plan 3 §0.6)
PROPOSAL_CREATED = "proposal.created"
PROPOSAL_DECIDED = "proposal.decided"
CONFIRMATION_REQUESTED = "confirmation.requested"
OFFER_PUBLISHED = "offer.published"
OFFER_ENDED = "offer.ended"
CLAIM_CREATED = "claim.created"
REDEMPTION_RECORDED = "redemption.recorded"
SHOP_COMPLETED = "shop.completed"  # Plan 2 internal: creates the Stripe customer


def handler(topic: str, name: str):
    """Register `fn(payload)` as a named handler for a topic."""

    def deco(fn: Handler) -> Handler:
        existing = _handlers.setdefault(topic, [])
        existing[:] = [(n, f) for n, f in existing if n != name]  # re-import safe
        existing.append((name, fn))
        return fn

    return deco


def handlers_for(topic: str) -> list[tuple[str, Handler]]:
    return list(_handlers.get(topic, []))


def clear_handlers() -> None:
    _handlers.clear()


async def emit(session: AsyncSession, topic: str, payload: dict[str, Any]) -> Outbox:
    """Add an event to the outbox inside the caller's transaction."""
    row = Outbox(topic=topic, payload=_jsonable(payload), status="pending", next_attempt_at=clock.now())
    session.add(row)
    await session.flush()
    return row


_jsonable = jsonable


def backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(5 * (2 ** max(attempts - 1, 0)), 600))


async def process_outbox(limit: int = 50) -> int:
    """Send due rows. Returns the number of rows fully sent."""
    sent = 0
    async with session_scope() as s:
        stmt = (
            select(Outbox)
            .where(Outbox.status == "pending", Outbox.next_attempt_at <= clock.now())
            .order_by(Outbox.created_at)
            .limit(limit)
        )
        if s.bind is not None and s.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        rows = (await s.execute(stmt)).scalars().all()
        for row in rows:
            payload = dict(row.payload or {})
            done: list[str] = list(payload.get("_done", []))
            failed: str | None = None
            for name, fn in handlers_for(row.topic):
                if name in done:
                    continue
                try:
                    await fn({k: v for k, v in payload.items() if k != "_done"})
                    done.append(name)
                except Exception as exc:  # noqa: BLE001 - handler failures are retried
                    failed = f"{name}: {exc}"
                    log.warning("outbox handler failed", extra={"topic": row.topic, "handler": name})
            payload["_done"] = done
            row.payload = payload
            row.attempts += 1
            if failed is None:
                row.status = "sent"
                row.last_error = None
                sent += 1
            else:
                row.last_error = failed[:500]
                if row.attempts >= MAX_ATTEMPTS:
                    row.status = "dead"
                else:
                    row.next_attempt_at = clock.now() + backoff(row.attempts)
    return sent


async def drain(max_rounds: int = 10) -> int:
    """Process until nothing due remains (tests / inline mode)."""
    total = 0
    for _ in range(max_rounds):
        n = await process_outbox()
        if n == 0:
            break
        total += n
    return total


_background: set[asyncio.Task] = set()


def kick() -> None:
    """Ask for the outbox to be processed soon (after the request's transaction committed)."""
    settings = get_settings()
    if settings.REDIS_URL:
        try:
            from shopnod_worker.celery_app import celery_app  # lazy: api may not ship celery config

            celery_app.send_task("ops.process_outbox")
            return
        except Exception:  # noqa: BLE001
            log.warning("could not enqueue outbox processing; running inline")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_safe_drain())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _safe_drain() -> None:
    try:
        await drain()
    except Exception:  # noqa: BLE001
        log.exception("inline outbox drain failed")


async def wait_background() -> None:
    """Tests: wait for drains started by kick()."""
    while _background:
        await asyncio.gather(*list(_background), return_exceptions=True)
