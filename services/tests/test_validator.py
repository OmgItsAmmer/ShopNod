"""Every rule in Plan 2 Phase 2's table, for both the AI path (fix + record a save) and the human path (refuse)."""
from datetime import UTC, datetime, timedelta

import pytest

from shopnod_core.guardrails import (
    Context,
    Draft,
    ItemFacts,
    Limits,
    PricePoint,
    RuleItem,
    fit_window,
    local_day_bounds,
    local_hour,
    local_weekday_key,
    max_pct_for_min_price,
    parse_hhmm,
    price_after,
    reference_price,
    round_up,
    rules_proposal,
    validate_for_agent,
    validate_for_human,
    within_allowed,
)
from shopnod_core.guardrails.validator import per_redemption_discount, remaining_budget

UTC = UTC
# Tuesday 2026-03-10 11:00 in Karachi (UTC+5) = 06:00 UTC
NOW = datetime(2026, 3, 10, 6, 0, tzinfo=UTC)
TZ = "Asia/Karachi"


def item(iid="a", name="Croissant", cat="pastry", price=10000, **kw):
    return ItemFacts(id=iid, name=name, category=cat, regular_price_minor=price, **kw)


def limits(**kw):
    base = dict(max_discount_pct=20, min_price_minor=0, max_offers_per_day=3, max_redemptions_per_offer=50,
                allowed_start_min=8 * 60, allowed_end_min=21 * 60, tz=TZ)
    base.update(kw)
    return Limits(**base)


def ctx(items=None, lim=None, **kw):
    items = items or [item()]
    return Context(now=NOW, limits=lim or limits(), items={i.id: i for i in items}, **kw)


def draft(ids=("a",), pct=15, start=None, end=None, cap=30):
    s = start or NOW + timedelta(minutes=30)
    return Draft(tuple(ids), pct, s, end or s + timedelta(minutes=90), cap)


# ── helpers ──────────────────────────────────────────────────────────────
def test_price_after_rounds_half_up():
    assert price_after(10000, 15) == 8500
    assert price_after(199, 10) == 179  # 179.1 -> 179
    assert price_after(105, 50) == 53  # 52.5 -> 53


def test_max_pct_for_min_price():
    assert max_pct_for_min_price(10000, 0) == 100
    assert max_pct_for_min_price(10000, 8000) == 20
    assert max_pct_for_min_price(10000, 10000) == 0
    assert max_pct_for_min_price(10000, 20000) == 0


def test_parse_hhmm_and_time_helpers():
    assert parse_hhmm("08:30") == 510
    assert local_hour(NOW, TZ) == 11
    assert local_weekday_key(NOW, TZ) == "tue"
    start, end = local_day_bounds(NOW, TZ)
    assert start == datetime(2026, 3, 9, 19, 0, tzinfo=UTC) and end - start == timedelta(days=1)
    assert round_up(datetime(2026, 1, 1, 10, 2, 30, tzinfo=UTC), 5) == datetime(2026, 1, 1, 10, 5, tzinfo=UTC)
    assert round_up(datetime(2026, 1, 1, 10, 5, tzinfo=UTC), 5) == datetime(2026, 1, 1, 10, 5, tzinfo=UTC)


def test_reference_price_non_eu_is_regular():
    assert reference_price(item(), ctx()) == 10000


# ── AI path ──────────────────────────────────────────────────────────────
def test_agent_ok_untouched():
    out = validate_for_agent(draft(), ctx())
    assert out.ok and out.saves == []
    v = out.proposal
    assert v.pct == 15 and v.cap == 30
    assert v.items[0].was_minor == 10000 and v.items[0].new_price_minor == 8500


def test_agent_pct_above_max_is_lowered_with_a_save():
    out = validate_for_agent(draft(pct=25), ctx())
    assert out.ok and out.proposal.pct == 20
    s = [x for x in out.saves if x.rule == "max_discount_pct"][0]
    assert (s.before, s.after) == (25, 20) and "25% → 20%" in s.message


def test_agent_min_price_lowers_pct():
    out = validate_for_agent(draft(pct=20), ctx(lim=limits(min_price_minor=8500)))
    assert out.ok and out.proposal.pct == 15
    assert any(s.rule == "min_price" and s.after == 15 for s in out.saves)


