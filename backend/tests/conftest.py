"""Test fixtures: a throwaway SQLite database, an in-process API client, and helpers to onboard a shop."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")
os.environ["VAPID_PUBLIC_KEY"] = os.environ["VAPID_PRIVATE_KEY"] = ""  # tests never depend on the developer's real push keys


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch):
    """Fresh database + settings for every test."""
    from shopnod_core import breaker, clock, db, dispatch, redis_util
    from shopnod_core.models import Base
    from shopnod_core.settings import reset_settings_cache

    pg = os.environ.get("SHOPNOD_TEST_DATABASE_URL")  # run the whole suite on a real Postgres
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    if pg:
        url = pg.replace("postgresql://", "postgresql+asyncpg://", 1).replace("postgres://", "postgresql+asyncpg://", 1)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("WEATHER_ENABLED", "false")  # tests never call the network
    monkeypatch.setenv("SIM_REDEEM_MIN_S", "0")
    monkeypatch.setenv("SIM_REDEEM_MAX_S", "0")
    monkeypatch.setenv("SIM_BURST_SPAN_S", "0")
    reset_settings_cache()
    await db.dispose_engine()
    engine = create_async_engine(url)
    db.configure_engine(engine)
    async with engine.begin() as conn:
        if pg:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    redis_util.set_client(None)
    redis_util.reset_local_state()
    breaker.reset_all()
    clock.set_fixed(DEFAULT_NOW)
    dispatch._pending_inline.clear()
    from shopnod_core import shopper as _sh

    _sh.clear_feed_cache()
    from shopnod_core import context as _ctx
    from shopnod_core import predict as _pr

    _ctx.clear_weather_cache()
    _pr.clear_caches()
    yield url
    from shopnod_core import outbox

    await outbox.wait_background()
    await dispatch.wait_inline()
    clock.reset()
    await db.dispose_engine()
    reset_settings_cache()


@pytest_asyncio.fixture
async def client(env):
    from shopnod_api.main import create_app

    app = create_app()
    import shopnod_worker.tasks.ops  # noqa: F401
    import shopnod_worker.tasks.shop  # noqa: F401
    import shopnod_worker.tasks.shopper  # noqa: F401
    import shopnod_worker.tasks.sim  # noqa: F401

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
        yield c


async def settle() -> None:
    """Let inline tasks and outbox drains finish (stand-in for the worker)."""
    from shopnod_core import dispatch, outbox

    for _ in range(3):
        await dispatch.wait_inline()
        await outbox.wait_background()
        await outbox.drain()


def idem() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


class Shopkeeper:
    """A logged-in demo shopkeeper with a completed Demo Market shop."""

    def __init__(self, client: httpx.AsyncClient, shop: dict):
        self.c = client
        self.shop = shop
        self.shop_id = shop["id"]

    async def quiet(self, simulated: bool = False) -> dict:
        r = await self.c.post("/v1/shop/demo/simulate-quiet" if simulated else "/v1/shop/signals/quiet")
        assert r.status_code == 202, r.text
        await settle()
        return r.json()

    async def inbox(self, status: str | None = None) -> list[dict]:
        r = await self.c.get("/v1/shop/proposals", params={"status": status} if status else None)
        assert r.status_code == 200, r.text
        return r.json()

    async def approve(self, pid: str, body: dict | None = None, key: dict | None = None):
        return await self.c.post(f"/v1/shop/proposals/{pid}/approve", json=body or {}, headers=key or idem())


async def onboard(client: httpx.AsyncClient, category: str = "bakery", name: str = "Test Bakery") -> Shopkeeper:
    r = await client.post("/v1/auth/demo-login")
    assert r.status_code == 200, r.text
    r = await client.post("/v1/shop/shops", json={"name": name, "category": category})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = await client.put(f"/v1/shop/shops/{sid}/location", json={"market": "demo"})
    assert r.status_code == 200, r.text
    r = await client.post(f"/v1/shop/shops/{sid}/apply-template", json={})
    assert r.status_code == 200, r.text
    r = await client.post(f"/v1/shop/shops/{sid}/complete")
    assert r.status_code == 200, r.text
    await settle()
    return Shopkeeper(client, r.json()["shop"])


@pytest_asyncio.fixture
async def shopkeeper(client):
    return await onboard(client)


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=UTC)


DEFAULT_NOW = utc(2026, 3, 10, 6, 0)  # Tuesday 11:00 in Asia/Karachi (UTC+5): inside opening hours, not a quiet hour
NOW = DEFAULT_NOW
_ = timedelta


async def outbox_errors() -> list[tuple[str, str]]:
    """Handlers that failed (any row with a last_error) - tests assert this stays empty on happy paths."""
    from sqlalchemy import select

    from shopnod_core.db import session_scope
    from shopnod_core.models import Outbox

    async with session_scope() as s:
        return [(o.topic, o.last_error) for o in (await s.execute(select(Outbox))).scalars() if o.last_error]
