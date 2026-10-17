"""Plan 3 Phase 1: every link between the shopper and shopkeeper sides (S1–S12), plus Phase 2 simulated shoppers.

Runs on SQLite by default and on a real Postgres with SHOPNOD_TEST_DATABASE_URL (CI does both).
"""
import asyncio
import json
import uuid
from datetime import timedelta

from conftest import NOW, idem, settle
from sqlalchemy import func, select

from shopnod_core import clock, flags, redeem, signals, sse
from shopnod_core import shopper as sh
from shopnod_core.db import session_scope
from shopnod_core.models import (
    AgentRun,
    Claim,
    MeterEvent,
    Notification,
    Offer,
    Outbox,
    Proposal,
    Redemption,
    Shopper,
    Signal,
)

BAKERY_LIST = ["croissant", "cake", "bread", "cookies"]  # matches whatever bakery items the rules proposal picks


class ShopperApp:
    """A shopper install talking to the API with its bearer token, like the Flutter app does."""

    def __init__(self, client, token: str, install_id: str):
        self.c, self.token, self.id = client, token, install_id

    @property
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def get(self, path, **kw):
        return await self.c.get(f"/v1/shopper{path}", headers={**self.h, **kw.pop("headers", {})}, **kw)

    async def post(self, path, **kw):
        return await self.c.post(f"/v1/shopper{path}", headers={**self.h, **kw.pop("headers", {})}, **kw)

    async def put(self, path, **kw):
        return await self.c.put(f"/v1/shopper{path}", headers={**self.h, **kw.pop("headers", {})}, **kw)

    async def delete(self, path, **kw):
        return await self.c.request("DELETE", f"/v1/shopper{path}", headers={**self.h, **kw.pop("headers", {})}, **kw)

    async def feed(self) -> list[dict]:
        r = await self.get("/feed")
        assert r.status_code == 200, r.text
        return r.json()

    async def claim(self, offer_id: str, key: dict | None = None):
        return await self.post(f"/offers/{offer_id}/claim", headers=key or idem())


async def new_shopper(client, *, items=BAKERY_LIST, consents=None, push=True, location: bool = False) -> ShopperApp:
    r = await client.post("/v1/shopper/installs", json={"platform": "web", "languages": ["en"], "age_confirmed": True})
    assert r.status_code == 201, r.text
    app = ShopperApp(client, r.json()["install_token"], r.json()["install_id"])
    c = {"location": location, "notifications": True, "list": True, "personalisation": True, "analytics": False}
    c.update(consents or {})
    assert (await app.put("/consents", json={**c, "policy_version": "1.0"})).status_code == 200
    assert (await app.put("/preferences", json={"categories": ["Bakery"], "languages": ["en"]})).status_code == 200
    r = await app.post("/location", json={"market": "demo"})
    assert r.status_code == 200 and r.json()["market_name"] == "Demo Market", r.text
    if c["list"] and items:
        assert (await app.put("/list", json={"items": list(items)})).status_code == 200
    if push and c["notifications"]:
        assert (await app.post("/push-tokens", json={"kind": "fcm", "token": f"fcm-{uuid.uuid4().hex}"})).status_code == 201
    return app


async def publish(sk, body: dict | None = None) -> dict:
    """Shopkeeper: simulate a quiet hour, approve the proposal, let the outbox run."""
    await sk.quiet(simulated=True)
    pid = (await sk.inbox("pending"))[0]["id"]
    r = await sk.approve(pid, body or {})
    assert r.status_code == 200, r.text
    await settle()
    return r.json()["offer"]


async def scan(client, *, payload=None, code=None):
    r = await client.post("/v1/shop/redemptions", json={"payload": payload} if payload else {"short_code": code}, headers=idem())
    assert r.status_code == 200, r.text
    return r.json()


