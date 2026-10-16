"""Phase 5: scan -> redeem (every result), impact tiles, billing, Stripe meter events and webhooks."""
import asyncio
import hashlib
import hmac
import json
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from conftest import idem, onboard, settle
from shopnod_core import billing, clock, redeem
from shopnod_core.db import session_scope
from shopnod_core.models import Claim, MeterEvent, Offer, Redemption, Shop

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "seed"))
import dev_claim  # noqa: E402


async def live_offer(sk, pct=None):
    await sk.quiet(simulated=True)
    pid = (await sk.inbox())[0]["id"]
    body = {"final_pct": pct} if pct else {}
    r = await sk.approve(pid, body)
    assert r.status_code == 200, r.text
    await settle()
    return r.json()["offer"]


async def scan(client, payload=None, code=None, key=None):
    body = {"payload": payload} if payload else {"short_code": code}
    r = await client.post("/v1/shop/redemptions", json=body, headers=key or idem())
    assert r.status_code == 200, r.text
    return r.json()


async def rows(model, *where):
    async with session_scope() as s:
        return (await s.execute(select(model).where(*where))).scalars().all()


async def test_scan_ok_then_already_redeemed_and_billing_counts_one(client, shopkeeper):
    offer = await live_offer(shopkeeper, 10)
    c = await dev_claim.make_claim(offer["id"])
    assert c["qr_text"].startswith("SN1:") and len(c["short_code"]) == 6
    res = await scan(client, payload=c["qr_text"])
    assert res["result"] == "ok" and res["discount_pct"] == 10 and res["message"] == "Apply 10% to this customer's items."
    assert res["items"][0]["new_price_minor"] < res["items"][0]["was_minor"]
    again = await scan(client, payload=c["qr_text"])
    assert again["result"] == "already_redeemed"
    assert len(await rows(Redemption)) == 1
    await settle()
    meters = await rows(MeterEvent)
    assert len(meters) == 1 and meters[0].status == "skipped" and meters[0].identifier == res["redemption_id"]
    b = (await client.get("/v1/shop/billing")).json()
    assert b["billable_redemptions"] == 1 and b["redemptions_today"] == 1 and b["upcoming_invoice_usd_cents"] == 10
    assert b["stripe_configured"] is False and b["test_mode"] is True
    offer_after = (await client.get(f"/v1/shop/offers/{offer['id']}")).json()
    assert offer_after["redeemed_count"] == 1


async def test_short_code_wrong_shop_invalid_and_expired(client, shopkeeper):
    offer = await live_offer(shopkeeper, 10)
    c = await dev_claim.make_claim(offer["id"])
    spaced = c["short_code"][:3].lower() + " " + c["short_code"][3:]
    # a second shop (new user) tries to redeem this shop's claim
    other = await onboard(client, "cafe", "Other Cafe")
    assert (await scan(client, code=c["short_code"]))["result"] == "wrong_shop"
    assert (await scan(client, payload=c["qr_text"]))["result"] == "wrong_shop"
    assert (await scan(client, payload="SN1:garbage"))["result"] == "invalid"
    assert (await scan(client, payload="not-a-shn-code"))["result"] == "invalid"
    assert (await scan(client, code="ZZZZZZ"))["result"] == "invalid"
    # back to the owner
    await client.post("/v1/auth/logout")
    _ = other
    login = await client.post("/v1/auth/demo-login")
    assert login.status_code == 200  # a different user again: still wrong shop
    # use the original shopkeeper's identity via a fresh client cookie is impossible, so redeem at the core level
    ok = await redeem.redeem(uuid.UUID(shopkeeper.shop_id), short_code=spaced)
    assert ok["result"] == "ok"
    c2 = await dev_claim.make_claim(offer["id"])
    clock.advance(timedelta(minutes=31))
    assert (await redeem.redeem(uuid.UUID(shopkeeper.shop_id), short_code=c2["short_code"]))["result"] == "expired"
    assert (await redeem.redeem(uuid.UUID(shopkeeper.shop_id), payload=c2["qr_text"]))["result"] == "expired"


