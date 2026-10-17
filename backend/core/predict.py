"""Auto-predict: what a shopper probably wants right now, without them typing anything.

A brand-new shopper has no history, so the model is **context first** and learns from behaviour second:

  context      time of day, weekday, payday and the weather for their area ("rainy evening → warm snacks")
  basket       what goes with the things they mentioned or liked ("bread → eggs, butter, tea")
  market       what people near them tend to claim at this time of day (only with enough people behind it)
  shop side    stock that expires today is worth sending to people who'd want it (less food wasted)
  stated       an item on their list, or a category they picked (a few taps at most)
  learned      what they open, claim, redeem, like or dismiss, weighted by how much evidence there is

Each signal gives a probability; they are combined so that *any* strong reason can lift an offer ("noisy OR"), and a
learned dislike pushes it down. Every offer comes with the reasons behind its score, in plain words.

Privacy: everything here is gated by the `personalisation` consent (the list also needs `list`). Learned signals are
built only from this shopper's own behaviour, and market numbers are used only when enough different people are
behind them. Nothing here leaves the server; the optional AI re-rank gets scores and reason *kinds*, never ids.
"""
from __future__ import annotations

import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .context import DAYPART_PHRASE, Context, daypart_of
from .models import Claim, Consent, Offer, Redemption, Shop, ShopperEvent, ShopperPreference, ShoppingList

HALF_LIFE_DAYS = 14.0
HISTORY = timedelta(days=30)
MARKET_WINDOW = timedelta(days=14)
MARKET_MIN_SHOPPERS = 5  # k-anonymity: never use a pattern from fewer people than this
MARKET_MIN_CLAIMS = 10
MARKET_TTL_S = 600.0

# What each action says about a shopper's taste. Negative = "not for me".
ACTION_WEIGHTS = {"open": 1.0, "save": 2.0, "why_up": 2.0, "claim": 3.0, "redemption": 5.0, "why_down": -3.0, "dismiss": -3.0}

# The most any one signal can contribute to the final probability.
CAP = {"list": 0.60, "prior": 0.30, "context": 0.38, "basket": 0.34, "market": 0.28, "learned": 0.50, "waste": 0.18}


# ── words ────────────────────────────────────────────────────────────────
STOP = frozenset(
    "the and with for dozen bunch slice pack box fresh white brown large small mini bar club kg ml pcs of in a an "
    "aa pair set".split()
)
# A few everyday words (incl. Urdu in Latin letters) so a list like "anda, doodh, chai" just works.
SYNONYMS = {
    "loaf": "bread", "bun": "bread", "toast": "bread", "roti": "bread", "naan": "bread", "sourdough": "bread",
    "anda": "egg", "doodh": "milk", "chai": "tea", "dahi": "yoghurt", "curd": "yoghurt", "lassi": "yoghurt",
    "chawal": "rice", "juice": "drink", "soda": "drink", "samosa": "snack", "pakora": "snack", "chips": "snack",
    "cappuccino": "coffee", "latte": "coffee", "espresso": "coffee", "croissant": "pastry", "cookies": "biscuit",
    "cookie": "biscuit", "cake": "dessert", "brownie": "dessert", "yogurt": "yoghurt",
}


def stem(word: str) -> str:
    """Cheap, consistent stemming applied to both sides ('cookies'/'cookie', 'tomatoes'/'tomato', 'battery'/'batteries')."""
    w = word.lower()
    if w in SYNONYMS:
        w = SYNONYMS[w]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    if len(w) > 3 and w.endswith("y"):
        w = w[:-1] + "i"
    return w


def words(text: str) -> list[tuple[str, str]]:
    """[(stem, original word)] for the useful words of a text."""
    out = []
    for raw in re.findall(r"[A-Za-z]+", text or ""):
        low = raw.lower()
        if len(low) < 3 or low in STOP:
            continue
        out.append((stem(low), SYNONYMS.get(low, low)))
    return out


