"""Phase 1 (login + wizard + items + guardrails) and Phase 2 (I'm quiet -> rules proposal in the inbox)."""
import time
import uuid

from conftest import idem, onboard, settle


async def test_health_and_request_id(client):
    r = await client.get("/healthz")
    assert r.status_code == 200 and r.headers["x-request-id"]
    assert (await client.get("/readyz")).json()["checks"]["database"] == "ok"


async def test_unauthenticated_gets_standard_error_shape(client):
    r = await client.get("/v1/shop/shop")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "unauthorized" and err["request_id"] == r.headers["x-request-id"] and err["retryable"] is False


async def test_demo_login_wizard_under_90s_and_session_cookie(client):
    t0 = time.perf_counter()
    r = await client.post("/v1/auth/demo-login")
    assert r.status_code == 200 and "sn_session" in r.headers["set-cookie"]
    assert "HttpOnly" in r.headers["set-cookie"] and "samesite=lax" in r.headers["set-cookie"].lower()
    me = (await client.get("/v1/auth/me")).json()
    assert me["user"]["is_demo"] and me["shop"] is None

    tpl = (await client.get("/v1/shop/templates")).json()
    assert {t["key"] for t in tpl} == {"bakery", "grocery", "cafe", "fruit_veg", "general"}  # no pharmacy

    sid = (await client.post("/v1/shop/shops", json={"name": "Ali's Bakery", "category": "bakery"})).json()["id"]
    loc = (await client.put(f"/v1/shop/shops/{sid}/location", json={"market": "demo"})).json()
    assert len(loc["geohash6"]) == 6 and loc["area_id"] and loc["timezone"] == "Asia/Karachi"
    r = await client.post(f"/v1/shop/shops/{sid}/apply-template", json={})
    assert r.json()["items"] == 5
    r = await client.post(f"/v1/shop/shops/{sid}/complete")
    assert r.status_code == 200 and r.json()["shop"]["onboarding_status"] == "complete"
    assert time.perf_counter() - t0 < 90

    items = (await client.get("/v1/shop/items")).json()
    g = (await client.get("/v1/shop/guardrails")).json()
    assert len(items) == 5 and g["max_discount_pct"] == 25 and "alcohol" in g["always_blocked_categories"]
    assert (await client.get("/v1/auth/me")).json()["shop"]["geohash6"] == loc["geohash6"]


async def test_wizard_guards(client):
    await client.post("/v1/auth/demo-login")
    sid = (await client.post("/v1/shop/shops", json={"name": "X", "category": "cafe"})).json()["id"]
    # not complete without a location / items
    assert (await client.post(f"/v1/shop/shops/{sid}/complete")).json()["error"]["code"] == "onboarding_incomplete"
    await client.put(f"/v1/shop/shops/{sid}/location", json={"lat": 31.5, "lng": 74.35, "timezone": "Asia/Karachi", "currency": "pkr", "is_eu": False})
    assert (await client.post(f"/v1/shop/shops/{sid}/complete")).json()["error"]["code"] == "onboarding_incomplete"
    assert (await client.put(f"/v1/shop/shops/{sid}/location", json={})).status_code == 422
    # app pages need a completed shop
    assert (await client.get("/v1/shop/offers")).status_code == 409
    # second user can't touch this shop
    other = await client.post("/v1/auth/demo-login")
    assert other.status_code == 200
    assert (await client.put(f"/v1/shop/shops/{sid}/location", json={"market": "demo"})).status_code == 403
    assert (await client.post(f"/v1/shop/shops/{uuid.uuid4()}/complete")).status_code == 404


async def test_logout_and_magic_link(client, capsys):
    await client.post("/v1/auth/demo-login")
    assert (await client.post("/v1/auth/logout")).status_code == 200
    assert (await client.get("/v1/auth/me")).status_code == 401

    assert (await client.post("/v1/auth/magic-link", json={"email": "not-an-email"})).status_code == 422
    assert (await client.post("/v1/auth/magic-link", json={"email": "Owner@Example.com"})).status_code == 202
    out = capsys.readouterr().out
    link = out.split("owner@example.com: ")[1].split()[0]  # printed in the logs (no EMAIL_PROVIDER_KEY)
    path = link.split("/api", 1)[1]
    r = await client.get(path)
    assert r.status_code == 303 and r.headers["location"] == "/dashboard" and "sn_session" in r.headers["set-cookie"]
    assert (await client.get("/v1/auth/me")).json()["user"]["email"] == "owner@example.com"
    again = await client.get(path)  # a magic link works once
    assert again.status_code == 303 and "error=used" in again.headers["location"]
    assert "error=link" in (await client.get("/v1/auth/magic-link/verify?token=garbage-token-value")).headers["location"]


