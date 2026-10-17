"""Auto-predict: context first (time, weather, payday), basket completion, market priors, shop-side urgency, and learning
from behaviour with a confidence that grows with the evidence. See core/predict.py."""
import uuid
from datetime import timedelta

import httpx
from conftest import NOW, settle
from sqlalchemy import select
from test_integration import new_shopper, publish

from shopnod_core import context, geo, predict, templates
from shopnod_core import shopper as sh
from shopnod_core.context import Context
from shopnod_core.db import session_scope
from shopnod_core.models import Claim, Item, Notification, Offer, Shop, Shopper, User

CROISSANT = [("Croissant", "pastry")]
ICED_TEA = [("Iced tea", "drinks")]
EGGS = [("Eggs (dozen)", "eggs")]
RICE = [("Rice 5kg", "pantry")]
BREAD = [("White bread", "bread")]
COFFEE = [("Latte", "coffee")]


def feats(items, cat="Bakery", shop="s1"):
    return predict.features_of([{"name": n, "category": c} for n, c in items], cat, shop)


def score(items, *, ctx=Context(), profile=None, cat="Bakery", distance=200, market=None, expires=None, claimed=0):
    """Prediction for one offer in the demo market at the fixed test time (Tuesday 11:00 Karachi = midday)."""
    p = profile or predict.PredictProfile(personalised=True)
    return predict.predict(
        p, feats(items, cat), shop_name="Ali's", distance_m=distance, max_distance_m=800, minutes_left=120, discount_pct=15,
        claimed=claimed, cap=30, expires_in_h=expires, now=NOW, tz="Asia/Karachi", ctx=ctx, market=market,
    )


# ── words ────────────────────────────────────────────────────────────────
def test_words_match_across_plurals_and_everyday_synonyms():
    st = lambda text: {s for s, _ in predict.words(text)}  # noqa: E731
    assert st("cookies") & st("Chocolate cookie")
    assert st("tomatoes") == st("Tomatoes (kg)")
    assert st("anda") & st("Eggs (dozen)")  # Urdu in Latin letters
    assert st("chai") & st("Iced tea")
    assert st("loaf") & st("White bread")
    assert "kg" not in st("Rice 5kg") and "dozen" not in st("Eggs (dozen)")


def test_context_classification_from_weather_codes():
    assert context.classify(61, 20, 0) == "rain"
    assert context.classify(0, 20, 2.5) == "rain"
    assert context.classify(0, 38, 0) == "hot"
    assert context.classify(0, 8, 0) == "cold"
    assert context.classify(1, 24, 0) == "clear"


# ── context: time and weather ────────────────────────────────────────────
def test_rain_prefers_warm_treats_and_avoids_iced_drinks():
    rain = Context(weather="rain", temp_c=22)
    warm, cold = score(CROISSANT, ctx=rain), score(ICED_TEA, ctx=rain, cat="Café")
    assert warm.score > cold.score + 0.2
    assert warm.why == "Rainy day: warm treats" and "context" in warm.parts and "context" not in cold.parts


def test_heat_prefers_cool_things():
    hot = Context(weather="hot", temp_c=37)
    assert score(ICED_TEA, ctx=hot, cat="Café").score > score(COFFEE, ctx=hot, cat="Café").score + 0.2
    assert score(ICED_TEA, ctx=hot, cat="Café").why == "Hot day: something cool"


def test_time_of_day_shifts_what_comes_first():
    morning, night = Context(daypart_override="morning"), Context(daypart_override="midday")
    assert score(BREAD, ctx=morning).why == "Good for breakfast"
    assert "context" not in score(CROISSANT + ICED_TEA, ctx=night).parts or score(BREAD, ctx=night).score < score(BREAD, ctx=morning).score
    assert score(RICE, ctx=night, cat="Groceries").why == "Lunch time"


def test_no_signals_at_all_still_gives_a_sensible_cold_start_ranking():
    near, far = score(BREAD, distance=100), score(BREAD, distance=700)
    assert 0 < far.score < near.score < 0.35  # distance and urgency only: never strong enough to notify anyone
    assert near.reasons == ["Near you"]


# ── basket completion, stated interest ───────────────────────────────────
def test_basket_completion_from_one_list_item():
    p = predict.PredictProfile.basic(["bread"], [])
    eggs = score(EGGS, profile=p, cat="Groceries")
    assert eggs.why == "Goes with your bread" and eggs.parts["basket"] > 0.3
    assert score(BREAD, profile=p).why == "On your list: bread"  # a direct hit beats a complement
    assert "basket" not in score(BREAD, profile=p).parts