@dataclass
class Features:
    """What an offer is about, as comparable tokens."""

    cat: str
    shop_id: str
    toks: frozenset[str]
    display: dict[str, str]

    def to_json(self) -> dict[str, Any]:
        return {"cat": self.cat, "shop": self.shop_id, "toks": sorted(self.toks), "disp": self.display}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Features:
        return cls(str(d.get("cat", "")), str(d.get("shop", "")), frozenset(d.get("toks", [])), dict(d.get("disp", {})))


def features_of(items: list[dict[str, Any]], category_label: str, shop_id: str) -> Features:
    toks: set[str] = set()
    disp: dict[str, str] = {}
    for it in items or []:
        for text in (str(it.get("name", "")), str(it.get("category", ""))):
            for st, shown in words(text):
                toks.add(st)
                disp.setdefault(st, shown)
    return Features(category_label, shop_id, frozenset(toks), disp)


# ── context rules (readable on purpose: this is the "knowledge") ─────────
@dataclass(frozen=True)
class Rule:
    when: str  # "weather:rain", "daypart:morning", "weekend", "payday"
    boost: frozenset[str]
    why: str
    strength: float
    avoid: frozenset[str] = frozenset()


def _toks(text: str) -> frozenset[str]:
    return frozenset(st for st, _ in words(text))


RULES: tuple[Rule, ...] = (
    Rule("weather:rain", _toks("coffee pastry biscuit dessert sandwich snack soup tea"), "Rainy day: warm treats", 0.9, _toks("iced soft")),
    Rule("weather:hot", _toks("iced drink fruit mango banana apple yoghurt"), "Hot day: something cool", 0.9, _toks("coffee soup")),
    Rule("weather:cold", _toks("coffee tea pastry biscuit soup bread"), "Chilly: something warm", 0.8, _toks("iced")),
    Rule("daypart:morning", _toks("bread egg milk dairy pastry coffee yoghurt"), "Good for breakfast", 0.8),
    Rule("daypart:midday", _toks("sandwich food rice pantry vegetable tomato spinach"), "Lunch time", 0.7),
    Rule("daypart:evening", _toks("snack pastry biscuit dessert coffee tea vegetable rice bread"), "Evening snacks and dinner", 0.7),
    Rule("daypart:night", _toks("milk bread egg dairy yoghurt"), "Restock for tomorrow", 0.5),
    Rule("weekend", _toks("dessert pastry sandwich food"), "Weekend treat", 0.5),
    Rule("payday", _toks("pantry rice oil dairy egg milk"), "Payday stock-up", 0.6),
)

# What goes with what: a shopper who wants the key probably wants these too.
_COMPLEMENT_TEXT = {
    "bread": "egg milk butter jam cheese tea yoghurt",
    "egg": "bread milk",
    "milk": "bread biscuit cereal tea egg",
    "tea": "biscuit pastry snack dessert",
    "coffee": "pastry dessert biscuit",
    "rice": "oil vegetable tomato spinach",
    "oil": "rice vegetable",
    "dessert": "coffee tea",
    "pastry": "coffee tea",
    "fruit": "yoghurt dairy",
    "vegetable": "rice oil",
    "snack": "drink tea",
    "biscuit": "tea milk coffee",
}
COMPLEMENTS: dict[str, frozenset[str]] = {stem(k): _toks(v) for k, v in _COMPLEMENT_TEXT.items()}


def _rule_matches(rule: Rule, hour: int, part: str, weekday: int, day: int, ctx: Context) -> bool:
    kind, _, arg = rule.when.partition(":")
    if kind == "weather":
        return ctx.weather == arg
    if kind == "daypart":
        return part == arg
    if kind == "weekend":
        return weekday >= 5 or weekday == 4 and hour >= 16  # Friday evening counts
    if kind == "payday":
        return day >= 25 or day <= 3
    return False