def test_agent_item_per_item_min_price_wins_over_global():
    it = item(min_price_minor=9000)
    out = validate_for_agent(draft(pct=20), ctx([it], limits(min_price_minor=100)))
    assert out.proposal.pct == 10  # 10000 * 0.9 = 9000


def test_agent_min_price_drops_item_when_limit_is_tiny():
    cheap = item("b", "Bread", "bread", 10000, min_price_minor=9800)  # at most 2% -> not useful
    out = validate_for_agent(draft(("a", "b"), pct=15), ctx([item(), cheap]))
    assert out.ok and [i.item_id for i in out.proposal.items] == ["a"] and out.proposal.pct == 15
    assert any(s.rule == "min_price" and s.item_id == "b" for s in out.saves)


def test_agent_all_items_below_min_price_rejects():
    out = validate_for_agent(draft(pct=15), ctx(lim=limits(min_price_minor=10000)))
    assert not out.ok and out.rejected_reason == "no_items_left"


def test_agent_never_discount_item_dropped_and_none_left_rejects():
    out = validate_for_agent(draft(), ctx(lim=limits(never_discount_item_ids=frozenset({"a"}))))
    assert not out.ok and out.rejected_reason == "no_items_left"
    assert {s.rule for s in out.saves} == {"never_discount", "no_items_left"}


def test_agent_never_discount_drops_only_that_item():
    out = validate_for_agent(draft(("a", "b")), ctx([item(), item("b", "Bread", "bread")], limits(never_discount_item_ids=frozenset({"a"}))))
    assert out.ok and [i.item_id for i in out.proposal.items] == ["b"]


@pytest.mark.parametrize("cat", ["alcohol", "tobacco", "medicine", "prescription_medicine", "infant_formula", "gambling", "weapons", "adult", "vapes", "ALCOHOL"])
def test_agent_banned_categories_are_dropped(cat):
    out = validate_for_agent(draft(), ctx([item(cat=cat)]))
    assert not out.ok and any(s.rule == "banned_category" for s in out.saves)


def test_agent_shop_blocked_category_dropped():
    out = validate_for_agent(draft(), ctx(lim=limits(blocked_categories=frozenset({"pastry"}))))
    assert not out.ok


def test_agent_unknown_and_duplicate_items():
    out = validate_for_agent(draft(("a", "a", "zzz")), ctx())
    assert out.ok and [i.item_id for i in out.proposal.items] == ["a"]
    assert any(s.rule == "unknown_item" for s in out.saves)


def test_agent_zero_pct_rejected():
    out = validate_for_agent(draft(pct=0), ctx())
    assert not out.ok and out.rejected_reason == "invalid_pct"


def test_agent_window_in_past_moves_forward():
    out = validate_for_agent(draft(start=NOW - timedelta(hours=2), end=NOW - timedelta(minutes=30)), ctx())
    assert out.ok and out.proposal.window_start >= NOW
    assert any(s.rule == "allowed_hours" for s in out.saves)


def test_agent_window_outside_allowed_hours_moves_to_next_allowed_window():
    # 20:50 local start: under 15 minutes left today -> next morning at opening
    start = datetime(2026, 3, 10, 15, 50, tzinfo=UTC)  # 20:50 Karachi
    out = validate_for_agent(draft(start=start, end=start + timedelta(minutes=90)), ctx())
    assert out.ok
    ls = out.proposal.window_start.astimezone(__import__("zoneinfo").ZoneInfo(TZ))
    assert ls.day == 11 and ls.hour == 8  # next morning at opening
    assert out.proposal.window_end - out.proposal.window_start == timedelta(minutes=90)


def test_agent_window_clamped_to_closing_time():
    start = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)  # 19:30 local
    out = validate_for_agent(draft(start=start, end=start + timedelta(hours=3)), ctx())
    end_local = out.proposal.window_end.astimezone(__import__("zoneinfo").ZoneInfo(TZ))
    assert (end_local.hour, end_local.minute) == (21, 0)