def test_picked_category_is_a_gentle_prior_not_a_command():
    p = predict.PredictProfile.basic([], ["Bakery"])
    s = score(CROISSANT, profile=p)
    assert s.why == "You like Bakery" and 0.3 < s.score < 0.55


def test_signals_combine_and_never_cancel_each_other():
    p = predict.PredictProfile.basic(["croissant"], ["Bakery"])
    rain = Context(weather="rain")
    alone, together = score(CROISSANT, profile=p), score(CROISSANT, profile=p, ctx=rain)
    assert together.score >= alone.score >= 0.6
    assert len(together.reasons) == 3


# ── shop side and market ─────────────────────────────────────────────────
def test_stock_that_must_go_today_is_lifted():
    plain, urgent = score(CROISSANT), score(CROISSANT, expires=6)
    assert urgent.score > plain.score and urgent.parts["waste"] > 0
    assert "waste" not in score(CROISSANT, expires=60).parts


def test_market_pattern_needs_enough_different_people():
    idx = predict.MarketIndex()
    idx.part_claims["midday"] = 20
    idx.cat_part_claims[("Bakery", "midday")] = 12
    idx.cat_part_shoppers[("Bakery", "midday")] = {uuid.uuid4() for _ in range(4)}  # only 4 people: ignored
    assert idx.share("Bakery", "midday") is None and "market" not in score(CROISSANT, market=idx).parts
    idx.cat_part_shoppers[("Bakery", "midday")] = {uuid.uuid4() for _ in range(5)}
    assert idx.share("Bakery", "midday") == 0.6
    s = score(CROISSANT, market=idx)
    assert s.parts["market"] > 0.2 and s.why == "Popular at lunchtime"


# ── learning from behaviour: more evidence, more trust ───────────────────
def test_learning_is_trusted_in_proportion_to_the_evidence():
    def learned(weight):
        p = predict.PredictProfile(personalised=True)
        predict._apply(p, feats(CROISSANT), weight, NOW, NOW)
        return score(CROISSANT, profile=p).parts.get("learned", 0.0)

    one_open, a_claim, redeemed_claim = learned(1.0), learned(3.0), learned(8.0)
    assert 0 < one_open < a_claim < redeemed_claim <= predict.CAP["learned"]


def test_recent_behaviour_counts_more_than_old():
    now_p, old_p = predict.PredictProfile(personalised=True), predict.PredictProfile(personalised=True)
    predict._apply(now_p, feats(CROISSANT), 3.0, NOW, NOW)
    predict._apply(old_p, feats(CROISSANT), 3.0, NOW - timedelta(days=28), NOW)  # two half-lives
    assert abs(old_p.tok["pastri"] - 0.75) < 1e-6 and now_p.tok["pastri"] == 3.0


def test_a_dislike_pushes_similar_offers_down():
    p = predict.PredictProfile.basic([], ["Bakery"])
    base = score(CROISSANT, profile=p).score
    predict._apply(p, feats(CROISSANT), -3.0, NOW, NOW)
    assert score(CROISSANT, profile=p).score < base * 0.85


# ── weather service ──────────────────────────────────────────────────────
class _FakeClient:
    """Stands in for httpx.AsyncClient with a canned Open-Meteo reply (or an error)."""

    calls = 0
    reply: dict | Exception = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        _FakeClient.calls += 1
        if isinstance(_FakeClient.reply, Exception):
            raise _FakeClient.reply
        return httpx.Response(200, json=_FakeClient.reply, request=httpx.Request("GET", url))


async def test_weather_is_read_from_the_area_cached_and_never_breaks_the_feed(env, monkeypatch):
    from shopnod_core.settings import reset_settings_cache

    monkeypatch.setenv("WEATHER_ENABLED", "true")
    reset_settings_cache()
    monkeypatch.setattr(context.httpx, "AsyncClient", _FakeClient)
    gh = geo.encode(31.5204, 74.3587, 6)
    _FakeClient.calls, _FakeClient.reply = 0, {"current": {"temperature_2m": 24.0, "precipitation": 1.2, "weather_code": 61}}
    assert await context.get_weather(gh) == ("rain", 24.0)
    assert await context.get_weather(gh) == ("rain", 24.0) and _FakeClient.calls == 1  # cached for 30 minutes
    context.clear_weather_cache()
    _FakeClient.reply = httpx.ConnectError("down")
    assert await context.get_weather(gh) == ("unknown", None)  # a failure is quietly tolerated
    assert await context.get_weather(None) == ("unknown", None)