# ── the shopper's profile ────────────────────────────────────────────────
@dataclass
class PredictProfile:
    install_id: uuid.UUID | None = None
    personalised: bool = False
    list_toks: dict[str, str] = field(default_factory=dict)  # stem → the list entry it came from
    prior_cats: set[str] = field(default_factory=set)
    cat: dict[str, float] = field(default_factory=dict)  # learned, decayed
    shop: dict[str, float] = field(default_factory=dict)
    tok: dict[str, float] = field(default_factory=dict)
    disp: dict[str, str] = field(default_factory=dict)
    evidence: float = 0.0  # sum of |decayed weights|: how much we actually know
    rev: int = 0  # changes whenever the learned part changes (cache key)

    def triggers(self) -> dict[str, str]:
        """Tokens this shopper wants, for basket completion: their list plus what they have shown interest in."""
        out = dict(self.list_toks)
        for t, w in self.tok.items():
            if w >= 1.0:
                out.setdefault(t, self.disp.get(t, t))
        return out

    @classmethod
    def basic(cls, list_items: list[str], categories: list[str]) -> PredictProfile:
        p = cls(personalised=True, prior_cats=set(categories))
        for entry in list_items:
            for st, _ in words(entry):
                p.list_toks[st] = entry.strip()
        return p


def _apply(p: PredictProfile, f: Features, weight: float, when: datetime, now: datetime) -> None:
    age_days = max((now - when).total_seconds(), 0) / 86400
    d = weight * 0.5 ** (age_days / HALF_LIFE_DAYS)
    p.cat[f.cat] = p.cat.get(f.cat, 0.0) + d
    if f.shop_id:
        p.shop[f.shop_id] = p.shop.get(f.shop_id, 0.0) + d
    for t in f.toks:
        p.tok[t] = p.tok.get(t, 0.0) + d
        if t in f.display:
            p.disp.setdefault(t, f.display[t])
    p.evidence += abs(d)
    p.rev += 1


async def build_profiles(s: AsyncSession, install_ids: list[uuid.UUID], now: datetime | None = None) -> dict[uuid.UUID, PredictProfile]:
    """Profiles for many shoppers at once (the feed asks for one, notification matching for hundreds)."""
    now = now or clock.now()
    ids = list(dict.fromkeys(install_ids))
    out = {i: PredictProfile(install_id=i) for i in ids}
    if not ids:
        return out
    since = now - HISTORY

    consents: dict[uuid.UUID, set[str]] = {}
    for iid, purpose in (await s.execute(select(Consent.install_id, Consent.purpose).where(Consent.install_id.in_(ids), Consent.withdrawn_at.is_(None)))).all():
        consents.setdefault(iid, set()).add(purpose)
    prefs = {r.install_id: dict(r.data or {}) for r in (await s.execute(select(ShopperPreference).where(ShopperPreference.install_id.in_(ids)))).scalars()}
    lists = {
        r.install_id: r.items or []
        for r in (await s.execute(select(ShoppingList).where(ShoppingList.install_id.in_(ids)))).scalars()
        if not r.expires_at or r.expires_at > now
    }
    resets: dict[uuid.UUID, datetime] = {}
    for iid in ids:
        pp, granted, pr = out[iid], consents.get(iid, set()), prefs.get(iid, {})
        pp.personalised = "personalisation" in granted
        if not pp.personalised:
            continue
        pp.prior_cats = set(pr.get("categories") or [])
        if "list" in granted:
            for entry in lists.get(iid, []):
                for st, _ in words(str(entry)):
                    pp.list_toks[st] = str(entry).strip()
        if pr.get("learning_reset_at"):
            try:
                resets[iid] = datetime.fromisoformat(pr["learning_reset_at"])
            except ValueError:
                pass

    live = [i for i in ids if out[i].personalised]
    if not live:
        return out

    def fresh(iid: uuid.UUID, when: datetime) -> bool:
        return when >= since and (iid not in resets or when > resets[iid])

    # What they did in the app (open, like, dislike, dismiss). Each event carries a snapshot of its offer.
    events = (
        await s.execute(select(ShopperEvent).where(ShopperEvent.install_id.in_(live), ShopperEvent.created_at >= since, ShopperEvent.type.in_(tuple(ACTION_WEIGHTS))))
    ).scalars().all()
    for e in events:
        snap = (e.data or {}).get("f")
        if snap and fresh(e.install_id, e.created_at):
            _apply(out[e.install_id], Features.from_json(snap), ACTION_WEIGHTS[e.type], e.created_at, now)

    # What they claimed and redeemed (these are rows we hold anyway).
    claim_rows = (
        await s.execute(
            select(Claim.install_id, Claim.created_at, Offer.items, Offer.shop_id, Shop.category)
            .join(Offer, Offer.id == Claim.offer_id).join(Shop, Shop.id == Offer.shop_id)
            .where(Claim.install_id.in_(live), Claim.created_at >= since)
        )
    ).all()
    red_rows = (
        await s.execute(
            select(Redemption.install_id, Redemption.redeemed_at, Offer.items, Offer.shop_id, Shop.category)
            .join(Offer, Offer.id == Redemption.offer_id).join(Shop, Shop.id == Redemption.shop_id)
            .where(Redemption.install_id.in_(live), Redemption.redeemed_at >= since)
        )
    ).all()
    from .shopper import category_label  # late import: shopper.py imports this module

    for kind, rows in (("claim", claim_rows), ("redemption", red_rows)):
        for iid, when, items, shop_id, shop_cat in rows:
            if fresh(iid, when):
                _apply(out[iid], features_of(items or [], category_label(shop_cat), str(shop_id)), ACTION_WEIGHTS[kind], when, now)
    return out


