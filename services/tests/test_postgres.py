"""Checks that only make sense on a real Postgres (skipped otherwise):

    SHOPNOD_TEST_DATABASE_URL=postgresql://shopnod:shopnod@localhost:5432/shopnod pytest services/tests/test_postgres.py

(The whole suite also runs on Postgres with that variable set.)
"""
import os
import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(not os.environ.get("SHOPNOD_TEST_DATABASE_URL"), reason="needs a real Postgres")


async def test_required_indexes_and_unique_constraints(env):
    from shopnod_core.db import get_maker

    async with get_maker()() as s:
        idx = {r[0]: r[1] for r in (await s.execute(text("select indexname, indexdef from pg_indexes where schemaname='public'"))).all()}
        defs = " ".join(idx.values()).lower()
        assert "shops" in defs and "(geohash6)" in defs
        assert "(status, ends_at)" in defs  # offers
        # unique claims(token_jti) and redemptions(claim_id)
        uniques = (
            await s.execute(
                text(
                    "select conrelid::regclass::text, pg_get_constraintdef(oid) from pg_constraint "
                    "where contype='u' and connamespace='public'::regnamespace"
                )
            )
        ).all()
        flat = [f"{t} {d}" for t, d in uniques] + [d for d in idx.values() if "UNIQUE" in d]
        joined = " | ".join(flat)
        assert "claims" in joined and "token_jti" in joined
        assert "redemptions" in joined and "claim_id" in joined


async def test_haversine_sql_function_matches_python(env):
    from shopnod_core import geo
    from shopnod_core.db import get_maker

    async with get_maker()() as s:
        await s.execute(text(geo.HAVERSINE_SQL))
        row = (await s.execute(text("select haversine_m(31.5204, 74.3587, 31.5250, 74.3640)"))).scalar_one()
    expected = geo.haversine_m(31.5204, 74.3587, 31.5250, 74.3640)
    assert abs(row - expected) < 1.0
    assert 600 < row < 800


async def test_jsonb_columns_and_uuid_types(env):
    from shopnod_core.db import get_maker

    async with get_maker()() as s:
        cols = {
            (r[0], r[1]): r[2]
            for r in (
                await s.execute(
                    text("select table_name, column_name, data_type from information_schema.columns where table_schema='public'")
                )
            ).all()
        }
    assert cols[("proposals", "items")] == "jsonb"
    assert cols[("shops", "quiet_grid")] == "jsonb"
    assert cols[("proposals", "id")] == "uuid"
    assert cols[("proposals", "window_start")] == "timestamp with time zone"


async def test_row_lock_serialises_concurrent_redemptions(client):
    """Four counters scan the same claim at once on real Postgres (SELECT ... FOR UPDATE + unique claim_id)."""
    import asyncio
    import sys
    from pathlib import Path

    from conftest import onboard, settle

    from shopnod_core import redeem

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "seed"))
    import dev_claim

    sk = await onboard(client)
    await sk.quiet(simulated=True)
    pid = (await sk.inbox())[0]["id"]
    offer = (await sk.approve(pid)).json()["offer"]
    await settle()
    claim = await dev_claim.make_claim(offer["id"])
    results = await asyncio.gather(*[redeem.redeem(uuid.UUID(sk.shop_id), payload=claim["qr_text"]) for _ in range(6)])
    assert sorted(r["result"] for r in results).count("ok") == 1
    assert {r["result"] for r in results} <= {"ok", "already_redeemed"}