# ── end to end through the API ───────────────────────────────────────────
async def seed_offer(name: str, shop_cat: str, items: list[tuple[str, str]], *, expires_in_h: float | None = None) -> str:
    """A live offer from a demo shop, inserted directly so a test can have shops of any kind."""
    async with session_scope() as s:
        area = await templates.ensure_demo_market(s)
        user = User(email=f"{uuid.uuid4().hex}@t.local", is_demo=True)
        s.add(user)
        await s.flush()
        shop = Shop(owner_id=user.id, name=name, category=shop_cat, is_demo=True, timezone=templates.DEMO_TZ, currency="PKR", onboarding_status="complete")
        templates.set_location(shop, *templates.demo_spot(0), area)
        s.add(shop)
        await s.flush()
        rows = []
        for nm, cat in items:
            it = Item(shop_id=shop.id, name=nm, category=cat, price_minor=1000, regular_price_minor=1000, quantity=5,
                      expires_at=NOW + timedelta(hours=expires_in_h) if expires_in_h else None)
            s.add(it)
            await s.flush()
            rows.append({"item_id": str(it.id), "name": nm, "category": cat, "was_minor": 1000, "new_price_minor": 850})
        offer = Offer(shop_id=shop.id, area_id=area.id, geohash6=shop.geohash6, items=rows, pct=15, starts_at=NOW - timedelta(minutes=5),
                      ends_at=NOW + timedelta(hours=3), cap=30, status="active", copy={"en": "Offer"}, copy_source="template", created_at=NOW)
        s.add(offer)
        await s.flush()
        return str(offer.id)


async def blank_shopper(client, **kw):
    """A shopper who told us nothing: no list, no categories. Only context can help."""
    me = await new_shopper(client, items=[], push=False, **kw)
    assert (await me.put("/preferences", json={"categories": []})).status_code == 200
    return me


async def order(me) -> list[str]:
    return [f["offer"]["id"] for f in await me.feed()]


async def test_a_shopper_who_typed_nothing_still_gets_a_good_feed_from_context(client):
    warm = await seed_offer("Ali's Bakery", "bakery", CROISSANT)
    cool = await seed_offer("Chai Corner", "cafe", ICED_TEA)
    me = await blank_shopper(client)
    r = await me.put("/demo-context", json={"weather": "rain", "daypart": "evening"})
    assert r.status_code == 200 and r.json()["summary"] == "Rainy evening · 22°C" and r.json()["pretend"] == {"weather": "rain", "daypart": "evening"}
    feed = await me.feed()
    assert [f["offer"]["id"] for f in feed] == [warm, cool]
    assert feed[0]["reasons"][0] == "Rainy day: warm treats" and feed[0]["score"] > feed[1]["score"] + 0.15
    await me.put("/demo-context", json={"weather": "hot", "daypart": "midday"})
    feed = await me.feed()
    assert [f["offer"]["id"] for f in feed] == [cool, warm] and feed[0]["reasons"][0] == "Hot day: something cool"
    await me.put("/demo-context", json={})
    assert (await me.get("/context")).json()["pretend"] == {"weather": None, "daypart": None}


async def test_pretending_is_per_shopper_and_only_in_demo_mode(client, monkeypatch):
    from shopnod_core.settings import reset_settings_cache

    await seed_offer("Ali's Bakery", "bakery", CROISSANT)
    a, b = await blank_shopper(client), await blank_shopper(client)
    await a.put("/demo-context", json={"weather": "rain"})
    assert (await a.feed())[0]["reasons"][0] == "Rainy day: warm treats"
    assert (await b.feed())[0]["reasons"] == ["Near you"]  # one judge flipping the switch never changes another's feed
    monkeypatch.setenv("DEMO_MODE", "false")
    reset_settings_cache()
    assert (await a.put("/demo-context", json={"weather": "hot"})).status_code == 403
    assert (await a.feed())[0]["reasons"] == ["Near you"]  # the stored override is ignored outside the demo
    assert (await a.get("/context")).json()["demo_mode"] is False


async def test_basket_completion_from_the_shopping_list(client):
    eggs = await seed_offer("Green Basket", "grocery", EGGS)
    me = await new_shopper(client, items=["bread"], push=False)
    feed = await me.feed()
    assert feed[0]["offer"]["id"] == eggs and feed[0]["reasons"][0] == "Goes with your bread"


