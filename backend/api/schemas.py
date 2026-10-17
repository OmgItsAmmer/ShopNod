"""Request/response models for the Plan 2 API. These drive the generated TypeScript types."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── auth ─────────────────────────────────────────────────────────────────
class UserOut(ORM):
    id: uuid.UUID
    email: str | None = None
    is_demo: bool
    is_admin: bool


class ShopSummary(ORM):
    id: uuid.UUID
    name: str
    category: str
    onboarding_status: str
    is_demo: bool
    plan: str
    currency: str
    timezone: str
    geohash6: str | None = None


class MeOut(BaseModel):
    user: UserOut
    shop: ShopSummary | None = None


class MagicLinkIn(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OkOut(BaseModel):
    ok: bool = True


# ── onboarding ───────────────────────────────────────────────────────────
class TemplateItemOut(BaseModel):
    name: str
    category: str
    price: float


class TemplateOut(BaseModel):
    key: str
    name: str
    item_count: int
    max_discount_pct: int
    sample_items: list[TemplateItemOut]


class ShopCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=40)


class LocationIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    market: str | None = Field(default=None, max_length=64, description="Market slug, e.g. 'demo'")
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_eu: bool | None = None


class ApplyTemplateIn(BaseModel):
    template_key: str | None = None


class ShopOut(ORM):
    id: uuid.UUID
    name: str
    category: str
    lat: float | None
    lng: float | None
    geohash6: str | None
    area_id: uuid.UUID | None
    hours: dict[str, Any]
    quiet_grid: dict[str, Any]
    languages: list[str]
    timezone: str
    currency: str
    is_eu: bool
    plan: str
    is_demo: bool
    template_key: str | None
    onboarding_status: str


class ShopUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=40)
    hours: dict[str, list[str]] | None = None
    quiet_grid: dict[str, list[Literal["busy", "normal", "quiet"]]] | None = None
    languages: list[Literal["en", "ur", "ar", "es"]] | None = None
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_eu: bool | None = None

    @field_validator("quiet_grid")
    @classmethod
    def _grid(cls, v):
        if v is not None:
            for day, hours in v.items():
                if day not in ("mon", "tue", "wed", "thu", "fri", "sat", "sun") or len(hours) != 24:
                    raise ValueError("quiet_grid needs 24 hourly values for each weekday (mon..sun)")
        return v

    @field_validator("hours")
    @classmethod
    def _hours(cls, v):
        if v is not None:
            for day, rng in v.items():
                if day not in ("mon", "tue", "wed", "thu", "fri", "sat", "sun") or len(rng) != 2:
                    raise ValueError("hours needs [open, close] per weekday")
        return v


class CompleteOut(BaseModel):
    shop: ShopOut
    items: int


# ── items ────────────────────────────────────────────────────────────────
class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="general", max_length=40)
    price_minor: int = Field(ge=0, le=100_000_000)
    regular_price_minor: int | None = Field(default=None, ge=0, le=100_000_000)
    cost_minor: int | None = Field(default=None, ge=0, le=100_000_000)
    min_price_minor: int | None = Field(default=None, ge=0, le=100_000_000)
    expires_at: datetime | None = None
    quantity: int = Field(default=0, ge=0, le=1_000_000)
    active: bool = True


class ItemOut(ORM):
    id: uuid.UUID
    name: str
    category: str
    price_minor: int
    regular_price_minor: int
    regular_price_since: datetime | None = None
    cost_minor: int | None
    min_price_minor: int | None
    expires_at: datetime | None
    quantity: int
    active: bool


# ── guardrails ───────────────────────────────────────────────────────────
class AllowedHours(BaseModel):
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class GuardrailIn(BaseModel):
    min_price_minor: int = Field(default=0, ge=0)
    max_discount_pct: int = Field(ge=1, le=90)
    never_discount_item_ids: list[uuid.UUID] = []
    blocked_categories: list[str] = []
    daily_budget_minor: int | None = Field(default=None, ge=0)
    weekly_budget_minor: int | None = Field(default=None, ge=0)
    max_offers_per_day: int = Field(ge=1, le=50)
    max_redemptions_per_offer: int = Field(ge=1, le=10_000)
    allowed_hours: AllowedHours


class GuardrailOut(BaseModel):
    min_price_minor: int
    max_discount_pct: int
    never_discount_item_ids: list[str]
    blocked_categories: list[str]
    daily_budget_minor: int | None
    weekly_budget_minor: int | None
    max_offers_per_day: int
    max_redemptions_per_offer: int
    allowed_hours: dict[str, str]
    always_blocked_categories: list[str]
    hint: str | None = None
    would_block: int = 0


# ── signals / proposals ─────────────────────────────────────────────────
class SignalOut(BaseModel):
    signal_id: uuid.UUID
    agent_queued: bool = True
    skipped_reason: str | None = None


class ProposalItem(BaseModel):
    item_id: str
    name: str
    category: str | None = None
    was_minor: int
    new_price_minor: int
    cost_minor: int | None = None
    pct: int | None = None


class GuardrailSave(BaseModel):
    rule: str
    message: str
    before: Any = None
    after: Any = None
    item_id: str | None = None


class ProposalOut(BaseModel):
    id: uuid.UUID
    shop_id: uuid.UUID
    status: str
    source: Literal["ai", "rules"]
    items: list[ProposalItem]
    proposed_pct: int
    original_pct: int | None
    final_pct: int | None
    window_start: datetime
    window_end: datetime
    cap: int
    reason: str
    channel: str | None = None
    reject_reason: str | None = None
    guardrail_saves: list[GuardrailSave] = []
    agent_run_id: uuid.UUID | None = None
    created_at: datetime
    decided_at: datetime | None = None
    confirmation_id: uuid.UUID | None = None


class WindowIn(BaseModel):
    start: datetime
    end: datetime


class ApproveIn(BaseModel):
    final_pct: int | None = Field(default=None, ge=0, le=100)
    window: WindowIn | None = None
    cap: int | None = Field(default=None, ge=0, le=100_000)


class RejectIn(BaseModel):
    reason: Literal["wrong_items", "wrong_time", "too_generous", "other"]
    note: str | None = Field(default=None, max_length=500)


class OfferOut(BaseModel):
    id: uuid.UUID
    shop_id: uuid.UUID
    proposal_id: uuid.UUID | None
    items: list[ProposalItem]
    pct: int
    starts_at: datetime
    ends_at: datetime
    cap: int
    redeemed_count: int
    status: str
    ended_reason: str | None = None
    copy_text: dict[str, str]
    copy_source: Literal["ai", "template"]
    created_at: datetime


class ApproveOut(BaseModel):
    offer: OfferOut
    proposal: ProposalOut


class AudienceNumber(BaseModel):
    value: int | None
    label: str


class OfferStatsOut(BaseModel):
    offer_id: str
    status: str
    pct: int
    cap: int
    claims: int
    redemptions: int
    discount_given_minor: int
    reach: AudienceNumber
    notified: AudienceNumber
    conversion: float | None
    time_to_first_redemption_s: int | None
    waste_units: int


class ConfirmationOut(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    final_pct: int
    status: str
    expires_at: datetime
    created_at: datetime
    proposal: ProposalOut | None = None


# ── redemptions ─────────────────────────────────────────────────────────
class RedeemIn(BaseModel):
    payload: str | None = Field(default=None, max_length=2000)
    short_code: str | None = Field(default=None, min_length=4, max_length=12)


class RedeemItem(BaseModel):
    name: str
    was_minor: int
    new_price_minor: int


class RedeemOfferOut(BaseModel):
    id: str
    pct: int
    shop_id: str
    status: str
    ends_at: str


class RedeemOut(BaseModel):
    result: Literal["ok", "invalid", "expired", "wrong_shop", "already_redeemed", "offer_ended"]
    discount_pct: int | None
    items: list[RedeemItem]
    offer: RedeemOfferOut | None
    message: str
    redemption_id: str | None = None


# ── tokens / push ───────────────────────────────────────────────────────
class TokenCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[Literal["shopkeeper:read", "shopkeeper:approve"]] = Field(min_length=1)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class TokenOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked: bool


class TokenCreatedOut(TokenOut):
    token: str
    mcp_config: dict[str, Any]


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=4, max_length=100)


class PushUnsubscribeIn(BaseModel):
    endpoint: str


# ── insights / billing / audit / agent runs ─────────────────────────────
class SummaryOut(BaseModel):
    currency: str
    redemptions_today: int
    extra_customers: int
    extra_customers_is_estimate: bool
    discount_given_minor: int
    waste_avoided_units: int
    margin_kept_minor: int
    estimated_extra_revenue_minor: int
    roi: float | None
    roi_is_estimate: bool
    fees_minor: int


class BillingOut(BaseModel):
    """Pay per redemption. Usage only: no card is taken and no money moves in this demo."""

    plan: str
    month: str
    billable_redemptions: int
    usage_recorded: int
    redemptions_today: int
    fee_per_redemption_usd_cents: int
    upcoming_invoice_usd_cents: int
    pro_unlocks: list[str]
    demo: bool


class AuditOut(BaseModel):
    id: uuid.UUID
    action: str
    actor_kind: str
    actor_user_id: uuid.UUID | None
    entity_type: str | None
    entity_id: str | None
    channel: str | None
    data: dict[str, Any]
    created_at: datetime


class AgentRunOut(BaseModel):
    id: uuid.UUID
    agent: str
    shop_id: uuid.UUID | None
    input_summary: str
    tool_calls: list[dict[str, Any]]
    output: dict[str, Any] | None
    latency_ms: int
    tokens: int
    cost_micro_usd: int
    fallback_used: bool
    fallback_reason: str | None
    error: str | None
    created_at: datetime
    proposal_id: uuid.UUID | None = None


# ── admin ───────────────────────────────────────────────────────────────
class FlagIn(BaseModel):
    enabled: bool


class SimIn(BaseModel):
    enabled: bool | None = None
    burst: bool = False


class AdminStatusOut(BaseModel):
    outbox: dict[str, int]
    breakers: dict[str, str]
    queue_length: int | None
    flags: dict[str, bool]
    last_agent_runs: list[AgentRunOut]
