"""Plain data types for the guardrail validator. No I/O, no database."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Categories banned by law/policy in many markets (compliance.md §2). Always enforced.
BANNED_CATEGORIES: frozenset[str] = frozenset(
    {
        "alcohol", "tobacco", "vapes", "vape", "medicine", "medicines", "prescription", "prescription_medicine",
        "pharmacy", "gambling", "weapons", "adult", "infant_formula",
    }
)
MIN_USEFUL_PCT = 5  # a discount below this is not worth proposing; lower-than-this limits drop the item
MIN_WINDOW_MINUTES = 15
EU_LOOKBACK_DAYS = 30


@dataclass(frozen=True)
class Limits:
    min_price_minor: int = 0
    max_discount_pct: int = 20
    never_discount_item_ids: frozenset[str] = frozenset()
    blocked_categories: frozenset[str] = frozenset()
    daily_budget_minor: int | None = None
    weekly_budget_minor: int | None = None
    max_offers_per_day: int = 3
    max_redemptions_per_offer: int = 50
    allowed_start_min: int = 8 * 60  # minutes after local midnight
    allowed_end_min: int = 21 * 60
    tz: str = "UTC"


@dataclass(frozen=True)
class PricePoint:
    """Regular price in effect from `changed_at` onwards."""

    changed_at: datetime
    price_minor: int


@dataclass(frozen=True)
class ItemFacts:
    id: str
    name: str
    category: str
    regular_price_minor: int
    regular_price_since: datetime | None = None
    min_price_minor: int | None = None
    cost_minor: int | None = None
    history: tuple[PricePoint, ...] = ()


@dataclass(frozen=True)
class Draft:
    item_ids: tuple[str, ...]
    pct: int
    window_start: datetime
    window_end: datetime
    cap: int


@dataclass(frozen=True)
class Context:
    now: datetime
    limits: Limits
    items: dict[str, ItemFacts]
    is_eu: bool = False
    offers_today: int = 0
    committed_today_minor: int = 0
    committed_week_minor: int = 0


@dataclass(frozen=True)
class Save:
    """Something the guardrail changed or blocked to protect the shop."""

    rule: str
    message: str
    before: Any = None
    after: Any = None
    item_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "message": self.message, "before": self.before, "after": self.after, "item_id": self.item_id}


@dataclass(frozen=True)
class Violation:
    """Something the human asked for that is outside the limits (refused, never changed)."""

    rule: str
    message: str
    limit: Any = None
    got: Any = None
    item_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "message": self.message, "limit": self.limit, "got": self.got, "item_id": self.item_id}


@dataclass(frozen=True)
class ValidatedItem:
    item_id: str
    name: str
    category: str
    was_minor: int
    new_price_minor: int
    cost_minor: int | None = None

    def to_dict(self, pct: int | None = None) -> dict[str, Any]:
        d = {
            "item_id": self.item_id, "name": self.name, "category": self.category,
            "was_minor": self.was_minor, "new_price_minor": self.new_price_minor, "cost_minor": self.cost_minor,
        }
        if pct is not None:
            d["pct"] = pct
        return d


@dataclass(frozen=True)
class Validated:
    items: tuple[ValidatedItem, ...]
    pct: int
    window_start: datetime
    window_end: datetime
    cap: int


@dataclass
class AgentOutcome:
    ok: bool
    proposal: Validated | None = None
    saves: list[Save] = field(default_factory=list)
    rejected_reason: str | None = None


@dataclass
class HumanOutcome:
    ok: bool
    proposal: Validated | None = None
    violations: list[Violation] = field(default_factory=list)
    saves: list[Save] = field(default_factory=list)  # neutral adjustments (e.g. EU reference price)
