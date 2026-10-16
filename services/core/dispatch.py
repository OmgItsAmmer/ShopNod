"""Enqueue background work. With Redis: Celery. Without: run in-process (local dev / tests)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from .settings import get_settings

log = logging.getLogger("shopnod.dispatch")
INLINE: dict[str, Callable[..., Awaitable[Any]]] = {}
_background: set[asyncio.Task] = set()
_pending_inline: list[asyncio.Task] = []


def inline(name: str):
    """Register the coroutine used to run task `name` when there is no Celery broker."""

    def deco(fn):
        INLINE[name] = fn
        return fn

    return deco


def enqueue(name: str, *args: Any) -> None:
    """Fire-and-forget. `name` is the Celery task name (e.g. 'shop.run_shop_agent')."""
    if get_settings().REDIS_URL:
        try:
            from shopnod_worker.celery_app import celery_app

            celery_app.send_task(name, args=list(args))
            return
        except Exception:  # noqa: BLE001
            log.warning("celery enqueue failed; running inline", extra={"task": name})
    fn = INLINE.get(name)
    if fn is None:
        _import_worker_tasks()
        fn = INLINE.get(name)
    if fn is None:
        log.error("no inline handler for task", extra={"task": name})
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_run(name, fn, args))
    _background.add(task)
    _pending_inline.append(task)
    task.add_done_callback(_background.discard)


def _import_worker_tasks() -> None:
    try:
        import shopnod_worker.tasks.shop  # noqa: F401
        import shopnod_worker.tasks.ops  # noqa: F401
    except Exception:  # noqa: BLE001
        log.exception("could not import worker tasks")


async def _run(name: str, fn, args) -> None:
    try:
        await fn(*args)
    except Exception:  # noqa: BLE001
        log.exception("inline task failed", extra={"task": name})


async def wait_inline() -> None:
    """Tests: wait for inline tasks started so far."""
    while _pending_inline:
        t = _pending_inline.pop()
        if not t.done():
            await t