def test_agent_too_many_offers_today_rejects():
    out = validate_for_agent(draft(), ctx(offers_today=3))
    assert not out.ok and out.rejected_reason == "max_offers_per_day"


def test_agent_cap_lowered_to_max_redemptions():
    out = validate_for_agent(draft(cap=500), ctx())
    assert out.proposal.cap == 50 and any(s.rule == "max_redemptions_per_offer" for s in out.saves)


def test_agent_cap_floor_is_one():
    assert validate_for_agent(draft(cap=0), ctx()).proposal.cap == 1


def test_agent_budget_lowers_cap_to_fit():
    # 15% of 10000 = 1500 per redemption; 10000 left in the budget -> cap 6
    out = validate_for_agent(draft(cap=30), ctx(lim=limits(daily_budget_minor=10000)))
    assert out.ok and out.proposal.cap == 6
    assert any(s.rule == "budget" and (s.before, s.after) == (30, 6) for s in out.saves)


def test_agent_budget_used_up_rejects():
    out = validate_for_agent(draft(), ctx(lim=limits(daily_budget_minor=5000), committed_today_minor=5000))
    assert not out.ok and out.rejected_reason == "budget"


def test_agent_budget_too_small_for_one_redemption_rejects():
    out = validate_for_agent(draft(), ctx(lim=limits(daily_budget_minor=1000)))  # one redemption costs 1500
    assert not out.ok and out.rejected_reason == "budget"


def test_agent_weekly_budget_applies_too():
    out = validate_for_agent(draft(cap=30), ctx(lim=limits(daily_budget_minor=100000, weekly_budget_minor=20000), committed_week_minor=11000))
    assert out.proposal.cap == 6  # 9000 left / 1500


def test_remaining_budget_none_when_unlimited():
    assert remaining_budget(ctx()) is None
    assert per_redemption_discount([10000, 20000], 10) == 1500


# ── EU "was price" rule ──────────────────────────────────────────────────
def eu_item(history, since):
    return item(price=10000, regular_price_since=since, history=tuple(PricePoint(t, p) for t, p in history))


def test_eu_recent_price_rise_uses_lowest_30_day_price_as_was():
    it = eu_item([(NOW - timedelta(days=60), 8000), (NOW - timedelta(days=5), 10000)], NOW - timedelta(days=5))
    assert reference_price(it, ctx([it], is_eu=True)) == 8000
    out = validate_for_agent(draft(pct=10), ctx([it], is_eu=True))
    assert out.ok and out.proposal.items[0].was_minor == 8000 and out.proposal.items[0].new_price_minor == 7200
    assert any(s.rule == "eu_reference_price" and s.after == 8000 for s in out.saves)


def test_eu_price_cut_recently_uses_the_lowest():
    it = eu_item([(NOW - timedelta(days=60), 12000), (NOW - timedelta(days=3), 10000)], NOW - timedelta(days=3))
    assert reference_price(it, ctx([it], is_eu=True)) == 10000


def test_eu_unchanged_old_price_is_regular():
    it = eu_item([(NOW - timedelta(days=200), 10000)], NOW - timedelta(days=200))
    assert reference_price(it, ctx([it], is_eu=True)) == 10000


def test_eu_recent_change_without_history_drops_the_item():
    it = eu_item([], NOW - timedelta(days=2))
    out = validate_for_agent(draft(), ctx([it], is_eu=True))
    assert not out.ok and any(s.rule == "eu_reference_price" for s in out.saves)


def test_eu_no_history_but_old_price_is_fine():
    it = eu_item([], NOW - timedelta(days=100))
    assert validate_for_agent(draft(), ctx([it], is_eu=True)).ok


def test_non_eu_shop_ignores_price_history():
    it = eu_item([(NOW - timedelta(days=60), 8000), (NOW - timedelta(days=5), 10000)], NOW - timedelta(days=5))
    assert reference_price(it, ctx([it], is_eu=False)) == 10000


# ── human path: refuse, never change ─────────────────────────────────────
def rule_set(out):
    return {v.rule for v in out.violations}


def test_human_ok_keeps_exact_numbers():
    out = validate_for_human(draft(pct=10, cap=12), ctx())
    assert out.ok and out.proposal.pct == 10 and out.proposal.cap == 12


