"""The guardrail validator (Plan 2 Phase 2). Pure functions, no I/O.

Strict with the AI: it fixes what it can and records a "save".
Stricter with the human: it NEVER changes their numbers; it refuses with the exact limit.
"""
from __future__ import annotations

from datetime import timedelta

from .types import (
    BANNED_CATEGORIES,
    EU_LOOKBACK_DAYS,
    MIN_USEFUL_PCT,
    AgentOutcome,
    Context,
    Draft,
    HumanOutcome,
    ItemFacts,
    Save,
    Validated,
    ValidatedItem,
    Violation,
)
from .windows import fit_window, within_allowed

HUMAN_PAST_GRACE = timedelta(seconds=60)


# ── price helpers ────────────────────────────────────────────────────────
def price_after(was_minor: int, pct: int) -> int:
    """Price after a % discount, rounded half up, in integer minor units."""
    return (was_minor * (100 - pct) + 50) // 100


def max_pct_for_min_price(was_minor: int, min_price_minor: int) -> int:
    """Largest whole % that keeps the new price at or above `min_price_minor`."""
    if min_price_minor <= 0:
        return 100
    for p in range(100, -1, -1):
        if price_after(was_minor, p) >= min_price_minor:
            return p
    return 0


def reference_price(item: ItemFacts, ctx: Context) -> int | None:
    """The honest 'was' price, or None if it cannot be shown truthfully.

    EU shops must use the lowest price of the last 30 days (Omnibus Directive).
    """
    regular = item.regular_price_minor
    if not ctx.is_eu:
        return regular
    window_start = ctx.now - timedelta(days=EU_LOOKBACK_DAYS)
    hist = sorted(item.history, key=lambda p: p.changed_at)
    if hist:
        prices = [p.price_minor for p in hist if p.changed_at >= window_start]
        earlier = [p for p in hist if p.changed_at < window_start]
        if earlier:
            prices.append(earlier[-1].price_minor)
        ref = min(prices + [regular]) if prices else regular
        return ref if ref > 0 else None
    since = item.regular_price_since
    if since is None or since < window_start:
        return regular
    return None  # price changed recently and we have no history to prove the lowest price


def effective_min_price(item: ItemFacts, ctx: Context) -> int:
    return max(ctx.limits.min_price_minor, item.min_price_minor or 0)