async def test_it_adapts_within_the_same_session(client):
    a = await seed_offer("Chai Corner", "cafe", COFFEE)
    b = await seed_offer("Green Basket", "grocery", RICE)
    me = await blank_shopper(client)
    base = {f["offer"]["id"]: f["score"] for f in await me.feed()}
    await me.post("/events", json={"type": "dismiss", "offer_id": a})
    await me.post("/events", json={"type": "why_up", "offer_id": b})
    after = {f["offer"]["id"]: f for f in await me.feed()}
    assert after[a]["score"] < base[a] and after[b]["score"] > base[b]  # the very next feed already differs
    assert after[b]["reasons"][0].startswith("You've shown interest")


async def test_what_it_learned_is_visible_and_can_be_reset(client, shopkeeper):
    me = await new_shopper(client, items=[], push=False)
    offer = await publish(shopkeeper, {"final_pct": 10})
    claim = (await me.claim(offer["id"])).json()
    await client.post("/v1/shop/redemptions", json={"payload": claim["qr_payload"]}, headers={"Idempotency-Key": uuid.uuid4().hex})
    await settle()
    learned = (await me.get("/affinity")).json()
    assert learned["categories"][0]["name"] == "Bakery" and learned["interests"]  # live, not a nightly job
    assert (await me.delete("/affinity")).status_code == 200
    again = (await me.get("/affinity")).json()
    assert again["categories"] == [] and again["interests"] == []
    assert (await me.get("/list")).status_code == 200 and (await me.get("/preferences")).json()["categories"] == ["Bakery"]  # their own choices stay


async def test_without_personalisation_nothing_is_predicted(client):
    warm = await seed_offer("Ali's Bakery", "bakery", CROISSANT)
    me = await new_shopper(client, consents={"personalisation": False, "list": False}, push=False)
    await me.put("/demo-context", json={"weather": "rain"})
    await me.post("/events", json={"type": "why_up", "offer_id": warm})
    f = (await me.feed())[0]
    assert f["reasons"] == ["Near you"] and f["source"] == "rules"
    await me.put("/consents", json={"personalisation": True})
    assert (await me.feed())[0]["reasons"][0] != "Near you"


async def test_notifications_go_to_the_people_the_moment_suits(client, shopkeeper):
    """Same bakery lover, same offer: only the one whose weather fits it gets a push-worthy match."""
    rainy, sunny = await new_shopper(client, items=[], push=False), await new_shopper(client, items=[], push=False)
    await rainy.put("/demo-context", json={"weather": "rain", "daypart": "evening"})
    await sunny.put("/demo-context", json={"weather": "clear", "daypart": "midday"})
    offer = await publish(shopkeeper)
    async with session_scope() as s:
        notified = set((await s.execute(select(Notification.install_id).where(Notification.offer_id == uuid.UUID(offer["id"])))).scalars().all())
    assert uuid.UUID(rainy.id) in notified and uuid.UUID(sunny.id) not in notified


async def test_market_priors_come_from_what_enough_people_claimed(client):
    offer_id = await seed_offer("Ali's Bakery", "bakery", CROISSANT)
    async with session_scope() as s:
        for _ in range(6):
            iid = uuid.uuid4()
            s.add(Shopper(install_id=iid, geohash6=geo.encode(31.5204, 74.3587, 6), area_slug="demo", last_seen_at=NOW, created_at=NOW))
            for _ in range(2):
                s.add(Claim(offer_id=uuid.UUID(offer_id), install_id=iid, token_jti=uuid.uuid4().hex, short_code="ABCDEF", status="issued",
                            expires_at=NOW + timedelta(hours=1), created_at=NOW))  # 11:00 in Karachi = midday
    predict.clear_caches()
    async with session_scope() as s:
        market = await predict.get_market(s, NOW)
    assert market.share("Bakery", "midday") == 1.0  # 12 claims by 6 different people
    assert market.share("Bakery", "evening") is None


async def test_expiring_stock_is_flagged_in_the_feed(client):
    soon = await seed_offer("Ali's Bakery", "bakery", CROISSANT, expires_in_h=6)
    me = await blank_shopper(client)
    f = (await me.feed())[0]
    assert f["offer"]["id"] == soon and "Fresh stock that must go today" in f["reasons"]


async def test_context_endpoint_works_for_everyone(client):
    me = await blank_shopper(client)
    c = (await me.get("/context")).json()
    assert c["weather"] == "unknown" and c["daypart"] == "midday" and c["demo_mode"] is True and c["summary"] == "Midday"
    _ = sh
