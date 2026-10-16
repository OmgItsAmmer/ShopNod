"""Phase 3: the MCP tool layer, token scopes, and the AI Shop Agent flow (with a fake model)."""
import asyncio
import json
import uuid
from datetime import timedelta

import httpx
import pytest

from conftest import onboard, settle
from shopnod_core import auth, clock, flags, shop_tools
from shopnod_core.agents import shop_agent
from shopnod_core.db import session_scope
from shopnod_core.errors import AppError
from shopnod_core.models import AgentRun, Item, Proposal
from shopnod_core.settings import get_settings


async def principal_for(shop_id, kind, scopes=None):
    async with session_scope() as s:
        if kind == "agent":
            return await auth.principal_from_bearer(s, auth.create_agent_token(uuid.UUID(shop_id), run_id=None))
        raw, hashed, prefix = auth.new_pat()
        from shopnod_core.models import PersonalAccessToken

        s.add(PersonalAccessToken(shop_id=uuid.UUID(shop_id), name="t", token_hash=hashed, prefix=prefix, scopes=scopes or []))
        await s.flush()
        return await auth.principal_from_bearer(s, raw)


async def call(tool, p, *args, **kw):
    async with session_scope() as s:
        return await getattr(shop_tools, tool)(s, p, *args, **kw)


async def first_item_ids(shop_id, n=1):
    from sqlalchemy import select

    async with session_scope() as s:
        rows = (await s.execute(select(Item).where(Item.shop_id == uuid.UUID(shop_id)).order_by(Item.name))).scalars().all()
    return [str(r.id) for r in rows[:n]]


def window(minutes_from_now=30, length=60):
    s = clock.now() + timedelta(minutes=minutes_from_now)
    return s.isoformat(), (s + timedelta(minutes=length)).isoformat()


# ── tokens ───────────────────────────────────────────────────────────────
async def test_agent_token_is_scoped_short_lived_and_tied_to_one_shop(client, shopkeeper):
    p = await principal_for(shopkeeper.shop_id, "agent")
    assert p.kind == "agent" and p.scopes == {auth.SCOPE_AGENT_PROPOSE} and str(p.shop_id) == shopkeeper.shop_id
    tok = auth.create_agent_token(uuid.UUID(shopkeeper.shop_id))
    clock.advance(timedelta(minutes=6))
    async with session_scope() as s:
        with pytest.raises(AppError) as e:
            await auth.principal_from_bearer(s, tok)
    assert e.value.status == 401
    async with session_scope() as s:
        with pytest.raises(AppError):
            await auth.principal_from_bearer(s, "snpat_doesnotexist")
        with pytest.raises(AppError):
            await auth.principal_from_bearer(s, "not.a.jwt")


async def test_pat_revoked_or_expired_is_refused(client, shopkeeper):
    r = await client.post("/v1/shop/tokens", json={"name": "Claude", "scopes": ["shopkeeper:approve"], "expires_in_days": 1})
    assert r.status_code == 201
    created = r.json()
    assert created["token"].startswith("snpat_") and set(created["scopes"]) == {"shopkeeper:read", "shopkeeper:approve"}
    cfg = created["mcp_config"]["mcpServers"]["shopnod"]
    assert cfg["type"] == "http" and cfg["url"].endswith("/mcp") and cfg["headers"]["Authorization"] == f"Bearer {created['token']}"
    listed = (await client.get("/v1/shop/tokens")).json()
    assert "token" not in listed[0] and listed[0]["prefix"] == created["token"][:12]  # shown once, stored as a hash
    async with session_scope() as s:
        assert (await auth.principal_from_bearer(s, created["token"])).kind == "pat"
    assert (await client.delete(f"/v1/shop/tokens/{created['id']}")).status_code == 200
    async with session_scope() as s:
        with pytest.raises(AppError):
            await auth.principal_from_bearer(s, created["token"])


# ── scope matrix ─────────────────────────────────────────────────────────
READ_TOOLS = ["get_shop_profile", "get_guardrails", "get_activity", "get_expiring_items", "list_items"]