def per_redemption_discount(refs: list[int], pct: int) -> int:
    avg = sum(refs) // max(len(refs), 1)
    return max((avg * pct + 50) // 100, 1)


def remaining_budget(ctx: Context) -> int | None:
    lim = ctx.limits
    rem: list[int] = []
    if lim.daily_budget_minor is not None:
        rem.append(lim.daily_budget_minor - ctx.committed_today_minor)
    if lim.weekly_budget_minor is not None:
        rem.append(lim.weekly_budget_minor - ctx.committed_week_minor)
    return min(rem) if rem else None


def _is_banned(item: ItemFacts, ctx: Context) -> bool:
    cat = item.category.strip().lower()
    return cat in BANNED_CATEGORIES or cat in {c.lower() for c in ctx.limits.blocked_categories}


# ── AI path ──────────────────────────────────────────────────────────────
def validate_for_agent(draft: Draft, ctx: Context) -> AgentOutcome:
    lim = ctx.limits
    saves: list[Save] = []
    kept: list[ItemFacts] = []

    seen: set[str] = set()
    for iid in draft.item_ids:
        if iid in seen:
            continue
        seen.add(iid)
        it = ctx.items.get(iid)
        if it is None:
            saves.append(Save("unknown_item", "An item that doesn't exist was removed.", item_id=iid))
        elif iid in lim.never_discount_item_ids:
            saves.append(Save("never_discount", f"{it.name} is on your never-discount list, so it was removed.", item_id=iid))
        elif _is_banned(it, ctx):
            saves.append(Save("banned_category", f"{it.name} is in a category that can't be discounted, so it was removed.", item_id=iid))
        else:
            kept.append(it)
    if not kept:
        saves.append(Save("no_items_left", "No items were allowed in this offer, so it was stopped."))
        return AgentOutcome(False, None, saves, "no_items_left")

    refs: dict[str, int] = {}
    for it in kept[:]:
        ref = reference_price(it, ctx)
        if ref is None:
            kept.remove(it)
            saves.append(
                Save("eu_reference_price", f"{it.name}: an honest 'was' price can't be shown, so it was removed.", item_id=it.id)
            )
            continue
        refs[it.id] = ref
        if ref != it.regular_price_minor:
            saves.append(
                Save(
                    "eu_reference_price",
                    f"{it.name}: the price changed in the last 30 days, so the lowest recent price is used as the 'was' price.",
                    before=it.regular_price_minor, after=ref, item_id=it.id,
                )
            )
    if not kept:
        saves.append(Save("no_items_left", "No items could be shown with an honest 'was' price, so it was stopped."))
        return AgentOutcome(False, None, saves, "no_items_left")

    pct = draft.pct
    if pct > lim.max_discount_pct:
        saves.append(Save("max_discount_pct", f"Guardrail saved you: {pct}% → {lim.max_discount_pct}%", before=pct, after=lim.max_discount_pct))
        pct = lim.max_discount_pct
    if pct < 1:
        saves.append(Save("invalid_pct", "The discount was zero or negative, so it was stopped."))
        return AgentOutcome(False, None, saves, "invalid_pct")

    pmax: dict[str, int] = {it.id: max_pct_for_min_price(refs[it.id], effective_min_price(it, ctx)) for it in kept}
    for it in kept[:]:
        if pmax[it.id] < min(pct, MIN_USEFUL_PCT):
            kept.remove(it)
            saves.append(
                Save("min_price", f"{it.name} can't go below its minimum price, so it was removed.", before=pct, after=pmax[it.id], item_id=it.id)
            )
    if not kept:
        saves.append(Save("no_items_left", "Every item would drop below its minimum price, so it was stopped."))
        return AgentOutcome(False, None, saves, "no_items_left")
    lowest = min(pmax[it.id] for it in kept)
    if pct > lowest:
        saves.append(Save("min_price", f"Guardrail saved you: {pct}% → {lowest}% (minimum price)", before=pct, after=lowest))
        pct = lowest

    if ctx.offers_today >= lim.max_offers_per_day:
        saves.append(Save("max_offers_per_day", f"You already reached {lim.max_offers_per_day} offers today.", before=ctx.offers_today, after=lim.max_offers_per_day))
        return AgentOutcome(False, None, saves, "max_offers_per_day")

    start, end = fit_window(draft.window_start, draft.window_end, ctx.now, lim)
    if (start, end) != (draft.window_start, draft.window_end):
        saves.append(Save("allowed_hours", "The time was moved to your next allowed offer hours.", before=[draft.window_start.isoformat(), draft.window_end.isoformat()], after=[start.isoformat(), end.isoformat()]))

    cap = max(draft.cap, 1)
    if cap > lim.max_redemptions_per_offer:
        saves.append(Save("max_redemptions_per_offer", f"The limit of customers was lowered {cap} → {lim.max_redemptions_per_offer}.", before=cap, after=lim.max_redemptions_per_offer))
        cap = lim.max_redemptions_per_offer

    rem = remaining_budget(ctx)
    if rem is not None:
        per = per_redemption_discount([refs[i.id] for i in kept], pct)
        if rem <= 0:
            saves.append(Save("budget", "Your discount budget is used up, so no offer was made.", before=0, after=0))
            return AgentOutcome(False, None, saves, "budget")
        if per * cap > rem:
            new_cap = rem // per
            if new_cap < 1:
                saves.append(Save("budget", "The remaining discount budget is too small for this offer.", before=cap, after=0))
                return AgentOutcome(False, None, saves, "budget")
            saves.append(Save("budget", f"Guardrail saved you: customers limit {cap} → {new_cap} to fit your budget.", before=cap, after=new_cap))
            cap = new_cap

    vitems = tuple(
        ValidatedItem(it.id, it.name, it.category, refs[it.id], price_after(refs[it.id], pct), it.cost_minor) for it in kept
    )
    return AgentOutcome(True, Validated(vitems, pct, start, end, cap), saves)


# ── Human path ───────────────────────────────────────────────────────────
def validate_for_human(draft: Draft, ctx: Context) -> HumanOutcome:
    """Re-check at approval time. Never changes the human's pct/window/cap: it refuses."""
    lim = ctx.limits
    violations: list[Violation] = []
    saves: list[Save] = []
    kept: list[ItemFacts] = []

    for iid in dict.fromkeys(draft.item_ids):
        it = ctx.items.get(iid)
        if it is None:
            violations.append(Violation("unknown_item", "An item in this offer no longer exists.", item_id=iid))
        elif iid in lim.never_discount_item_ids:
            violations.append(Violation("never_discount", f"{it.name} is on your never-discount list.", item_id=iid))
        elif _is_banned(it, ctx):
            violations.append(Violation("banned_category", f"{it.name} is in a category that can't be discounted.", item_id=iid))
        else:
            kept.append(it)

    refs: dict[str, int] = {}
    for it in kept[:]:
        ref = reference_price(it, ctx)
        if ref is None:
            kept.remove(it)
            saves.append(Save("eu_reference_price", f"{it.name}: an honest 'was' price can't be shown, so it was removed.", item_id=it.id))
            continue
        refs[it.id] = ref
        if ref != it.regular_price_minor:
            saves.append(Save("eu_reference_price", f"{it.name}: the lowest price of the last 30 days is the 'was' price.", before=it.regular_price_minor, after=ref, item_id=it.id))
    if not kept and not violations:
        violations.append(Violation("no_items_left", "No items can be shown with an honest 'was' price."))

    pct = draft.pct
    if pct > lim.max_discount_pct:
        violations.append(Violation("max_discount_pct", f"The most you allow is {lim.max_discount_pct}%.", limit=lim.max_discount_pct, got=pct))
    if pct < 1:
        violations.append(Violation("invalid_pct", "The discount must be at least 1%.", limit=1, got=pct))
    else:
        for it in kept:
            floor = effective_min_price(it, ctx)
            new = price_after(refs[it.id], min(pct, 100))
            if floor > 0 and new < floor:
                allowed = max_pct_for_min_price(refs[it.id], floor)
                violations.append(Violation("min_price", f"{it.name} would cost {new}, below its minimum price {floor}.", limit=allowed, got=pct, item_id=it.id))

    if draft.window_end <= draft.window_start:
        violations.append(Violation("window_invalid", "The end time must be after the start time."))
    elif draft.window_start < ctx.now - HUMAN_PAST_GRACE:
        violations.append(Violation("window_in_past", "That time has already started. Choose a later time."))
    elif not within_allowed(draft.window_start, draft.window_end, lim):
        violations.append(
            Violation("allowed_hours", "That time is outside your allowed offer hours.", limit=[lim.allowed_start_min, lim.allowed_end_min])
        )

    if ctx.offers_today >= lim.max_offers_per_day:
        violations.append(Violation("max_offers_per_day", f"You already reached {lim.max_offers_per_day} offers today.", limit=lim.max_offers_per_day, got=ctx.offers_today))

    if draft.cap < 1:
        violations.append(Violation("invalid_cap", "At least 1 customer must be allowed.", limit=1, got=draft.cap))
    elif draft.cap > lim.max_redemptions_per_offer:
        violations.append(Violation("max_redemptions_per_offer", f"You allow at most {lim.max_redemptions_per_offer} customers per offer.", limit=lim.max_redemptions_per_offer, got=draft.cap))

    rem = remaining_budget(ctx)
    if rem is not None and kept and pct >= 1 and draft.cap >= 1:
        per = per_redemption_discount([refs[i.id] for i in kept], min(pct, 100))
        est = per * draft.cap
        if est > rem:
            violations.append(Violation("budget", f"This could cost up to {est}, but only {max(rem, 0)} is left in your budget.", limit=max(rem, 0), got=est))

    if violations:
        return HumanOutcome(False, None, violations, saves)
    vitems = tuple(
        ValidatedItem(it.id, it.name, it.category, refs[it.id], price_after(refs[it.id], pct), it.cost_minor) for it in kept
    )
    return HumanOutcome(True, Validated(vitems, pct, draft.window_start, draft.window_end, draft.cap), [], saves)