async def count(model, *where) -> int:
    async with session_scope() as s:
        return (await s.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


# ── S1 publish → match → push ────────────────────────────────────────────
async def test_s1_publish_match_push(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper)
    iid = uuid.UUID(me.id)
    assert await count(Notification, Notification.install_id == iid, Notification.offer_id == uuid.UUID(offer["id"])) == 1
    async with session_scope() as s:
        pushes = (await s.execute(select(Outbox).where(Outbox.topic == "shopper.push"))).scalars().all()
    assert len(pushes) == 1 and pushes[0].payload["install_id"] == me.id and pushes[0].status == "sent"  # skipped: FCM not set up
    feed = await me.feed()
    assert [f["offer"]["id"] for f in feed] == [offer["id"]]
    item = feed[0]
    assert item["why"].startswith("On your list") and item["source"] == "rules" and item["distance_m"] % 50 == 0
    assert item["offer"]["now_price"] < item["offer"]["was_price"] and item["shop"]["name"] == "Test Bakery"
    # running the handler again (the same event can arrive twice) notifies nobody twice
    from shopnod_worker.tasks.shopper.matching import match_and_notify

    await match_and_notify(uuid.UUID(offer["id"]))
    assert await count(Notification, Notification.install_id == iid) == 1


async def test_s1_no_notification_without_consent_or_when_muted(client, shopkeeper):
    quiet_one = await new_shopper(client, consents={"notifications": False})
    muted = await new_shopper(client)
    assert (await muted.put("/preferences", json={"muted_shops": [shopkeeper.shop_id]})).status_code == 200
    offer = await publish(shopkeeper)
    for x in (quiet_one, muted):
        assert await count(Notification, Notification.install_id == uuid.UUID(x.id)) == 0
    assert [f["offer"]["id"] for f in await quiet_one.feed()] == [offer["id"]]  # still in the feed, just no push
    assert await muted.feed() == []


# ── S2 claim → redeem ────────────────────────────────────────────────────
async def test_s2_claim_then_redeem_exactly_once(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper, {"final_pct": 10})
    key = idem()
    r = await me.claim(offer["id"], key)
    assert r.status_code == 200, r.text
    claim = r.json()
    assert claim["qr_payload"].startswith("SN1:") and len(claim["short_code"]) == 6 and claim["status"] == "issued"
    assert (await me.claim(offer["id"], key)).json()["claim_id"] == claim["claim_id"]  # same key → same claim
    assert (await me.claim(offer["id"])).json()["claim_id"] == claim["claim_id"]  # one active claim per offer
    res = await scan(client, payload=claim["qr_payload"])
    assert res["result"] == "ok" and res["discount_pct"] == 10
    assert (await scan(client, payload=claim["qr_payload"]))["result"] == "already_redeemed"
    await settle()
    assert await count(Redemption) == 1 and await count(MeterEvent) == 1


# ── S3 short code ────────────────────────────────────────────────────────
async def test_s3_short_code_and_wrong_shop(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper)
    claim = (await me.claim(offer["id"])).json()
    other_shop = uuid.uuid4()
    wrong = await redeem.redeem(other_shop, short_code=claim["short_code"])
    assert wrong["result"] == "wrong_shop"
    assert (await scan(client, code=claim["short_code"].lower()))["result"] == "ok"


# ── S4 redeem → shopper sees it ──────────────────────────────────────────
async def test_s4_live_redeemed_event_and_savings(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper, {"final_pct": 10})
    claim = (await me.claim(offer["id"])).json()
    before = (await me.get("/savings")).json()["amount_minor"]

    got: list[dict] = []

    async def listen():
        async for raw in sse.subscribe(sse.shopper_channel(me.id), heartbeat_s=0.2):
            if raw:
                got.append(json.loads(raw))
                return

    task = asyncio.create_task(listen())
    await asyncio.sleep(0.05)
    res = await scan(client, payload=claim["qr_payload"])
    await settle()
    await asyncio.wait_for(task, timeout=5)
    assert got[0]["type"] == "claim.redeemed" and got[0]["data"]["claim_id"] == claim["claim_id"]
    saved = got[0]["data"]["saved_minor"]
    assert saved > 0
    st = (await me.get(f"/claims/{claim['claim_id']}")).json()
    assert st["status"] == "redeemed" and st["saved_minor"] == saved
    after = (await me.get("/savings")).json()
    assert after["amount_minor"] == before + saved and after["count"] == 1 and after["currency"] == "PKR"
    assert res["result"] == "ok"


# ── S5 offer ends ────────────────────────────────────────────────────────
async def test_s5_offer_ends_claims_expire_and_feed_updates(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper)
    claim = (await me.claim(offer["id"])).json()
    r = await client.post(f"/v1/shop/offers/{offer['id']}/end", headers=idem())
    assert r.status_code == 200, r.text
    await settle()
    assert (await me.get(f"/claims/{claim['claim_id']}")).json()["status"] == "expired"
    async with session_scope() as s:
        assert (await s.get(Claim, uuid.UUID(claim["claim_id"]))).status == "expired"
    assert await me.feed() == []
    assert (await scan(client, payload=claim["qr_payload"]))["result"] == "offer_ended"
    r = await me.claim(offer["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "offer_ended"


async def test_s5_offer_time_up_via_sweep(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper)
    claim = (await me.claim(offer["id"])).json()
    from shopnod_core import proposals

    clock.advance(timedelta(hours=12))
    assert await proposals.end_offers() == 1
    await settle()
    assert (await me.get(f"/claims/{claim['claim_id']}")).json()["status"] == "expired"
    assert await me.feed() == []


# ── S6 cap reached ───────────────────────────────────────────────────────
async def test_s6_cap_reached_sold_out_but_issued_claims_still_work(client, shopkeeper):
    a, b, c, d = [await new_shopper(client) for _ in range(4)]
    offer = await publish(shopkeeper, {"cap": 2})
    claims = [(await x.claim(offer["id"])).json() for x in (a, b, c)]
    assert (await scan(client, payload=claims[0]["qr_payload"]))["result"] == "ok"
    assert (await scan(client, payload=claims[1]["qr_payload"]))["result"] == "ok"
    await settle()
    async with session_scope() as s:
        assert (await s.get(Offer, uuid.UUID(offer["id"]))).status == "sold_out"
    r = await d.claim(offer["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "offer_sold_out"
    assert (await scan(client, payload=claims[2]["qr_payload"]))["result"] == "ok"  # issued before sold out
    assert await d.feed() == []


# ── S7 shopper numbers → shop stats ──────────────────────────────────────
async def test_s7_reach_and_notified_shown_only_from_10(client, shopkeeper):
    for _ in range(12):
        await new_shopper(client, push=False)
    offer = await publish(shopkeeper)
    st = (await client.get(f"/v1/shop/offers/{offer['id']}/stats")).json()
    assert st["reach"]["value"] == 12 and st["notified"]["value"] == 12


async def test_s7_below_10_says_fewer_than_10(client, shopkeeper):
    for _ in range(3):
        await new_shopper(client, push=False)
    offer = await publish(shopkeeper)
    st = (await client.get(f"/v1/shop/offers/{offer['id']}/stats")).json()
    assert st["reach"] == {"value": None, "label": "fewer than 10"} and st["notified"]["label"] == "fewer than 10"


# ── S8 redemptions → quiet detection ─────────────────────────────────────
async def test_s8_simulated_redemptions_shape_the_quiet_baseline(client, shopkeeper):
    from shopnod_worker.tasks.sim import sim

    await sim.seed_shoppers(12)
    offer = await publish(shopkeeper, {"cap": 30})
    async with session_scope() as s:
        sims = (await s.execute(select(Shopper).where(Shopper.is_simulated.is_(True)))).scalars().all()
        claims = []
        for x in sims[:12]:
            cl, _, _ = await sh.create_claim(s, x.install_id, uuid.UUID(offer["id"]))
            claims.append(cl.id)
    for cid in claims:
        assert (await sim.redeem_claim(cid))["result"] == "ok"
    # Pretend these happened at this hour on each of the last 4 weeks (3 per week): the usual is 3.
    async with session_scope() as s:
        from shopnod_core.models import Shop

        (await s.get(Shop, uuid.UUID(shopkeeper.shop_id))).created_at = NOW - timedelta(weeks=5)  # a shop with history
        reds = (await s.execute(select(Redemption).order_by(Redemption.id))).scalars().all()
        assert all(r.is_simulated and r.billable for r in reds)
        for i, r in enumerate(reds):
            r.redeemed_at = NOW - timedelta(weeks=1 + i % 4, minutes=30)
    await client.post(f"/v1/shop/offers/{offer['id']}/end", headers=idem())
    await settle()
    async with session_scope() as s:
        st = await signals.activity_stats(s, await s.get(Shop, uuid.UUID(shopkeeper.shop_id)), NOW)
    assert st["usual_for_this_hour"] == 3 and st["redemptions_last_60_min"] == 0
    created = await signals.detect_quiet()
    async with session_scope() as s:
        sig = await s.get(Signal, created[0])
    assert sig.window["via"] == "baseline" and sig.baseline == 3 and sig.observed == 0


# ── S9 dashboard QR → shopper web ────────────────────────────────────────
async def test_s9_join_market_without_location(client, shopkeeper):
    offer = await publish(shopkeeper)
    me = await new_shopper(client, consents={"location": False, "list": False, "personalisation": False}, push=False)
    feed = await me.feed()
    assert [f["offer"]["id"] for f in feed] == [offer["id"]] and feed[0]["shop"]["id"] == shopkeeper.shop_id
    r = await me.post("/location", json={"lat": 31.52, "lng": 74.35})
    assert r.status_code == 409 and r.json()["error"]["code"] == "consent_required"


# ── S10 AI outage switch ─────────────────────────────────────────────────
async def test_s10_ai_outage_both_agents_use_rules(client, shopkeeper):
    r = await client.post("/v1/admin/ai-outage", json={"enabled": True})
    assert r.status_code == 200, r.text
    me = await new_shopper(client)
    offer = await publish(shopkeeper)
    async with session_scope() as s:
        prop = (await s.execute(select(Proposal).order_by(Proposal.created_at.desc()))).scalars().first()
    assert prop.source == "rules"
    feed = await me.feed()
    assert feed[0]["offer"]["id"] == offer["id"] and feed[0]["source"] == "rules"
    matching = await _runs("matching")
    assert matching and all(x.fallback_used and x.fallback_reason == "ai_outage_flag" for x in matching)
    assert all(x.fallback_used for x in await _runs())  # the Shop Agent too


async def _runs(agent: str | None = None) -> list[AgentRun]:
    async with session_scope() as s:
        stmt = select(AgentRun)
        if agent:
            stmt = stmt.where(AgentRun.agent == agent)
        return list((await s.execute(stmt)).scalars().all())


# ── S11 delete my data ───────────────────────────────────────────────────
async def test_s11_delete_keeps_redemptions_without_install_id(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper)
    claim = (await me.claim(offer["id"])).json()
    await scan(client, payload=claim["qr_payload"])
    await settle()
    billing_before = (await client.get("/v1/shop/billing")).json()
    export = (await me.get("/me/export")).json()
    assert len(export["claims"]) == 1 and len(export["redemptions"]) == 1 and len(export["notifications"]) == 1
    assert export["shopping_list"] == BAKERY_LIST and not {"lat", "lng"} & set(export["shopper"])
    assert (await me.delete("/me")).status_code == 200
    iid = uuid.UUID(me.id)
    async with session_scope() as s:
        reds = (await s.execute(select(Redemption))).scalars().all()
    assert len(reds) == 1 and reds[0].install_id is None
    assert await count(Claim, Claim.install_id == iid) == 0 and await count(Notification, Notification.install_id == iid) == 0
    assert await count(Shopper, Shopper.install_id == iid) == 0
    assert (await client.get("/v1/shop/billing")).json()["billable_redemptions"] == billing_before["billable_redemptions"] == 1
    r = await me.get("/feed")
    assert r.status_code == 401  # the old token stops working


# ── S12 demo reset ───────────────────────────────────────────────────────
async def test_s12_demo_reset_clears_offers_claims_and_notifications(client, shopkeeper):
    me = await new_shopper(client)
    offer = await publish(shopkeeper)
    await me.claim(offer["id"])
    assert await count(Notification) == 1
    r = await client.post("/v1/shop/demo/reset")
    assert r.status_code == 200, r.text
    await settle()
    assert await count(Offer) == 0 and await count(Claim) == 0 and await count(Notification) == 0
    assert await me.feed() == []
    assert (await me.get("/claims")).json() == []


# ── shopper API basics and privacy rules ─────────────────────────────────
async def test_install_needs_age_and_token(client):
    r = await client.post("/v1/shopper/installs", json={"age_confirmed": False})
    assert r.status_code == 422 and r.json()["error"]["code"] == "age_required"
    assert (await client.get("/v1/shopper/feed")).status_code == 401
    assert (await client.get("/v1/shopper/feed", headers={"Authorization": "Bearer nope"})).status_code == 401


async def test_list_and_push_need_consent_and_consent_history_is_kept(client):
    me = await new_shopper(client, consents={"list": False, "notifications": False}, push=False)
    r = await me.put("/list", json={"items": ["milk"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "consent_required"
    r = await me.post("/push-tokens", json={"kind": "fcm", "token": "x"})
    assert r.status_code == 409
    await me.put("/consents", json={"list": True})
    assert (await me.put("/list", json={"items": ["milk"]})).json()["items"] == ["milk"]
    await me.put("/consents", json={"list": False})
    assert (await me.get("/list")).status_code == 409
    from shopnod_core.models import Consent

    async with session_scope() as s:
        rows = (await s.execute(select(Consent).where(Consent.install_id == uuid.UUID(me.id), Consent.purpose == "list"))).scalars().all()
    assert len(rows) == 1 and rows[0].withdrawn_at is not None  # granted then withdrawn, both times recorded


async def test_location_stores_only_the_cell(client):
    me = await new_shopper(client, consents={"location": True}, push=False)
    r = await me.post("/location", json={"lat": 31.520412, "lng": 74.358712})
    assert r.status_code == 200 and len(r.json()["geohash6"]) == 6
    async with session_scope() as s:
        row = await s.get(Shopper, uuid.UUID(me.id))
    assert row.geohash6 == r.json()["geohash6"] and row.area_slug is None
    assert not hasattr(row, "lat")


def test_matching_prompt_never_contains_install_id_or_coordinates():
    from shopnod_core.models import Offer as O
    from shopnod_core.models import Shop

    install_id = uuid.uuid4()
    shop = Shop(id=uuid.uuid4(), owner_id=uuid.uuid4(), name="Ali's Bakery", category="bakery", lat=31.523456, lng=74.361234)
    offer = O(id=uuid.uuid4(), shop_id=shop.id, items=[{"name": "Croissant", "category": "pastry", "was_minor": 180, "new_price_minor": 150}],
              pct=15, starts_at=NOW, ends_at=NOW + timedelta(hours=1), cap=10, redeemed_count=0)
    p = sh.Profile(list_items=["croissant"], categories=["Bakery"], language="ur")
    text = sh.matching_prompt([sh.Candidate(offer, shop, 250)], p, NOW)
    assert str(install_id) not in text and "31.52" not in text and "74.36" not in text and "Ali" not in text
    data = json.loads(text)
    assert data["offers"][0]["distance_band"] == "250–300 m" and data["shopper"]["language"] == "ur"


async def test_feed_hides_demo_shops_from_shoppers_outside_the_demo_market(client, shopkeeper):
    await publish(shopkeeper)
    me = await new_shopper(client, consents={"location": True}, push=False)
    await me.post("/location", json={"lat": 31.5204, "lng": 74.3587})
    assert await me.feed() == []


# ── Phase 2: simulated shoppers ──────────────────────────────────────────
async def test_sim_shoppers_claim_and_redeem_after_approval(client, shopkeeper, monkeypatch):
    from shopnod_worker.tasks.sim import sim

    assert await sim.seed_shoppers(40) == 40 and await sim.seed_shoppers(40) == 0  # idempotent
    await flags_on(flags.SIM_ENABLED)
    monkeypatch.setattr(sim.rng, "random", lambda: 0.0)  # every fake shopper with a score > 0 claims
    offer = await publish(shopkeeper, {"cap": 30})
    await settle()
    await settle()
    reds = await count(Redemption, Redemption.offer_id == uuid.UUID(offer["id"]), Redemption.is_simulated.is_(True))
    assert reds >= 10
    st = (await client.get(f"/v1/shop/offers/{offer['id']}/stats")).json()
    assert st["redemptions"] == reds and st["reach"]["value"] == 40
    assert await count(Outbox, Outbox.topic == "shopper.push") == 0  # fake shoppers never get real pushes
    async with session_scope() as s:
        assert (await s.execute(select(func.count()).select_from(MeterEvent))).scalar_one() == reds  # billable


async def test_sim_off_does_nothing_and_burst_makes_5(client, shopkeeper):
    from shopnod_worker.tasks.sim import sim

    await sim.seed_shoppers(10)
    offer = await publish(shopkeeper, {"cap": 30})
    assert await count(Redemption) == 0  # sim_enabled is off by default
    r = await client.post("/v1/admin/sim", json={"burst": True})
    assert r.status_code == 200, r.text
    await settle()
    await settle()
    assert await count(Redemption, Redemption.offer_id == uuid.UUID(offer["id"]), Redemption.is_simulated.is_(True)) == 5


async def flags_on(key: str) -> None:
    async with session_scope() as s:
        await flags.set_flag(s, key, True)

