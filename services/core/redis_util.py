"""Redis access with a graceful in-process fallback (tests / `REDIS_URL` unset).

Used for per-shop agent locks, rate limits and SSE fan-out.
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from .settings import get_settings

log = logging.getLogger("shopnod.redis")
_client = None
_override = None


def set_client(client) -> None:
    """Inject a (fake) redis client for tests."""
    global _override, _client
    _override = client
    _client = None


def get_redis():
    """Return an asyncio redis client or None when REDIS_URL is not configured."""
    global _client
    if _override is not None:
        return _override
    url = get_settings().REDIS_URL
    if not url:
        return None
    if _client is None:
        import redis.asyncio as aioredis

        _client = aioredis.from_url(url, decode_responses=True)
    return _client


# ── In-process fallbacks ─────────────────────────────────────────────────
_local_locks: dict[str, float] = {}
_local_buckets: dict[str, list[float]] = {}


def reset_local_state() -> None:
    _local_locks.clear()
    _local_buckets.clear()


@asynccontextmanager
async def try_lock(name: str, ttl_s: int = 60) -> AsyncIterator[bool]:
    """Non-blocking lock. Yields True if acquired, False if someone else holds it."""
    r = get_redis()
    if r is not None:
        try:
            token = str(time.time_ns())
            got = await r.set(f"lock:{name}", token, nx=True, ex=ttl_s)
        except Exception:  # redis down: fall back to local
            log.warning("redis lock failed, using local lock")
            r = None
        else:
            try:
                yield bool(got)
            finally:
                if got:
                    try:
                        if await r.get(f"lock:{name}") == token:
                            await r.delete(f"lock:{name}")
                    except Exception:
                        pass
            return
    now = time.monotonic()
    held_until = _local_locks.get(name, 0.0)
    if held_until > now:
        yield False
        return
    _local_locks[name] = now + ttl_s
    try:
        yield True
    finally:
        _local_locks.pop(name, None)


async def rate_limit(key: str, limit: int, window_s: int = 60) -> bool:
    """True if the call is allowed."""
    r = get_redis()
    if r is not None:
        try:
            k = f"rl:{key}:{int(time.time() // window_s)}"
            n = await r.incr(k)
            if n == 1:
                await r.expire(k, window_s + 1)
            return n <= limit
        except Exception:
            log.warning("redis rate limit failed, using local bucket")
    now = time.monotonic()
    hits = [t for t in _local_buckets.get(key, []) if now - t < window_s]
    if len(hits) >= limit:
        _local_buckets[key] = hits
        return False
    hits.append(now)
    _local_buckets[key] = hits
    return True


async def sleep(s: float) -> None:
    await asyncio.sleep(s)