async def test_offer_ended_and_sold_out_rules(client, shopkeeper):
    offer = await live_offer(shopkeeper, 10)
    c1, c2, c3 = [await dev_claim.make_claim(offer["id"]) for _ in range(3)]
    sid = uuid.UUID(shopkeeper.shop_id)
    async with session_scope() as s:
        (await s.get(Offer, uuid.UUID(offer["id"]))).cap = 1
    assert (await redeem.redeem(sid, payload=c1["qr_text"]))["result"] == "ok"
    assert (await client.get(f"/v1/shop/offers/{offer['id']}")).json()["status"] == "sold_out"
    # claims already issued still work until they expire
    assert (await redeem.redeem(sid, payload=c2["qr_text"]))["result"] == "ok"
    r = await client.post(f"/v1/shop/offers/{offer['id']}/end", headers=idem())
    assert r.status_code == 200
    assert (await redeem.redeem(sid, payload=c3["qr_text"]))["result"] == "offer_ended"
    assert (await redeem.redeem(sid, short_code=c3["short_code"]))["result"] == "offer_ended"


async def test_same_scan_twice_with_same_key_returns_saved_result(client, shopkeeper):
    offer = await live_offer(shopkeeper)
    c = await dev_claim.make_claim(offer["id"])
    key = idem()
    a = await scan(client, payload=c["qr_text"], key=key)
    b = await scan(client, payload=c["qr_text"], key=key)
    assert a == b and a["result"] == "ok" and len(await rows(Redemption)) == 1


async def test_two_counters_scanning_one_claim_at_once_redeem_once(client, shopkeeper):
    offer = await live_offer(shopkeeper)
    c = await dev_claim.make_claim(offer["id"])
    sid = uuid.UUID(shopkeeper.shop_id)
    results = await asyncio.gather(*[redeem.redeem(sid, payload=c["qr_text"]) for _ in range(4)])
    assert sorted(r["result"] for r in results).count("ok") == 1
    assert len(await rows(Redemption)) == 1 and len(await rows(Claim, Claim.status == "redeemed")) == 1


async def test_validation_and_impact_tiles(client, shopkeeper):
    r = await client.post("/v1/shop/redemptions", json={}, headers=idem())
    assert r.status_code == 422
    offer = await live_offer(shopkeeper, 10)
    for _ in range(3):
        c = await dev_claim.make_claim(offer["id"])
        assert (await scan(client, payload=c["qr_text"]))["result"] == "ok"
    await settle()
    t = (await client.get("/v1/shop/insights/summary")).json()
    assert t["redemptions_today"] == 3 and t["extra_customers"] == 3 and t["extra_customers_is_estimate"] and t["roi_is_estimate"]
    assert t["discount_given_minor"] > 0 and t["margin_kept_minor"] > 0 and t["waste_avoided_units"] >= 0
    assert t["currency"] == "PKR"


# ── Stripe ───────────────────────────────────────────────────────────────
class FakeStripe:
    def __init__(self):
        self.meter_calls, self.customers = [], []
        self.billing = SimpleNamespace(MeterEvent=SimpleNamespace(create=self._meter))
        self.Customer = SimpleNamespace(create=self._customer)
        self.Subscription = SimpleNamespace(create=lambda **kw: {"id": "sub_test_1"})
        self.checkout = SimpleNamespace(Session=SimpleNamespace(create=lambda **kw: {"url": "https://checkout.stripe.test/s/1", "kw": kw}))
        self.billing_portal = SimpleNamespace(Session=SimpleNamespace(create=lambda **kw: {"url": "https://portal.stripe.test/p/1"}))

    def _meter(self, **kw):
        if any(c["identifier"] == kw["identifier"] for c in self.meter_calls):
            return {"identifier": kw["identifier"], "duplicate": True}  # Stripe ignores duplicates
        self.meter_calls.append(kw)
        return {"identifier": kw["identifier"]}

    def _customer(self, **kw):
        self.customers.append(kw)
        return {"id": "cus_test_1"}


