"""Phase 5: scan -> redeem (every result), impact tiles, and billing (the usage ledger: one row per redemption)."""
import asyncio
import sys
import uuid
from datetime import timedelta
from pathlib import Path

from conftest import idem, onboard, settle
from sqlalchemy import select

from shopnod_core import billing, clock, redeem
from shopnod_core.db import session_scope
from shopnod_core.models import Claim, MeterEvent, Offer, Redemption

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "seed"))
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
    assert len(meters) == 1 and meters[0].status == "recorded" and meters[0].identifier == res["redemption_id"]
    b = (await client.get("/v1/shop/billing")).json()
    assert b["billable_redemptions"] == 1 and b["redemptions_today"] == 1 and b["upcoming_invoice_usd_cents"] == 10
    assert b["usage_recorded"] == 1 and b["demo"] is True
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


# ── billing ledger ───────────────────────────────────────────────────────
async def test_usage_is_recorded_once_per_redemption_even_if_the_handler_runs_twice(client, shopkeeper):
    offer = await live_offer(shopkeeper, 10)
    res = await scan(client, payload=(await dev_claim.make_claim(offer["id"]))["qr_text"])
    await settle()
    assert await billing.meter_redemption(uuid.UUID(res["redemption_id"])) == "recorded"  # the same event again
    assert len(await rows(MeterEvent)) == 1
    b = (await client.get("/v1/shop/billing")).json()
    assert b["billable_redemptions"] == 1 and b["usage_recorded"] == 1 and b["upcoming_invoice_usd_cents"] == 10


async def test_no_payment_endpoints_or_webhooks(client, shopkeeper):
    for path in ("/v1/shop/billing/checkout-pro", "/v1/shop/billing/portal", "/webhooks/stripe"):
        assert (await client.post(path)).status_code in (404, 405)