async def test_agent_token_can_read_and_submit_but_never_approve(client, shopkeeper):
    agent = await principal_for(shopkeeper.shop_id, "agent")
    for t in READ_TOOLS + ["get_decision_history"]:
        assert await call(t, agent) is not None
    ids = await first_item_ids(shopkeeper.shop_id)
    s, e = window()
    res = await call("submit_proposal", agent, ids, 10, s, e, 20, "Quiet hour.")
    assert res["status"] == "pending"
    pid = res["proposal_id"]
    # the proof the plan asks for: the agent token cannot approve (or reject, or read the inbox/stats)
    for tool, args in [("approve_proposal", (pid, 10)), ("reject_proposal", (pid, "other")), ("list_pending_proposals", ()),
                       ("get_offer_stats", (str(uuid.uuid4()),)), ("get_confirmation_status", (str(uuid.uuid4()),))]:
        with pytest.raises(AppError) as exc:
            await call(tool, agent, *args)
        assert exc.value.code.value == "scope_missing" and exc.value.status == 403, tool
    async with session_scope() as sess:
        assert (await sess.get(Proposal, uuid.UUID(pid))).status == "pending"


async def test_shopkeeper_tokens_read_only_cannot_write_or_see_agent_tools(client, shopkeeper):
    reader = await principal_for(shopkeeper.shop_id, "pat", ["shopkeeper:read"])
    for t in READ_TOOLS + ["list_pending_proposals"]:
        assert await call(t, reader) is not None
    ids = await first_item_ids(shopkeeper.shop_id)
    s, e = window()
    with pytest.raises(AppError):
        await call("submit_proposal", reader, ids, 10, s, e, 20, "nope")
    with pytest.raises(AppError):
        await call("get_decision_history", reader)
    for tool, args in [("approve_proposal", (str(uuid.uuid4()), 10)), ("reject_proposal", (str(uuid.uuid4()), "other"))]:
        with pytest.raises(AppError) as exc:
            await call(tool, reader, *args)
        assert exc.value.code.value == "scope_missing"


async def test_tools_refuse_other_shops(client, shopkeeper):
    other = await onboard(client, "grocery", "Other Shop")  # logs in as a second user in the same client
    ids_a = await first_item_ids(shopkeeper.shop_id)
    s, e = window()
    agent_b = await principal_for(other.shop_id, "agent")
    res = await call("submit_proposal", agent_b, ids_a, 10, s, e, 20, "cross-shop attempt")
    assert res["status"] == "blocked" and res["reason"] == "no_items_left"  # shop A's items don't exist for shop B
    # B's proposal can't be read/approved/rejected through A's token
    ids_b = await first_item_ids(other.shop_id)
    created = await call("submit_proposal", agent_b, ids_b, 10, s, e, 20, "ok")
    keeper_a = await principal_for(shopkeeper.shop_id, "pat", ["shopkeeper:read", "shopkeeper:approve"])
    with pytest.raises(AppError) as exc:
        await call("approve_proposal", keeper_a, created["proposal_id"], 10)
    assert exc.value.status == 404
    with pytest.raises(AppError) as exc:
        await call("reject_proposal", keeper_a, created["proposal_id"], "other")
    assert exc.value.status == 404
    assert (await call("list_pending_proposals", keeper_a))["proposals"] == []
    with pytest.raises(AppError):
        await call("get_offer_stats", keeper_a, str(uuid.uuid4()))


async def test_submit_proposal_is_validated_and_only_one_pending(client, shopkeeper):
    agent = await principal_for(shopkeeper.shop_id, "agent")
    ids = await first_item_ids(shopkeeper.shop_id, 2)
    s, e = window()
    big = await call("submit_proposal", agent, ids, 60, s, e, 500, "greedy")
    assert big["status"] == "pending"
    saved = {x["rule"] for x in big["guardrail_saves"]}
    assert {"max_discount_pct", "max_redemptions_per_offer"} <= saved
    with pytest.raises(AppError) as exc:
        await call("submit_proposal", agent, ids, 10, s, e, 20, "second")
    assert exc.value.status == 409
    with pytest.raises(AppError) as exc:
        await call("submit_proposal", agent, ids, 10, "garbage", e, 20, "bad time")
    assert exc.value.status == 422