def test_human_pct_above_max_is_refused_with_limit():
    out = validate_for_human(draft(pct=40), ctx())
    assert not out.ok and out.proposal is None
    v = out.violations[0]
    assert v.rule == "max_discount_pct" and v.limit == 20 and v.got == 40


def test_human_zero_pct_refused():
    assert "invalid_pct" in rule_set(validate_for_human(draft(pct=0), ctx()))


def test_human_min_price_refused_with_allowed_pct():
    out = validate_for_human(draft(pct=20), ctx(lim=limits(min_price_minor=8500)))
    v = [x for x in out.violations if x.rule == "min_price"][0]
    assert v.limit == 15 and v.got == 20


def test_human_never_discount_and_banned_refused():
    assert "never_discount" in rule_set(validate_for_human(draft(), ctx(lim=limits(never_discount_item_ids=frozenset({"a"})))))
    assert "banned_category" in rule_set(validate_for_human(draft(), ctx([item(cat="tobacco")])))


def test_human_unknown_item_refused():
    assert "unknown_item" in rule_set(validate_for_human(draft(("zzz",)), ctx()))


def test_human_window_rules():
    past = validate_for_human(draft(start=NOW - timedelta(hours=1), end=NOW + timedelta(minutes=30)), ctx())
    assert "window_in_past" in rule_set(past)
    inverted = validate_for_human(draft(start=NOW + timedelta(hours=2), end=NOW + timedelta(hours=1)), ctx())
    assert "window_invalid" in rule_set(inverted)
    late = datetime(2026, 3, 10, 16, 30, tzinfo=UTC)  # 21:30 local
    assert "allowed_hours" in rule_set(validate_for_human(draft(start=late, end=late + timedelta(hours=1)), ctx()))


def test_human_just_started_window_is_forgiven_by_grace():
    assert validate_for_human(draft(start=NOW - timedelta(seconds=30), end=NOW + timedelta(hours=1)), ctx()).ok


def test_human_offers_per_day_and_cap_rules():
    assert "max_offers_per_day" in rule_set(validate_for_human(draft(), ctx(offers_today=3)))
    assert "max_redemptions_per_offer" in rule_set(validate_for_human(draft(cap=51), ctx()))
    assert "invalid_cap" in rule_set(validate_for_human(draft(cap=0), ctx()))


def test_human_budget_refused():
    out = validate_for_human(draft(cap=30), ctx(lim=limits(daily_budget_minor=10000)))
    v = [x for x in out.violations if x.rule == "budget"][0]
    assert v.limit == 10000 and v.got == 45000


def test_human_eu_reference_price_applied_and_unverifiable_removed():
    it = eu_item([(NOW - timedelta(days=60), 8000), (NOW - timedelta(days=5), 10000)], NOW - timedelta(days=5))
    out = validate_for_human(draft(pct=10), ctx([it], is_eu=True))
    assert out.ok and out.proposal.items[0].was_minor == 8000
    bad = eu_item([], NOW - timedelta(days=2))
    refused = validate_for_human(draft(), ctx([bad], is_eu=True))
    assert not refused.ok and "no_items_left" in rule_set(refused)


# ── windows ──────────────────────────────────────────────────────────────
def test_within_allowed_variants():
    lim = limits()
    assert within_allowed(NOW + timedelta(hours=1), NOW + timedelta(hours=2), lim)
    assert not within_allowed(NOW - timedelta(hours=5), NOW - timedelta(hours=4), lim)  # 06:00 local
    # spanning midnight is never allowed
    s = datetime(2026, 3, 10, 18, 0, tzinfo=UTC)  # 23:00 local
    assert not within_allowed(s, s + timedelta(hours=3), lim)
    # no restriction configured
    assert within_allowed(s, s + timedelta(hours=3), limits(allowed_start_min=0, allowed_end_min=0))


def test_fit_window_no_restriction_only_clamps_to_now():
    lim = limits(allowed_start_min=0, allowed_end_min=0)
    s, e = fit_window(NOW - timedelta(hours=1), NOW, NOW, lim)
    assert s == NOW and e > s


