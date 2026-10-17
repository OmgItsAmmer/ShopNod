"""Phase 6 (signals with a fake clock, MCP approvals with confirmation, push) and Phase 7 (admin, reset, SSE)."""
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from conftest import idem, onboard, outbox_errors, settle
from sqlalchemy import func, select, update

from shopnod_core import auth, clock, push, shop_tools, signals, sse
from shopnod_core.db import session_scope
from shopnod_core.errors import AppError
from shopnod_core.ids import uuid7
from shopnod_core.models import (
    AgentRun,
    ApprovalConfirmation,
    AuditLog,
    Claim,
    Item,
    Notification,
    Offer,
    PersonalAccessToken,
    Proposal,
    Redemption,
    Shop,
    ShopPushSubscription,
    Signal,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "seed"))
import dev_claim  # noqa: E402

UTC = UTC
# Tuesday 2026-03-10: 15:30 in Karachi (UTC+5) -> the template grid marks 15:00-17:00 as quiet
TUE_1530 = datetime(2026, 3, 10, 10, 30, tzinfo=UTC)
TUE_1200 = datetime(2026, 3, 10, 7, 0, tzinfo=UTC)  # 12:00 local = "busy" in the grid


async def count(model, *where):
    async with session_scope() as s:
        return (await s.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


async def signals_of(type_=None):
    async with session_scope() as s:
        stmt = select(Signal)
        if type_:
            stmt = stmt.where(Signal.type == type_)
        return list((await s.execute(stmt)).scalars().all())


# ── detect_quiet ─────────────────────────────────────────────────────────
async def test_quiet_hour_in_grid_creates_signal_and_agent_runs(client):
    clock.set_fixed(TUE_1530)
    sk = await onboard(client)
    created = await signals.detect_quiet()
    assert len(created) == 1
    await settle()
    sig = (await signals_of("quiet"))[0]
    assert sig.window["via"] == "grid"
    inbox = await sk.inbox()
    assert len(inbox) == 1 and inbox[0]["source"] == "rules" and "marked quiet" in inbox[0]["reason"]
    # cooldown + pending proposal: nothing new is created
    assert await signals.detect_quiet() == []
    clock.advance(timedelta(minutes=5))
    assert await signals.detect_quiet() == []


async def test_busy_hour_new_shop_creates_no_signal(client):
    clock.set_fixed(TUE_1200)
    await onboard(client)
    assert await signals.detect_quiet() == []


def fake_redemption(session, offer, sid, when):
    """A redemption row with a real claim behind it (Postgres enforces the foreign key)."""
    claim = Claim(id=uuid7(), offer_id=offer.id, token_jti=uuid.uuid4().hex, short_code="ABCDEF", status="redeemed", expires_at=when)
    session.add(claim)
    session.add(Redemption(claim_id=claim.id, offer_id=offer.id, shop_id=sid, discount_minor=1000, redeemed_at=when))


async def seed_history(shop_id, now, per_week: int, this_hour: int, weeks=4):
    """Redemptions in the same weekday/hour window of the last `weeks` weeks, plus `this_hour` in the last 60 min."""
    async with session_scope() as s:
        sid = uuid.UUID(shop_id)
        (await s.get(Shop, sid)).created_at = now - timedelta(days=60)
        offer = Offer(shop_id=sid, items=[], pct=10, starts_at=now, ends_at=now + timedelta(hours=1), cap=999, status="ended")
        s.add(offer)
        await s.flush()
        stamps = [now - timedelta(weeks=k, minutes=20 + i) for k in range(1, weeks + 1) for i in range(per_week)]
        stamps += [now - timedelta(minutes=10 + i) for i in range(this_hour)]
        for t in stamps:
            fake_redemption(s, offer, sid, t)


async def test_below_60_percent_of_usual_is_quiet_and_normal_is_not(client):
    clock.set_fixed(TUE_1200)  # grid says busy here, so only the baseline can trigger
    sk = await onboard(client)
    await seed_history(sk.shop_id, TUE_1200, per_week=10, this_hour=3)  # 3 vs usual 10 -> 30%
    async with session_scope() as s:
        shop = await s.get(Shop, uuid.UUID(sk.shop_id))
        st = await signals.activity_stats(s, shop, TUE_1200)
    assert st["usual_for_this_hour"] == 10 and st["redemptions_last_60_min"] == 3 and st["pct_of_usual"] == 0.3
    assert len(await signals.detect_quiet()) == 1
    assert (await signals_of("quiet"))[0].window["via"] == "baseline"
    await settle()
    pid = (await sk.inbox())[0]["id"]
    await client.post(f"/v1/shop/proposals/{pid}/reject", json={"reason": "other"})
    # busier hour: 8 vs usual 10 = 80% -> not quiet (new cooldown window after an hour)
    clock.set_fixed(TUE_1200 + timedelta(hours=2))
    async with session_scope() as s:
        await s.execute(update(Redemption).where(Redemption.redeemed_at > TUE_1200 - timedelta(hours=1)).values(redeemed_at=TUE_1200 - timedelta(days=3)))
    now = clock.now()
    await seed_history(sk.shop_id, now, per_week=0, this_hour=0)  # (keeps created_at old)
    async with session_scope() as s:
        offer = (await s.execute(select(Offer))).scalars().first()
        for i in range(10):  # usual for last 4 weeks at this hour
            for k in range(1, 5):
                fake_redemption(s, offer, uuid.UUID(sk.shop_id), now - timedelta(weeks=k, minutes=20 + i))
        for i in range(8):
            fake_redemption(s, offer, uuid.UUID(sk.shop_id), now - timedelta(minutes=5 + i))
    assert await signals.detect_quiet() == []


async def test_closed_shop_or_live_offer_blocks_quiet_signal(client):
    clock.set_fixed(datetime(2026, 3, 10, 18, 30, tzinfo=UTC))  # 23:30 local, after 21:00 closing
    sk = await onboard(client)
    assert await signals.detect_quiet() == []
    clock.set_fixed(TUE_1530)
    assert len(await signals.detect_quiet()) == 1
    await settle()
    pid = (await sk.inbox())[0]["id"]
    assert (await sk.approve(pid)).status_code == 200
    clock.advance(timedelta(hours=2))
    clock.set_fixed(clock.now())
    await signals.detect_quiet()  # offer (90 min) already ended by now? it is still 'active' until end_offers runs
    assert await count(Signal, Signal.type == "quiet") == 1


async def test_expiry_sweep_one_signal_per_three_hours(client):
    clock.set_fixed(TUE_1200)
    sk = await onboard(client)
    assert len(await signals.expiry_sweep()) == 1
    await settle()
    s1 = (await signals_of("expiry"))[0]
    assert s1.window["items"] >= 1
    pid = (await sk.inbox())[0]["id"]
    await client.post(f"/v1/shop/proposals/{pid}/reject", json={"reason": "other"})
    clock.advance(timedelta(hours=1))
    assert await signals.expiry_sweep() == []  # max one per shop every 3 h
    clock.advance(timedelta(hours=2, minutes=1))
    assert len(await signals.expiry_sweep()) == 1
    # nothing expiring -> nothing
    async with session_scope() as s:
        await s.execute(update(Item).values(expires_at=None))
    await settle()
    clock.advance(timedelta(hours=4))
    assert await signals.expiry_sweep() == []


# ── MCP approvals: the assistant can never publish by itself ─────────────
async def make_pat(client, scopes=("shopkeeper:approve",)):
    r = await client.post("/v1/shop/tokens", json={"name": "Claude", "scopes": list(scopes)})
    raw = r.json()["token"]
    async with session_scope() as s:
        return await auth.principal_from_bearer(s, raw)


async def call(tool, p, *a, **k):
    async with session_scope() as s:
        return await getattr(shop_tools, tool)(s, p, *a, **k)


async def pending(sk):
    await sk.quiet(simulated=True)
    return (await sk.inbox())[0]


async def test_mcp_approval_waits_for_dashboard_confirmation(client, shopkeeper):
    p = await pending(shopkeeper)
    pat = await make_pat(client)
    listing = await call("list_pending_proposals", pat)
    assert [x["id"] for x in listing["proposals"]] == [p["id"]]
    res = await call("approve_proposal", pat, p["id"], 12)
    assert res["status"] == "awaiting_confirmation" and "confirm in the ShopNod dashboard" in res["message"]
    assert await count(Offer) == 0  # NOT published
    await settle()
    cards = (await client.get("/v1/shop/confirmations")).json()
    assert len(cards) == 1 and cards[0]["final_pct"] == 12 and cards[0]["proposal"]["status"] == "awaiting_confirmation"
    inbox = await shopkeeper.inbox()
    assert inbox[0]["status"] == "awaiting_confirmation" and inbox[0]["confirmation_id"] == cards[0]["id"]
    assert (await call("get_confirmation_status", pat, res["confirmation_id"]))["status"] == "awaiting"
    again = await call("approve_proposal", pat, p["id"], 12)  # asking twice reuses the same card
    assert again["confirmation_id"] == res["confirmation_id"]
    # assistants cannot approve a proposal that is waiting on a different path either: direct dashboard approve is 409
    assert (await shopkeeper.approve(p["id"])).status_code == 409

    cid = cards[0]["id"]
    r = await client.post(f"/v1/shop/confirmations/{cid}/confirm", headers=idem())
    assert r.status_code == 200, r.text
    assert r.json()["offer"]["pct"] == 12 and r.json()["proposal"]["channel"] == "mcp_confirmed"
    assert await count(Offer) == 1
    audit = (await client.get("/v1/shop/audit")).json()
    approved = [a for a in audit if a["action"] in ("proposal.approved", "proposal.edited")][0]
    assert approved["channel"] == "mcp_confirmed"
    assert (await client.post(f"/v1/shop/confirmations/{cid}/confirm", headers=idem())).status_code == 409
    assert (await call("get_confirmation_status", pat, res["confirmation_id"]))["status"] == "confirmed"
    stats = await call("get_offer_stats", pat, r.json()["offer"]["id"])
    assert stats["redemptions"] == 0
    await settle()
    assert await outbox_errors() == []


async def test_mcp_request_is_validated_immediately_and_guardrails_still_apply(client, shopkeeper):
    p = await pending(shopkeeper)
    pat = await make_pat(client)
    with pytest.raises(AppError) as e:
        await call("approve_proposal", pat, p["id"], 40)
    assert e.value.status == 422 and e.value.code.value == "guardrail_violation"
    assert await count(ApprovalConfirmation) == 0
    assert (await shopkeeper.inbox())[0]["status"] == "pending"
    with pytest.raises(AppError):
        await call("approve_proposal", pat, "not-a-uuid", 10)


async def test_decline_and_ten_minute_timeout_put_the_proposal_back(client, shopkeeper):
    from shopnod_core import proposals

    p = await pending(shopkeeper)
    pat = await make_pat(client)
    res = await call("approve_proposal", pat, p["id"], 10)
    r = await client.post(f"/v1/shop/confirmations/{res['confirmation_id']}/decline")
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert (await call("get_confirmation_status", pat, res["confirmation_id"]))["status"] == "declined"
    assert await count(Offer) == 0
    # ask again, ignore it for 10 minutes
    res2 = await call("approve_proposal", pat, p["id"], 10)
    clock.advance(timedelta(minutes=16))
    assert (await call("get_confirmation_status", pat, res2["confirmation_id"]))["status"] == "expired"
    late = await client.post(f"/v1/shop/confirmations/{res2['confirmation_id']}/confirm", headers=idem())
    assert late.status_code == 409 and late.json()["error"]["code"] == "confirmation_expired"
    assert (await client.get("/v1/shop/confirmations")).json() == []
    # the proposal's own window (10 min lead) has started too, so the sweep expires it for good
    counts = await proposals.expire_proposals()
    assert counts["proposals"] == 1
    assert await count(Offer) == 0


async def test_unconfirmed_request_returns_to_pending_when_window_still_open(client, shopkeeper):
    from shopnod_core import proposals

    p = await pending(shopkeeper)
    async with session_scope() as s:
        row = await s.get(Proposal, uuid.UUID(p["id"]))
        row.window_start = clock.now() + timedelta(hours=2)
        row.window_end = clock.now() + timedelta(hours=3)
    pat = await make_pat(client)
    await call("approve_proposal", pat, p["id"], 10)
    clock.advance(timedelta(minutes=11))
    counts = await proposals.expire_proposals()
    assert counts == {"proposals": 0, "confirmations": 1}
    assert (await shopkeeper.inbox())[0]["status"] == "pending"


async def test_reject_through_mcp_records_channel(client, shopkeeper):
    p = await pending(shopkeeper)
    pat = await make_pat(client)
    out = await call("reject_proposal", pat, p["id"], "wrong_time", "not now")
    assert out["status"] == "rejected"
    a = [x for x in (await client.get("/v1/shop/audit")).json() if x["action"] == "proposal.rejected"][0]
    assert a["channel"] == "mcp" and a["data"]["reason"] == "wrong_time"


async def test_no_route_and_no_mcp_tool_can_publish_without_a_shopkeeper_session(client, shopkeeper):
    """The standalone-done check: an offer only appears through a logged-in shopkeeper's click."""
    p = await pending(shopkeeper)
    from shopnod_api.main import create_app

    app = create_app()
    anon = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    public = ("/v1/auth/",)
    for route in app.routes:
        path = getattr(route, "path", None)
        for sub in getattr(route, "routes", [route]):
            path = getattr(sub, "path", path)
            methods = getattr(sub, "methods", None) or set()
            for m in methods & {"POST", "PUT", "DELETE", "PATCH"}:
                if not path or path.startswith(public) or path == "/mcp":
                    continue
                url = path.replace("{proposal_id}", p["id"]).replace("{confirmation_id}", str(uuid.uuid4()))
                url = url.replace("{offer_id}", str(uuid.uuid4())).replace("{shop_id}", shopkeeper.shop_id)
                url = url.replace("{item_id}", str(uuid.uuid4())).replace("{token_id}", str(uuid.uuid4()))
                r = await anon.request(m, url, json={}, headers=idem())
                assert r.status_code == 401, f"{m} {path} -> {r.status_code}"
    await anon.aclose()
    # every MCP tool, called with an agent token and with an approve token, never creates an offer
    agent = await (lambda: _agent_principal(shopkeeper.shop_id))()
    pat = await make_pat(client, ("shopkeeper:read", "shopkeeper:approve"))
    for principal in (agent, pat):
        for tool in sorted(shop_tools.AGENT_TOOLS | shop_tools.SHOPKEEPER_TOOLS):
            try:
                args = {"approve_proposal": (p["id"],), "reject_proposal": (str(uuid.uuid4()), "other"), "get_offer_stats": (str(uuid.uuid4()),),
                        "get_confirmation_status": (str(uuid.uuid4()),)}.get(tool, ())
                if tool == "submit_proposal":
                    args = ([], 10, clock.now().isoformat(), clock.now().isoformat(), 5, "x")
                await call(tool, principal, *args)
            except AppError:
                pass
    assert await count(Offer) == 0
    assert not any(n.startswith("publish") for n in dir(shop_tools))


async def _agent_principal(shop_id):
    async with session_scope() as s:
        return await auth.principal_from_bearer(s, auth.create_agent_token(uuid.UUID(shop_id)))


# ── shopkeeper push ──────────────────────────────────────────────────────
@pytest.fixture
def fake_push(monkeypatch):
    sent, state = [], {"fail": None}

    async def send(endpoint, p256dh, auth_, payload, ttl=3600):
        if state["fail"] == "gone":
            raise push.SubscriptionGone(endpoint)
        if state["fail"] == "500":
            raise RuntimeError("push service 500")
        sent.append((endpoint, payload))

    monkeypatch.setattr(push, "webpush_configured", lambda: True)
    monkeypatch.setattr(push, "send_webpush", send)
    return SimpleNamespace(sent=sent, state=state)


async def test_push_subscription_and_new_offer_notification(client, shopkeeper, fake_push):
    sub = {"endpoint": "https://push.example/abc", "p256dh": "BPkey" * 5, "auth": "authsecret"}
    assert (await client.post("/v1/shop/push-subscriptions", json=sub)).status_code == 201
    assert (await client.post("/v1/shop/push-subscriptions", json=sub)).status_code == 201  # idempotent
    assert await count(ShopPushSubscription) == 1
    await shopkeeper.quiet(simulated=True)
    assert len(fake_push.sent) == 1
    payload = fake_push.sent[0][1]
    assert payload["body"].startswith("New offer to approve: 10% ") and "–" in payload["body"] and payload["url"] == "/dashboard"
    assert (await client.get("/v1/shop/push-config")).json()["enabled"] is False  # no VAPID keys in tests
    r = await client.request("DELETE", "/v1/shop/push-subscriptions", json={"endpoint": sub["endpoint"]})
    assert r.status_code == 200 and await count(ShopPushSubscription) == 0


async def test_push_gone_subscription_is_removed_and_failures_retry(client, shopkeeper, fake_push):
    sub = {"endpoint": "https://push.example/zzz", "p256dh": "BPkey" * 5, "auth": "authsecret"}
    await client.post("/v1/shop/push-subscriptions", json=sub)
    fake_push.state["fail"] = "500"
    await shopkeeper.quiet(simulated=True)
    from shopnod_core.models import Outbox

    async with session_scope() as s:
        row = (await s.execute(select(Outbox).where(Outbox.topic == "proposal.created"))).scalars().one()
    assert row.status == "pending" and row.attempts == 1 and "push service 500" in row.last_error
    assert "sse" in row.payload["_done"]  # the in-app live update was not blocked by the push failure
    fake_push.state["fail"] = "gone"
    clock.advance(timedelta(seconds=30))
    await settle()
    assert await count(ShopPushSubscription) == 0


async def test_confirmation_request_sends_push(client, shopkeeper, fake_push):
    await client.post("/v1/shop/push-subscriptions", json={"endpoint": "https://push.example/c", "p256dh": "BPkey" * 5, "auth": "authsecret"})
    p = await pending(shopkeeper)
    fake_push.sent.clear()
    pat = await make_pat(client)
    await call("approve_proposal", pat, p["id"], 10)
    await settle()
    assert any("Confirm it in the dashboard" in s[1]["body"] for s in fake_push.sent)


# ── SSE ──────────────────────────────────────────────────────────────────
async def test_sse_events_reach_the_shop_stream(client, shopkeeper):
    ch = sse.shop_channel(shopkeeper.shop_id)
    got: list[dict] = []

    async def listen():
        async for raw in sse.subscribe(ch, heartbeat_s=0.2):
            if raw:
                got.append(json.loads(raw))
                if any(e["type"] == "offer.published" for e in got):
                    return

    task = asyncio.create_task(listen())
    await asyncio.sleep(0.05)
    p = await pending(shopkeeper)
    await shopkeeper.approve(p["id"])
    await settle()
    await asyncio.wait_for(task, 5)
    types = [e["type"] for e in got]
    assert "proposal.created" in types and "proposal.decided" in types and "offer.published" in types
    assert got[0]["data"]["proposal_id"] == p["id"]
    frames = []
    async for frame in sse.event_stream(ch, heartbeat_s=0.05):
        frames.append(frame)
        if len(frames) == 2:
            break
    assert frames[0].startswith(b": connected") and frames[1].startswith(b": heartbeat")
    anon = httpx.AsyncClient(transport=httpx.ASGITransport(app=client._transport.app), base_url="http://test")
    assert (await anon.get("/v1/shop/stream")).status_code == 401
    await anon.aclose()


async def test_redemption_and_sold_out_events_on_stream(client, shopkeeper):
    p = await pending(shopkeeper)
    offer = (await shopkeeper.approve(p["id"])).json()["offer"]
    await settle()
    got = []

    async def listen():
        async for raw in sse.subscribe(sse.shop_channel(shopkeeper.shop_id), heartbeat_s=0.2):
            if raw:
                got.append(json.loads(raw))
                if {"offer.ended", "redemption.recorded"} <= {e["type"] for e in got}:
                    return

    task = asyncio.create_task(listen())
    await asyncio.sleep(0.05)
    async with session_scope() as s:
        (await s.get(Offer, uuid.UUID(offer["id"]))).cap = 1
    c = await dev_claim.make_claim(offer["id"])
    r = await client.post("/v1/shop/redemptions", json={"payload": c["qr_text"]}, headers=idem())
    assert r.json()["result"] == "ok"
    await settle()
    await asyncio.wait_for(task, 5)
    assert {e["type"] for e in got} == {"redemption.recorded", "offer.ended"}
    assert [e for e in got if e["type"] == "offer.ended"][0]["data"]["reason"] == "sold_out"


# ── Phase 7: admin, demo reset ──────────────────────────────────────────
async def test_admin_status_flags_and_permissions(client, shopkeeper):
    await shopkeeper.quiet(simulated=True)
    st = (await client.get("/v1/admin/status")).json()
    assert st["outbox"]["sent"] >= 1 and st["outbox"]["dead"] == 0 and st["breakers"] == {"openai": "closed", "push": "closed", "weather": "closed"}
    assert st["flags"] == {"ai_outage": False, "sim_enabled": False} and st["last_agent_runs"][0]["agent"] == "shop_agent"
    assert (await client.post("/v1/admin/sim", json={"enabled": True})).status_code == 200
    assert (await client.post("/v1/admin/sim", json={"burst": True})).status_code == 200
    assert (await client.get("/v1/admin/status")).json()["flags"]["sim_enabled"] is True
    await client.post("/v1/admin/ai-outage", json={"enabled": True})
    assert (await client.get("/v1/admin/status")).json()["flags"]["ai_outage"] is True
    # a normal (non-admin) user is refused
    async with session_scope() as s:
        from shopnod_core.models import User

        await s.execute(update(User).values(is_admin=False))
    assert (await client.get("/v1/admin/status")).status_code == 403
    assert (await client.post("/v1/admin/ai-outage", json={"enabled": False})).status_code == 403


async def test_demo_reset_removes_offers_claims_and_restores_template(client, shopkeeper):
    p = await pending(shopkeeper)
    offer = (await shopkeeper.approve(p["id"])).json()["offer"]
    c = await dev_claim.make_claim(offer["id"])
    await client.post("/v1/shop/redemptions", json={"payload": c["qr_text"]}, headers=idem())
    async with session_scope() as s:
        s.add(Notification(install_id=uuid.uuid4(), offer_id=uuid.UUID(offer["id"]), title="x"))
        await s.execute(update(Item).values(quantity=0))
    await settle()
    r = await client.post("/v1/shop/demo/reset")
    assert r.status_code == 200
    assert await count(Offer) == 0 and await count(Claim) == 0 and await count(Redemption) == 0
    assert await count(Notification) == 0 and await count(Proposal) == 0 and await count(Signal) == 0
    items = (await client.get("/v1/shop/items")).json()
    assert len(items) == 5 and all(i["quantity"] > 0 for i in items)
    await settle()
    from shopnod_core.models import Outbox

    async with session_scope() as s:
        ended = (await s.execute(select(Outbox).where(Outbox.topic == "offer.ended"))).scalars().all()
    assert any(o.payload["reason"] == "demo_reset" for o in ended)  # shopper feeds are told
    # a real (non-demo) shop cannot be reset
    async with session_scope() as s:
        (await s.get(Shop, uuid.UUID(shopkeeper.shop_id))).is_demo = False
    assert (await client.post("/v1/shop/demo/reset")).json()["error"]["code"] == "demo_only"
    _ = (AuditLog, PersonalAccessToken)


async def test_dead_letter_after_five_attempts(client, shopkeeper, monkeypatch):
    from shopnod_core import outbox

    @outbox.handler("test.topic", "always_fails")
    async def boom(_):
        raise RuntimeError("nope")

    async with session_scope() as s:
        await outbox.emit(s, "test.topic", {"x": 1})
    for _ in range(6):
        await outbox.process_outbox()
        clock.advance(timedelta(minutes=15))
    from shopnod_core.models import Outbox

    async with session_scope() as s:
        row = (await s.execute(select(Outbox).where(Outbox.topic == "test.topic"))).scalars().one()
    assert row.status == "dead" and row.attempts == 5 and "nope" in row.last_error


async def test_ask_your_shop_uses_the_tools_and_only_requests_approval(client, shopkeeper):
    p = await pending(shopkeeper)
    r = (await client.post("/v1/shop/assistant", json={"message": "what's pending?"})).json()
    assert [c["tool"] for c in r["tool_calls"]] == ["list_pending_proposals"] and "%" in r["reply"]
    r = (await client.post("/v1/shop/assistant", json={"message": "approve it at 12%"})).json()
    assert r["needs_confirmation"] and "approve_proposal" in [c["tool"] for c in r["tool_calls"]]
    assert await count(Offer) == 0  # still nothing live
    assert (await client.post("/v1/shop/assistant", json={"message": "hello"})).json()["tool_calls"] == []


async def test_rules_fallback_trace_lists_the_read_tools(client, shopkeeper):
    await pending(shopkeeper)
    async with session_scope() as s:
        run = (await s.execute(select(AgentRun).where(AgentRun.fallback_used.is_(True)).order_by(AgentRun.created_at.desc()))).scalars().first()
    names = [c["tool"] for c in run.tool_calls]
    assert "get_activity" in names and names[-1] == "submit_proposal"