# ── the real MCP server over Streamable HTTP ────────────────────────────
async def mcp_rpc(client_, method, params, token, id_=1):
    return await client_.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )


async def test_mcp_server_over_http_enforces_scopes(client, shopkeeper):
    from shopnod_mcp.server import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://mcp.test") as m:
            assert (await m.get("/healthz")).json()["status"] == "ok"
            agent_token = auth.create_agent_token(uuid.UUID(shopkeeper.shop_id))
            r = await mcp_rpc(m, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}, agent_token)
            assert r.status_code == 200, r.text
            r = await mcp_rpc(m, "tools/list", {}, agent_token, 2)
            names = {t["name"] for t in r.json()["result"]["tools"]}
            assert {"submit_proposal", "approve_proposal", "get_guardrails"} <= names
            r = await mcp_rpc(m, "tools/call", {"name": "get_guardrails", "arguments": {}}, agent_token, 3)
            body = r.json()["result"]
            assert not body.get("isError"), body
            r = await mcp_rpc(m, "tools/call", {"name": "approve_proposal", "arguments": {"proposal_id": str(uuid.uuid4())}}, agent_token, 4)
            res = r.json()["result"]
            assert res["isError"] and "scope_missing" in json.dumps(res)
            r = await mcp_rpc(m, "tools/call", {"name": "get_guardrails", "arguments": {}}, "snpat_wrong", 5)
            assert r.json()["result"]["isError"] and "unauthorized" in json.dumps(r.json())
            # no Authorization header at all
            r = await m.post("/mcp", json={"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "get_guardrails", "arguments": {}}},
                             headers={"Accept": "application/json, text/event-stream"})
            assert r.json()["result"]["isError"]


# ── the Shop Agent flow ─────────────────────────────────────────────────
@pytest.fixture
def fake_ai(monkeypatch):
    """Pretend OpenAI is available; the 'model' calls submit_proposal through the agent token like the real one."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from shopnod_core.settings import reset_settings_cache

    reset_settings_cache()
    state = {"mode": "ok", "calls": 0}

    async def fake_run(trace, *, mcp_token=None, name="", **_):
        state["calls"] += 1
        if state["mode"] == "error":
            raise RuntimeError("openai exploded")
        if state["mode"] == "slow":
            await asyncio.sleep(5)
        async with session_scope() as s:
            p = await auth.principal_from_bearer(s, mcp_token)
            from sqlalchemy import select

            ids = [str(i.id) for i in (await s.execute(select(Item).where(Item.shop_id == p.shop_id, Item.name == "Croissant"))).scalars()]
            trace.tool("get_guardrails")
            s_, e_ = window(30, 90)
            res = await shop_tools.submit_proposal(s, p, ids, 12, s_, e_, 25, "Quiet for 40 min, 38% below a normal Tuesday. 12 croissants expire tonight.")
            trace.tool("submit_proposal", result=res)
        return shop_agent.ShopAgentOutput(proposal_submitted=True, proposal_id=res.get("proposal_id"), summary="ok")

    monkeypatch.setattr(shop_agent, "run_openai_agent", fake_run)
    return state


async def test_ai_proposal_arrives_via_mcp_tools_with_agent_trace(client, shopkeeper, fake_ai):
    await shopkeeper.quiet(simulated=True)
    p = (await shopkeeper.inbox())[0]
    assert p["source"] == "ai" and p["proposed_pct"] == 12 and "croissants expire tonight" in p["reason"]
    runs = (await client.get("/v1/shop/agent-runs", params={"agent": "shop_agent"})).json()
    assert runs[0]["fallback_used"] is False and runs[0]["latency_ms"] >= 0
    assert [t["tool"] for t in runs[0]["tool_calls"]] == ["get_guardrails", "submit_proposal"]
    detail = (await client.get(f"/v1/shop/agent-runs/{runs[0]['id']}")).json()
    assert detail["proposal_id"] == p["id"] and p["agent_run_id"] == runs[0]["id"]
    assert (await client.get(f"/v1/shop/agent-runs/{uuid.uuid4()}")).status_code == 404


@pytest.mark.parametrize("mode", ["error", "slow"])
async def test_ai_failure_or_timeout_falls_back_to_rules(client, shopkeeper, fake_ai, monkeypatch, mode):
    fake_ai["mode"] = mode
    monkeypatch.setattr(get_settings(), "AGENT_TIMEOUT_S", 0.3)
    await shopkeeper.quiet(simulated=True)
    p = (await shopkeeper.inbox())[0]
    assert p["source"] == "rules"
    run = (await client.get("/v1/shop/agent-runs", params={"agent": "shop_agent"})).json()[0]
    assert run["fallback_used"] is True and run["fallback_reason"] in ("error", "timeout")


async def test_outage_flag_uses_rules_with_honest_label(client, shopkeeper, fake_ai):
    assert (await client.post("/v1/admin/ai-outage", json={"enabled": True})).status_code == 200
    await shopkeeper.quiet(simulated=True)
    p = (await shopkeeper.inbox())[0]
    assert p["source"] == "rules" and fake_ai["calls"] == 0
    run = (await client.get("/v1/shop/agent-runs", params={"agent": "shop_agent"})).json()[0]
    assert run["fallback_used"] is True and run["fallback_reason"] == "ai_outage_flag"


async def test_no_openai_key_runs_on_rules_and_trace_shows_fallback(client, shopkeeper):
    await shopkeeper.quiet(simulated=True)
    assert (await shopkeeper.inbox())[0]["source"] == "rules"
    run = (await client.get("/v1/shop/agent-runs")).json()[0]
    assert run["fallback_used"] is True and run["fallback_reason"] == "no_ai_configured"


async def test_circuit_breaker_opens_after_repeated_ai_failures(client, shopkeeper, fake_ai):
    from shopnod_core.breaker import get_breaker

    fake_ai["mode"] = "error"
    for _ in range(3):
        await shopkeeper.quiet(simulated=True)
        pid = (await shopkeeper.inbox())[0]["id"]
        await client.post(f"/v1/shop/proposals/{pid}/reject", json={"reason": "other"})
    assert get_breaker("openai").state == "open"
    calls = fake_ai["calls"]
    await shopkeeper.quiet(simulated=True)
    assert fake_ai["calls"] == calls  # open breaker: AI is not even tried
    run = (await client.get("/v1/shop/agent-runs")).json()[0]
    assert run["fallback_reason"] == "circuit_open"


async def test_agent_stop_conditions(client, shopkeeper, fake_ai):
    # budget used up
    from shopnod_core.shop_data import load_guardrail

    async with session_scope() as s:
        (await load_guardrail(s, uuid.UUID(shopkeeper.shop_id))).daily_budget_minor = 0
    res = await client.post("/v1/shop/signals/quiet")
    assert res.json()["skipped_reason"] == "budget_used_up"
    await settle()
    assert await shopkeeper.inbox() == [] and fake_ai["calls"] == 0


async def test_redis_lock_blocks_a_second_agent_for_the_same_shop(client, shopkeeper, fake_ai):
    from shopnod_core.redis_util import try_lock

    async with try_lock(f"agent:shop:{shopkeeper.shop_id}", 60) as got:
        assert got
        out = await shop_agent.run_shop_agent(uuid.UUID(shopkeeper.shop_id), None)
        assert out == {"skipped": "locked"}
    out = await shop_agent.run_shop_agent(uuid.UUID(shopkeeper.shop_id), None)
    assert out["fallback_used"] is False and out["proposal_id"]


async def test_active_offer_overlap_stops_the_agent(client, shopkeeper, fake_ai):
    await shopkeeper.quiet(simulated=True)
    pid = (await shopkeeper.inbox())[0]["id"]
    assert (await shopkeeper.approve(pid)).status_code == 200
    out = await shop_agent.run_shop_agent(uuid.UUID(shopkeeper.shop_id), None)
    assert out == {"skipped": "active_offer_overlaps"}


async def test_flags_roundtrip_and_ai_run_rows(client, shopkeeper):
    async with session_scope() as s:
        await flags.set_flag(s, flags.AI_OUTAGE, True)
    assert await flags.get_flag(flags.AI_OUTAGE) is True
    async with session_scope() as s:
        assert await flags.get_flag(flags.SIM_ENABLED, s) is False
        assert (await s.get(AgentRun, uuid.uuid4())) is None