# ── what people near here do at this time of day ─────────────────────────
@dataclass
class MarketIndex:
    cat_part_shoppers: dict[tuple[str, str], set[uuid.UUID]] = field(default_factory=dict)
    cat_part_claims: dict[tuple[str, str], int] = field(default_factory=dict)
    part_claims: dict[str, int] = field(default_factory=dict)

    def share(self, cat: str, part: str) -> float | None:
        """Share of this daypart's claims that were in `cat`, or None when too few people are behind it."""
        total = self.part_claims.get(part, 0)
        who = self.cat_part_shoppers.get((cat, part), set())
        if total < MARKET_MIN_CLAIMS or len(who) < MARKET_MIN_SHOPPERS:
            return None
        return self.cat_part_claims.get((cat, part), 0) / total


_market: tuple[float, MarketIndex] | None = None


def clear_caches() -> None:
    global _market
    _market = None


async def get_market(s: AsyncSession, now: datetime | None = None) -> MarketIndex:
    global _market
    if _market and _market[0] > time.monotonic():
        return _market[1]
    now = now or clock.now()
    idx = MarketIndex()
    from .shopper import category_label

    rows = (
        await s.execute(
            select(Claim.install_id, Claim.created_at, Shop.category, Shop.timezone)
            .join(Offer, Offer.id == Claim.offer_id).join(Shop, Shop.id == Offer.shop_id)
            .where(Claim.created_at >= now - MARKET_WINDOW, Claim.install_id.is_not(None))
        )
    ).all()
    for iid, when, shop_cat, tz in rows:
        try:
            hour = when.astimezone(ZoneInfo(tz)).hour
        except Exception:  # noqa: BLE001
            hour = when.hour
        part, cat = daypart_of(hour), category_label(shop_cat)
        idx.cat_part_shoppers.setdefault((cat, part), set()).add(iid)
        idx.cat_part_claims[(cat, part)] = idx.cat_part_claims.get((cat, part), 0) + 1
        idx.part_claims[part] = idx.part_claims.get(part, 0) + 1
    _market = (time.monotonic() + MARKET_TTL_S, idx)
    return idx


# ── the prediction ───────────────────────────────────────────────────────
@dataclass
class Prediction:
    score: float
    why: str  # the strongest reason, in plain words
    reasons: list[str]  # up to 3 reasons, strongest first
    parts: dict[str, float]  # probability each signal gave (for tests and the AI hint)


def _squash(z: float) -> float:
    return math.tanh(z / 3.0)


