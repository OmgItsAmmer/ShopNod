"""Rules-based proposal (also the fallback whenever the AI is unavailable). Pure function."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .types import BANNED_CATEGORIES, Draft, ItemFacts, Limits
from .windows import round_up

DEFAULT_PCT = 10
DEFAULT_CAP = 30
WINDOW_MINUTES = 90
EXPIRY_HORIZON = timedelta(hours=24)
MAX_ITEMS = 3


@dataclass(frozen=True)
class RuleItem:
    facts: ItemFacts
    expires_at: datetime | None = None
    quantity: int = 0


@dataclass(frozen=True)
class RulesResult:
    draft: Draft
    reason: str
    category: str


def _eligible(it: RuleItem, limits: Limits) -> bool:
    cat = it.facts.category.lower()
    return (
        it.facts.id not in limits.never_discount_item_ids
        and cat not in BANNED_CATEGORIES
        and cat not in {c.lower() for c in limits.blocked_categories}
    )


def _expiry_phrase(expires_at: datetime, now: datetime) -> str:
    hours = (expires_at - now).total_seconds() / 3600
    if hours <= 0:
        return "have expired"
    if hours < 6:
        return "expire in a few hours"
    if hours < 14:
        return "expire tonight"
    return "expire within a day"


def rules_proposal(
    items: list[RuleItem],
    learned_pct: dict[str, float],
    now: datetime,
    limits: Limits,
    lead_minutes: int = 10,
    quiet_note: str | None = None,
) -> RulesResult | None:
    """Pick items, % and a window with simple rules. Returns None if there's nothing to offer."""
    eligible = [i for i in items if _eligible(i, limits)]
    if not eligible:
        return None

    expiring = sorted(
        (i for i in eligible if i.expires_at and i.quantity > 0 and now < i.expires_at <= now + EXPIRY_HORIZON),
        key=lambda i: i.expires_at,  # type: ignore[arg-type,return-value]
    )
    if expiring:
        first = expiring[0]
        chosen = [i for i in expiring if i.facts.category == first.facts.category][:MAX_ITEMS]
        category = first.facts.category
        reason = f"{first.quantity} {first.facts.name} {_expiry_phrase(first.expires_at, now)}."  # type: ignore[arg-type]
    else:
        counts: dict[str, int] = {}
        for i in eligible:
            counts[i.facts.category] = counts.get(i.facts.category, 0) + 1
        category = max(counts, key=lambda c: (counts[c], learned_pct.get(c, 0)))
        chosen = [i for i in eligible if i.facts.category == category][:MAX_ITEMS]
        reason = f"{category.replace('_', ' ').title()} is your top category."
    if quiet_note:
        reason = f"{quiet_note} {reason}"

    pct = int(round(learned_pct[category])) if category in learned_pct else DEFAULT_PCT
    pct = max(1, min(pct, 100))
    start = round_up(now + timedelta(minutes=lead_minutes), 5)
    draft = Draft(
        item_ids=tuple(i.facts.id for i in chosen),
        pct=pct,
        window_start=start,
        window_end=start + timedelta(minutes=WINDOW_MINUTES),
        cap=DEFAULT_CAP,
    )
    return RulesResult(draft, reason, category)