@pytest.fixture
def fake_stripe(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_pro")
    monkeypatch.setenv("STRIPE_METERED_PRICE_ID", "price_metered")
    from shopnod_core.settings import reset_settings_cache

    reset_settings_cache()
    fs = FakeStripe()
    monkeypatch.setattr(billing, "_stripe", lambda: fs)
    return fs


async def test_stripe_customer_created_on_complete_and_meter_event_once(client, fake_stripe):
    sk = await onboard(client)  # completes the wizard -> shop.completed -> create_stripe_customer
    async with session_scope() as s:
        assert (await s.get(Shop, uuid.UUID(sk.shop_id))).stripe_customer_id == "cus_test_1"
    assert fake_stripe.customers[0]["metadata"] == {"shop_id": sk.shop_id}
    offer = await live_offer(sk, 10)
    c = await dev_claim.make_claim(offer["id"])
    res = await scan(client, payload=c["qr_text"])
    await settle()
    assert len(fake_stripe.meter_calls) == 1
    call = fake_stripe.meter_calls[0]
    assert call["identifier"] == res["redemption_id"] and call["payload"] == {"stripe_customer_id": "cus_test_1", "value": "1"}
    assert (await rows(MeterEvent))[0].status == "sent"
    # replaying the same event/handler changes nothing (Stripe also dedupes on `identifier`)
    assert await billing.meter_redemption(uuid.UUID(res["redemption_id"])) == "sent"
    assert len(fake_stripe.meter_calls) == 1
    b = (await client.get("/v1/shop/billing")).json()
    assert b["meter_events_sent"] == 1 and b["billable_redemptions"] == 1 and b["stripe_customer"] is True


async def test_meter_failure_is_retried_by_the_outbox(client, fake_stripe, monkeypatch):
    sk = await onboard(client)
    offer = await live_offer(sk, 10)
    boom = {"n": 0}
    real = fake_stripe._meter

    def flaky(**kw):
        boom["n"] += 1
        if boom["n"] == 1:
            raise RuntimeError("stripe 500")
        return real(**kw)

    fake_stripe.billing.MeterEvent.create = flaky
    c = await dev_claim.make_claim(offer["id"])
    await scan(client, payload=c["qr_text"])
    await settle()
    assert (await rows(MeterEvent))[0].status == "failed"
    from shopnod_core.models import Outbox

    pending = [o for o in await rows(Outbox, Outbox.topic == "redemption.recorded")][0]
    assert pending.status == "pending" and pending.attempts == 1
    clock.advance(timedelta(seconds=30))
    await settle()
    assert (await rows(MeterEvent))[0].status == "sent" and len(fake_stripe.meter_calls) == 1


def sign(payload: bytes, secret="whsec_test_secret", ts=None):
    ts = ts or int(clock.now().timestamp())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def stripe_event(evt_id, typ, obj):
    return json.dumps({"id": evt_id, "type": typ, "data": {"object": obj}}).encode()


async def test_webhook_signature_replay_and_upgrade(client, shopkeeper):
    payload = stripe_event("evt_1", "checkout.session.completed", {"customer": "cus_9", "subscription": "sub_9", "metadata": {"shop_id": shopkeeper.shop_id}})
    bad = await client.post("/webhooks/stripe", content=payload, headers={"stripe-signature": "t=1,v1=deadbeef"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "webhook_signature_invalid"
    assert (await client.post("/webhooks/stripe", content=payload)).status_code == 400
    old = await client.post("/webhooks/stripe", content=payload, headers={"stripe-signature": sign(payload, ts=int(clock.now().timestamp()) - 3600)})
    assert old.status_code == 400
    ok = await client.post("/webhooks/stripe", content=payload, headers={"stripe-signature": sign(payload)})
    assert ok.status_code == 200
    replay = await client.post("/webhooks/stripe", content=payload, headers={"stripe-signature": sign(payload)})
    assert replay.status_code == 200
    async with session_scope() as s:
        shop = await s.get(Shop, uuid.UUID(shopkeeper.shop_id))
        from shopnod_core.models import Subscription

        subs = (await s.execute(select(func.count()).select_from(Subscription).where(Subscription.stripe_subscription_id == "sub_9"))).scalar_one()
    assert shop.plan == "pro" and shop.stripe_customer_id == "cus_9" and subs == 1  # replay changed nothing
    cancel = stripe_event("evt_2", "customer.subscription.deleted", {"id": "sub_9", "status": "canceled"})
    await client.post("/webhooks/stripe", content=cancel, headers={"stripe-signature": sign(cancel)})
    async with session_scope() as s:
        assert (await s.get(Shop, uuid.UUID(shopkeeper.shop_id))).plan == "free"


async def test_checkout_and_portal(client, shopkeeper, fake_stripe):
    r = await client.post("/v1/shop/billing/checkout-pro")
    assert r.status_code == 200 and r.json()["url"].startswith("https://checkout.stripe.test")
    assert (await client.post("/v1/shop/billing/portal")).json()["url"].startswith("https://portal.stripe.test")


async def test_billing_degrades_without_stripe(client, shopkeeper):
    r = await client.post("/v1/shop/billing/checkout-pro")
    assert r.status_code == 503 and r.json()["error"]["code"] == "billing_unavailable"
    assert (await client.post("/v1/shop/billing/portal")).status_code == 503