def predict(
    p: PredictProfile, f: Features, *, shop_name: str, distance_m: int | None, max_distance_m: int, minutes_left: float,
    discount_pct: int, claimed: int, cap: int, expires_in_h: float | None, now: datetime, tz: str, ctx: Context,
    market: MarketIndex | None,
) -> Prediction:
    hour, part, weekday, day = ctx.local(now, tz)
    parts: dict[str, float] = {}
    why: dict[str, str] = {}

    # stated: an item on their list / a category they picked
    hits = [t for t in f.toks if t in p.list_toks]
    if hits:
        parts["list"] = CAP["list"]
        why["list"] = f"On your list: {p.list_toks[hits[0]].lower()}"
    if f.cat in p.prior_cats:
        parts["prior"] = CAP["prior"]
        why["prior"] = f"You like {f.cat}"

    # context: time of day, weather, weekend, payday
    boost, avoid, best = 0.0, 0.0, ("", 0.0)
    for r in RULES:
        if not _rule_matches(r, hour, part, weekday, day, ctx):
            continue
        if f.toks & r.avoid:  # "iced tea" on a rainy day: not a warm treat, even though it contains "tea"
            avoid = max(avoid, r.strength)
            continue
        if f.toks & r.boost:
            boost += r.strength
            if r.strength > best[1]:
                best = (r.why, r.strength)
    if boost > 0:
        parts["context"] = CAP["context"] * min(1.0, boost)
        why["context"] = best[0]

    # basket: goes with what they want
    if not hits:
        for trig, shown in p.triggers().items():
            if f.toks & COMPLEMENTS.get(trig, frozenset()):
                parts["basket"] = CAP["basket"]
                why["basket"] = f"Goes with your {shown.lower()}"
                break

    # market: popular at this time of day near here (only with enough people behind it)
    if market is not None:
        share = market.share(f.cat, part)
        if share:
            parts["market"] = CAP["market"] * min(1.0, share / 0.4)
            why["market"] = f"Popular {DAYPART_PHRASE[part]}"

    # learned: what they open / claim / redeem / dislike, trusted in proportion to the evidence
    z_pos = sum(sorted((v for t, v in ((t, p.tok.get(t, 0.0)) for t in f.toks) if v > 0), reverse=True)[:3]) * 0.5
    z_neg = sum(v for t in f.toks if (v := p.tok.get(t, 0.0)) < 0) * 0.5
    z = z_pos + z_neg + 0.7 * p.cat.get(f.cat, 0.0) + 0.8 * p.shop.get(f.shop_id, 0.0)
    confidence = p.evidence / (p.evidence + 2.0)
    penalty = 0.0
    if z > 0:
        parts["learned"] = CAP["learned"] * confidence * _squash(z)
        top = max(f.toks, key=lambda t: p.tok.get(t, 0.0), default=None)
        if p.shop.get(f.shop_id, 0.0) >= max(p.tok.get(top, 0.0) if top else 0.0, 4.0):  # repeat business, not one tap
            why["learned"] = f"You keep coming back to {shop_name}"
        elif top and p.tok.get(top, 0.0) > 0:
            why["learned"] = f"You've shown interest in {p.disp.get(top, top)}"
        else:
            why["learned"] = f"You've shown interest in {f.cat}"
    elif z < 0:
        penalty = 0.6 * confidence * _squash(-z)

    # shop side: stock that must go today
    if expires_in_h is not None and 0 < expires_in_h <= 24:
        parts["waste"] = CAP["waste"]
        why["waste"] = "Fresh stock that must go today"

    # base: close, ending soon, a good discount, filling up
    prox = 0.5 if distance_m is None else 1.0 - min(distance_m / max(max_distance_m, 1), 1.0)
    urgency = 1.0 - min(max(minutes_left, 0) / 180.0, 1.0)
    fill = min(claimed / max(cap, 1), 1.0)
    parts["base"] = 0.12 * prox + 0.08 * urgency + 0.05 * min(discount_pct / 30, 1.0) + 0.04 * fill

    keep = 1.0
    for v in parts.values():
        keep *= 1.0 - v
    score = (1.0 - keep) * (1.0 - penalty) * (1.0 - 0.5 * avoid * 0.6)
    score = round(min(max(score, 0.0), 1.0), 4)

    ranked = [k for k, v in sorted(parts.items(), key=lambda kv: -kv[1]) if k in why and v >= 0.05]
    reasons = [why[k] for k in ranked[:3]]
    if not reasons:
        reasons = ["Ending soon near you" if minutes_left < 60 else "Near you"]
    return Prediction(score, reasons[0], reasons, {k: round(v, 4) for k, v in parts.items()})