def test_fit_window_unknown_timezone_falls_back_to_utc():
    lim = limits(tz="Mars/Olympus")
    s, e = fit_window(NOW + timedelta(hours=1), NOW + timedelta(hours=2), NOW, lim)
    assert s >= NOW


# ── rules fallback ───────────────────────────────────────────────────────
def rule_item(iid, name, cat, expires=None, qty=0, price=10000, **kw):
    return RuleItem(item(iid, name, cat, price, **kw), expires, qty)


def test_rules_prefers_expiring_items_and_default_pct():
    items = [rule_item("a", "Croissant", "pastry", NOW + timedelta(hours=8), 12), rule_item("b", "Bread", "bread")]
    res = rules_proposal(items, {}, NOW, limits(), lead_minutes=10)
    assert res.draft.item_ids == ("a",) and res.draft.pct == 10 and res.draft.cap == 30
    assert "12 Croissant" in res.reason and res.category == "pastry"
    assert res.draft.window_end - res.draft.window_start == timedelta(minutes=90)
    assert res.draft.window_start >= NOW + timedelta(minutes=10)


def test_rules_uses_learned_pct_for_category():
    items = [rule_item("a", "Croissant", "pastry", NOW + timedelta(hours=3), 5)]
    assert rules_proposal(items, {"pastry": 12.4}, NOW, limits()).draft.pct == 12


def test_rules_falls_back_to_top_category_when_nothing_expires():
    items = [rule_item("a", "Rye", "bread"), rule_item("b", "Loaf", "bread"), rule_item("c", "Cake", "cake")]
    res = rules_proposal(items, {}, NOW, limits(), quiet_note="Quiet hour.")
    assert set(res.draft.item_ids) == {"a", "b"} and res.reason.startswith("Quiet hour.") and "Bread" in res.reason


def test_rules_skips_banned_never_and_expired():
    items = [
        rule_item("a", "Beer", "alcohol", NOW + timedelta(hours=2), 5),
        rule_item("b", "Milk", "dairy", NOW - timedelta(hours=1), 5),
        rule_item("c", "Cake", "cake", None, 0),
    ]
    res = rules_proposal(items, {}, NOW, limits(never_discount_item_ids=frozenset({"c"})))
    assert res is not None and res.draft.item_ids == ("b",)  # b expired -> not "expiring", falls to top category
    assert rules_proposal([rule_item("a", "Beer", "alcohol")], {}, NOW, limits()) is None
    assert rules_proposal([], {}, NOW, limits()) is None


def test_rules_expiry_phrases():
    soon = rules_proposal([rule_item("a", "Milk", "dairy", NOW + timedelta(hours=3), 4)], {}, NOW, limits())
    tonight = rules_proposal([rule_item("a", "Milk", "dairy", NOW + timedelta(hours=10), 4)], {}, NOW, limits())
    day = rules_proposal([rule_item("a", "Milk", "dairy", NOW + timedelta(hours=20), 4)], {}, NOW, limits())
    assert "few hours" in soon.reason and "tonight" in tonight.reason and "within a day" in day.reason


def test_rules_proposal_passes_the_validator():
    items = [rule_item("a", "Croissant", "pastry", NOW + timedelta(hours=8), 12)]
    res = rules_proposal(items, {"pastry": 40.0}, NOW, limits())
    out = validate_for_agent(res.draft, ctx([i.facts for i in items]))
    assert out.ok and out.proposal.pct == 20  # clamped from the learned 40 to the shop's max


def test_to_dict_shapes_and_expiry_phrase():
    from shopnod_core.guardrails import Save, ValidatedItem, Violation
    from shopnod_core.guardrails.rules import _expiry_phrase

    assert Save("r", "m", 1, 2, "x").to_dict() == {"rule": "r", "message": "m", "before": 1, "after": 2, "item_id": "x"}
    assert Violation("r", "m", 1, 2).to_dict()["limit"] == 1
    d = ValidatedItem("a", "A", "c", 100, 90, 50).to_dict(10)
    assert d["pct"] == 10 and d["new_price_minor"] == 90 and "pct" not in ValidatedItem("a", "A", "c", 100, 90).to_dict()
    assert _expiry_phrase(NOW - timedelta(hours=1), NOW) == "have expired"