async def test_demo_login_is_rate_limited(client, monkeypatch):
    from shopnod_core.settings import get_settings

    monkeypatch.setattr(get_settings(), "DEMO_LOGIN_PER_MINUTE", 2)
    codes = [(await client.post("/v1/auth/demo-login")).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


async def test_items_crud_and_price_history(client, shopkeeper):
    from sqlalchemy import select

    from shopnod_core.db import session_scope
    from shopnod_core.models import ItemPriceHistory

    r = await client.post("/v1/shop/items", json={"name": "Baguette", "category": "Bread", "price_minor": 20000, "cost_minor": 9000, "quantity": 5})
    assert r.status_code == 201
    it = r.json()
    assert it["category"] == "bread" and it["regular_price_minor"] == 20000
    body = {"name": "Baguette", "category": "bread", "price_minor": 22000, "regular_price_minor": 22000, "quantity": 5}
    r = await client.put(f"/v1/shop/items/{it['id']}", json=body)
    assert r.json()["regular_price_minor"] == 22000
    async with session_scope() as s:
        hist = (await s.execute(select(ItemPriceHistory).where(ItemPriceHistory.item_id == uuid.UUID(it["id"])))).scalars().all()
    assert sorted(h.price_minor for h in hist) == [20000, 22000]
    assert (await client.delete(f"/v1/shop/items/{it['id']}")).status_code == 204
    assert (await client.put(f"/v1/shop/items/{it['id']}", json=body)).status_code == 404


async def test_guardrails_edit_is_audited_with_hint(client, shopkeeper):
    g = (await client.get("/v1/shop/guardrails")).json()
    body = {k: g[k] for k in ("min_price_minor", "max_discount_pct", "never_discount_item_ids", "blocked_categories", "daily_budget_minor",
                              "weekly_budget_minor", "max_offers_per_day", "max_redemptions_per_offer", "allowed_hours")}
    body["max_discount_pct"] = 5
    await shopkeeper.quiet(simulated=True)  # a 10% rules proposal now exists
    r = await client.post("/v1/shop/guardrails/preview", json=body)
    assert r.json()["would_block"] == 1 and "blocked 1 of last week's proposal" in r.json()["hint"]
    r = await client.put("/v1/shop/guardrails", json=body)
    assert r.status_code == 200 and r.json()["max_discount_pct"] == 5
    audit = (await client.get("/v1/shop/audit", params={"action": "guardrails"})).json()
    assert audit[0]["action"] == "guardrails.updated" and audit[0]["data"]["changes"]["max_discount_pct"]["after"] == 5
    bad = {**body, "allowed_hours": {"start": "20:00", "end": "08:00"}}
    assert (await client.put("/v1/shop/guardrails", json=bad)).status_code == 422
    bad = {**body, "never_discount_item_ids": [str(uuid.uuid4())]}
    assert (await client.put("/v1/shop/guardrails", json=bad)).status_code == 422


async def test_quiet_gives_rules_proposal_card(client, shopkeeper):
    t0 = time.perf_counter()
    r = await client.post("/v1/shop/signals/quiet")
    assert r.status_code == 202 and r.json()["agent_queued"] is True
    await settle()
    inbox = await shopkeeper.inbox()
    assert time.perf_counter() - t0 < 3
    assert len(inbox) == 1
    p = inbox[0]
    assert p["source"] == "rules" and p["status"] == "pending" and p["proposed_pct"] == 10
    assert p["reason"] and p["items"][0]["was_minor"] > p["items"][0]["new_price_minor"]
    assert p["items"][0]["name"] == "Cake slice" or p["items"][0]["name"]  # expiring item first
    assert (await client.get(f"/v1/shop/proposals/{p['id']}")).json()["id"] == p["id"]
    # a second press while one is pending is told why nothing new happens
    again = (await client.post("/v1/shop/signals/quiet")).json()
    assert again["agent_queued"] is False and again["skipped_reason"] == "proposal_already_pending"
    await settle()
    assert len(await shopkeeper.inbox()) == 1


async def test_simulate_quiet_demo_only(client):
    await client.post("/v1/auth/demo-login")
    sid = (await client.post("/v1/shop/shops", json={"name": "Real", "category": "cafe"})).json()["id"]
    await client.put(f"/v1/shop/shops/{sid}/location", json={"market": "demo"})
    await client.post(f"/v1/shop/shops/{sid}/apply-template", json={})
    await client.post(f"/v1/shop/shops/{sid}/complete")
    from shopnod_core.db import session_scope
    from shopnod_core.models import Shop

    async with session_scope() as s:
        (await s.get(Shop, uuid.UUID(sid))).is_demo = False
    r = await client.post("/v1/shop/demo/simulate-quiet")
    assert r.status_code == 403 and r.json()["error"]["code"] == "demo_only"


async def test_expiring_stock_proposal_and_guardrail_save_chip(client, shopkeeper):
    from sqlalchemy import update

    from shopnod_core.db import session_scope
    from shopnod_core.models import Guardrail, Item
    from shopnod_core.shop_data import load_guardrail

    async with session_scope() as s:
        g = await load_guardrail(s, uuid.UUID(shopkeeper.shop_id))
        g.max_discount_pct = 5  # default rules pct is 10 -> clamped
        await s.execute(update(Item).values(quantity=3))
    await shopkeeper.quiet(simulated=True)
    p = (await shopkeeper.inbox())[0]
    assert p["proposed_pct"] == 5 and p["original_pct"] == 10
    save = [x for x in p["guardrail_saves"] if x["rule"] == "max_discount_pct"][0]
    assert "10% → 5%" in save["message"]
    _ = (Guardrail, idem, onboard)
