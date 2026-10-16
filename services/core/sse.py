"""Server-Sent Events fan-out. Messages are `{type, data}` with a heartbeat every 15 s.

With Redis, events go through pub/sub so any api replica can deliver them.
Without Redis, an in-process broker is used.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from .redis_util import get_redis

log = logging.getLogger("shopnod.sse")
HEARTBEAT_S = 15.0

_local_subs: dict[str, set[asyncio.Queue]] = {}


def shop_channel(shop_id: Any) -> str:
    return f"sse:shop:{shop_id}"


def shopper_channel(install_id: Any) -> str:
    return f"sse:shopper:{install_id}"


async def publish(channel: str, type_: str, data: dict[str, Any]) -> None:
    msg = json.dumps({"type": type_, "data": data}, default=str)
    r = get_redis()
    if r is not None:
        try:
            await r.publish(channel, msg)
            return
        except Exception:  # noqa: BLE001
            log.warning("redis publish failed; delivering locally")
    for q in list(_local_subs.get(channel, ())):
        q.put_nowait(msg)


async def publish_shop(shop_id: Any, type_: str, data: dict[str, Any]) -> None:
    await publish(shop_channel(shop_id), type_, data)


async def subscribe(channel: str, heartbeat_s: float = HEARTBEAT_S) -> AsyncIterator[str]:
    """Yield raw JSON message strings; yields `""` as a heartbeat tick."""
    r = get_redis()
    if r is not None:
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=heartbeat_s)
                yield m["data"] if m and m.get("data") else ""
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
    else:
        q: asyncio.Queue = asyncio.Queue()
        _local_subs.setdefault(channel, set()).add(q)
        try:
            while True:
                try:
                    yield await asyncio.wait_for(q.get(), timeout=heartbeat_s)
                except asyncio.TimeoutError:
                    yield ""
        finally:
            _local_subs.get(channel, set()).discard(q)


async def event_stream(channel: str, heartbeat_s: float = HEARTBEAT_S) -> AsyncIterator[bytes]:
    """SSE wire format for StreamingResponse."""
    yield b": connected\n\n"
    async for raw in subscribe(channel, heartbeat_s):
        if raw == "":
            yield b": heartbeat\n\n"
        else:
            yield f"data: {raw}\n\n".encode()
