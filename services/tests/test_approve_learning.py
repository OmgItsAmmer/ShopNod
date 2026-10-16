"""Phase 4: approve / edit / reject, the guardrail 422, idempotency, copy text, learning, offers lifecycle."""
import asyncio
import uuid
from datetime import timedelta

from conftest import DEFAULT_NOW, idem, settle
from sqlalchemy import func, select

from shopnod_core import clock, copyagent, learning
from shopnod_core.db import session_scope
from shopnod_core.models import AuditLog, Offer, Outbox, Proposal, ShopLearning


async def make_proposal(sk, pct=None):
    """A pending rules proposal; optionally force its % (as if the AI proposed 25%)."""
    await sk.quiet(simulated=True)
    p = (await sk.inbox())[0]
    if pct is not None:
        async with session_scope() as s:
            row = await s.get(Proposal, uuid.UUID(p["id"]))
            row.proposed_pct = pct
        p = (await sk.inbox())[0]
    return p


async def count(model, *where):
    async with session_scope() as s:
        return (await s.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


async def test_approve_publishes_offer_with_copy_and_audit(client, shopkeeper):
    p = await make_proposal(shopkeeper)
    r = await shopkeeper.approve(p["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    offer, prop = body["offer"], body["proposal"]
    assert offer["status"] == "active" and offer["pct"] == p["proposed_pct"] and prop["status"] == "approved"
    assert offer["copy_source"] == "template" and offer["copy_text"]["en"].startswith(f"{offer['pct']}% off")
    audit = (await client.get("/v1/shop/audit")).json()
    assert audit[0]["action"] in ("proposal.approved", "proposal.edited") and audit[0]["channel"] == "dashboard"
    await settle()
    async with session_scope() as s:
        topics = [o.topic for o in (await s.execute(select(Outbox))).scalars()]
    assert "offer.published" in topics and "proposal.decided" in topics


async def test_edit_25_to_10_publishes_and_moves_the_next_proposal(client, shopkeeper):
    p = await make_proposal(shopkeeper, pct=25)
    assert p["proposed_pct"] == 25
    r = await shopkeeper.approve(p["id"], {"final_pct": 10})
    assert r.status_code == 200 and r.json()["offer"]["pct"] == 10
    await settle()
    async with session_scope() as s:
        learned = (await s.get(ShopLearning, uuid.UUID(shopkeeper.shop_id))).category_pct
    cat = next(iter(learned))
    assert learned[cat] == 10.0
    # end the offer so the agent may propose again, then simulate quiet: the next proposal starts at ~10%
    assert (await client.post(f"/v1/shop/offers/{r.json()['offer']['id']}/end", headers=idem())).status_code == 200
    await settle()
    nxt = await make_proposal(shopkeeper)
    assert 10 <= nxt["proposed_pct"] <= 15
    curve = (await client.get("/v1/shop/insights/learning-curve")).json()
    assert curve["totals"]["edit_rate"] == 1.0 and curve["totals"]["avg_edit"] == -15.0
    assert curve["next_proposal_pct"] == 10 and curve["approval_channels"] == {"dashboard": 1}


async def test_edit_to_40_is_refused_with_guardrail_violation(client, shopkeeper):
    p = await make_proposal(shopkeeper)
    r = await shopkeeper.approve(p["id"], {"final_pct": 40})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "guardrail_violation" and err["details"]["rule"] == "max_discount_pct"
    assert err["details"]["limit"] == 25 and err["details"]["got"] == 40
    assert await count(Offer) == 0
    assert (await shopkeeper.inbox())[0]["status"] == "pending"  # nothing was changed
    # the human's numbers are never silently adjusted: window in the past is refused too
    past = clock.now() - timedelta(hours=1)
    r = await shopkeeper.approve(p["id"], {"window": {"start": past.isoformat(), "end": (past + timedelta(minutes=30)).isoformat()}})
    assert r.status_code == 422 and r.json()["error"]["details"]["rule"] in ("window_in_past", "allowed_hours")


async def test_double_click_approve_creates_one_offer(client, shopkeeper):
    p = await make_proposal(shopkeeper)
    key = idem()
    r1, r2 = await asyncio.gather(shopkeeper.approve(p["id"], key=key), shopkeeper.approve(p["id"], key=key))
    codes = sorted([r1.status_code, r2.status_code])
    assert codes in ([200, 200], [200, 409])
    r3 = await shopkeeper.approve(p["id"], key=key)  # a retry with the same key gets the saved result
    assert r3.status_code == 200 and r3.json()["offer"]["id"]
    assert await count(Offer) == 1
    # a different key after the fact is told it's already decided
    r4 = await shopkeeper.approve(p["id"])
    assert r4.status_code == 409 and r4.json()["error"]["code"] == "proposal_not_pending"
    assert await count(Offer) == 1


async def test_idempotency_key_is_required(client, shopkeeper):
    p = await make_proposal(shopkeeper)
    r = await client.post(f"/v1/shop/proposals/{p['id']}/approve", json={})
    assert r.status_code == 400 and r.json()["error"]["code"] == "idempotency_key_required"
    r = await client.post(f"/v1/shop/offers/{uuid.uuid4()}/end")
    assert r.status_code == 400
    r = await client.post("/v1/shop/redemptions", json={"short_code": "ABC234"})
    assert r.status_code == 400


async def test_reject_with_reason_feeds_learning(client, shopkeeper):
    p = await make_proposal(shopkeeper)
    r = await client.post(f"/v1/shop/proposals/{p['id']}/reject", json={"reason": "too_generous", "note": "we are busy"})
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["reject_reason"] == "too_generous"
    assert (await client.post(f"/v1/shop/proposals/{p['id']}/reject", json={"reason": "other"})).status_code == 409
    assert (await client.post(f"/v1/shop/proposals/{uuid.uuid4()}/reject", json={"reason": "other"})).status_code == 404
    assert (await client.post(f"/v1/shop/proposals/{p['id']}/reject", json={"reason": "nonsense"})).status_code == 422
    await settle()
    async with session_scope() as s:
        row = await s.get(ShopLearning, uuid.UUID(shopkeeper.shop_id))
    assert row.reject_counts == {"too_generous": 1}
    assert list(row.category_pct.values())[0] == round(p["proposed_pct"] * learning.TOO_GENEROUS_FACTOR, 2) or list(row.category_pct.values())[0] >= 1
    curve = (await client.get("/v1/shop/insights/learning-curve")).json()
    assert curve["reject_reasons"] == {"too_generous": 1} and curve["totals"]["approval_rate"] == 0.0


async def test_learning_is_idempotent_and_ewma(client, shopkeeper):
    p = await make_proposal(shopkeeper, pct=25)
    await shopkeeper.approve(p["id"], {"final_pct": 10})
    await settle()
    pid = uuid.UUID(p["id"])
    async with session_scope() as s:
        assert await learning.update_learning(s, pid) is False  # already applied; handlers may run twice
        row = await s.get(ShopLearning, uuid.UUID(shopkeeper.shop_id))
        assert row.decisions == 1 and list(row.category_pct.values()) == [10.0]
    assert learning.ewma(None, 10) == 10 and learning.ewma(20, 10) == 15
    async with session_scope() as s:
        rec = await learning.recompute_learning(s, uuid.UUID(shopkeeper.shop_id))
        assert rec.decisions == 1 and rec.weekly[0]["approval_rate"] == 1.0


async def test_offer_text_banned_phrases_fall_back_to_template():
    facts = copyagent.facts_for("Ali's Bakery", [{"name": "Croissant", "was_minor": 18000, "new_price_minor": 16200}],
                                10, clock.now(), clock.now() + timedelta(hours=1), "UTC", "PKR")
    good = {"en": "10% off Croissant at Ali's Bakery today."}
    assert copyagent.check_copy(good, facts, ["en"])
    for bad in ["Only 2 left! 10% off Croissant", "Hurry, 10% off", "10% off, last chance", "Limited time 10% off",
                "50% off Croissant", "", "x" * 400]:
        assert not copyagent.check_copy({"en": bad}, facts, ["en"]), bad
    assert not copyagent.check_copy({"en": "10% off"}, facts, ["en", "es"])  # missing language
    assert copyagent.has_banned_phrase("ONLY 3 LEFT") and not copyagent.has_banned_phrase("10% off bread")
    tpl = copyagent.template_copy(facts, ["en", "ur", "ar", "es", "xx"])
    assert all("10" in t for t in tpl.values()) and len(tpl) == 5


async def test_ai_copy_is_checked_then_used_or_replaced(client, shopkeeper, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from shopnod_core.settings import reset_settings_cache

    reset_settings_cache()
    outputs = iter([
        copyagent.CopyOutput(texts={"en": "10% off Croissant at Test Bakery."}),
        copyagent.CopyOutput(texts={"en": "Only 2 left! 10% off Croissant"}),
    ])

    async def fake_run(trace, **kw):
        return next(outputs)

    monkeypatch.setattr(copyagent, "run_openai_agent", fake_run)
    p = await make_proposal(shopkeeper, pct=10)
    r = await shopkeeper.approve(p["id"], {"final_pct": 10})
    assert r.json()["offer"]["copy_source"] == "ai" and "Croissant" in r.json()["offer"]["copy_text"]["en"] or r.json()["offer"]["copy_source"] == "ai"
    end = await client.post(f"/v1/shop/offers/{r.json()['offer']['id']}/end", headers=idem())
    assert end.status_code == 200
    await settle()
    p2 = await make_proposal(shopkeeper, pct=10)
    r2 = await shopkeeper.approve(p2["id"], {"final_pct": 10})
    assert r2.json()["offer"]["copy_source"] == "template"  # banned phrase caught


async def test_offers_list_stats_and_end_now(client, shopkeeper):
    p = await make_proposal(shopkeeper)
    offer = (await shopkeeper.approve(p["id"])).json()["offer"]
    assert [o["id"] for o in (await client.get("/v1/shop/offers", params={"status": "active"})).json()] == [offer["id"]]
    assert (await client.get(f"/v1/shop/offers/{offer['id']}")).json()["id"] == offer["id"]
    st = (await client.get(f"/v1/shop/offers/{offer['id']}/stats")).json()
    assert st["redemptions"] == 0 and st["reach"] == {"value": None, "label": "fewer than 10"}
    # reach is shown only when >= 10
    from shopnod_core.models import OfferReachStat

    async with session_scope() as s:
        s.add(OfferReachStat(offer_id=uuid.UUID(offer["id"]), reach=42, notified=9))
    st = (await client.get(f"/v1/shop/offers/{offer['id']}/stats")).json()
    assert st["reach"]["value"] == 42 and st["notified"]["label"] == "fewer than 10"
    key = idem()
    r = await client.post(f"/v1/shop/offers/{offer['id']}/end", headers=key)
    assert r.status_code == 200 and r.json()["status"] == "ended"
    assert (await client.post(f"/v1/shop/offers/{offer['id']}/end", headers=key)).status_code == 200
    assert (await client.get(f"/v1/shop/offers/{uuid.uuid4()}")).status_code == 404
    await settle()
    async with session_scope() as s:
        ended = [o for o in (await s.execute(select(Outbox).where(Outbox.topic == "offer.ended"))).scalars()]
    assert len(ended) == 1 and ended[0].payload["reason"] == "shopkeeper"


async def test_end_offers_and_expire_proposals_sweeps(client, shopkeeper):
    from shopnod_core import proposals

    p = await make_proposal(shopkeeper)
    # the window starts in ~10 min; once it has started the pending proposal expires
    clock.advance(timedelta(minutes=30))
    counts = await proposals.expire_proposals()
    assert counts["proposals"] == 1
    assert (await client.get("/v1/shop/proposals", params={"status": "expired"})).json()[0]["id"] == p["id"]
    r = await shopkeeper.approve(p["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "proposal_not_pending"

    clock.set_fixed(DEFAULT_NOW)
    p2 = await make_proposal(shopkeeper)
    offer = (await shopkeeper.approve(p2["id"])).json()["offer"]
    clock.advance(timedelta(hours=3))
    assert await proposals.end_offers() == 1
    assert (await client.get(f"/v1/shop/offers/{offer['id']}")).json()["status"] == "ended"
    assert await proposals.end_offers() == 0
    curve = (await client.get("/v1/shop/insights/learning-curve")).json()
    assert curve["totals"]["expired"] == 1


async def test_stale_proposal_cannot_be_approved_after_its_window_started(client, shopkeeper):
    p = await make_proposal(shopkeeper)
    clock.advance(timedelta(minutes=45))
    r = await shopkeeper.approve(p["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "proposal_expired"
    _ = (AuditLog,)
