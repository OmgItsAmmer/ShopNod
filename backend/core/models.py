"""All tables (Plan 3 §0.4). Portable between Postgres and SQLite.

Owners: Plan 2 owns users..redemptions; Plan 1 owns shoppers..shopper_affinity and creates claims.
Changing a shared table follows the contract rule (PR approved by both plan owners).
Money is an integer in the smallest unit. Times are UTC.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .ids import uuid7

JSONType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator):
    """timestamptz that always returns aware UTC datetimes (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _now() -> datetime:
    from . import clock

    return clock.now()


class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: Uuid(as_uuid=True),
        datetime: UTCDateTime(),
        dict[str, Any]: JSONType,
        list[Any]: JSONType,
    }


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7)


def created() -> Mapped[datetime]:
    return mapped_column(UTCDateTime(), default=_now)


# ── Phase 0 shared tables ────────────────────────────────────────────────
class MarketArea(Base):
    __tablename__ = "market_areas"
    id: Mapped[uuid.UUID] = pk()
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[uuid.UUID] = pk()
    topic: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|sent|dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created()
    __table_args__ = (Index("ix_outbox_status_next", "status", "next_attempt_at"),)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[uuid.UUID] = pk()
    scope: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress|done
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = created()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idem_scope_key"),)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)


# ── Plan 2 tables ────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created()


class Shop(Base):
    __tablename__ = "shops"
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    geohash6: Mapped[str | None] = mapped_column(String(6), nullable=True)
    area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("market_areas.id"), nullable=True)
    hours: Mapped[dict] = mapped_column(JSONType, default=dict)  # {"mon": ["08:00","20:00"], ...}
    quiet_grid: Mapped[dict] = mapped_column(JSONType, default=dict)  # {"mon": ["normal"]*24, ...}
    languages: Mapped[list] = mapped_column(JSONType, default=lambda: ["en"])
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_eu: Mapped[bool] = mapped_column(Boolean, default=False)
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free|pro
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    template_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    onboarding_status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|complete
    stripe_customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = created()
    __table_args__ = (Index("ix_shops_geohash6", "geohash6"),)


class Guardrail(Base):
    __tablename__ = "guardrails"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), unique=True)
    min_price_minor: Mapped[int] = mapped_column(Integer, default=0)
    max_discount_pct: Mapped[int] = mapped_column(Integer, default=20)
    never_discount_item_ids: Mapped[list] = mapped_column(JSONType, default=list)
    blocked_categories: Mapped[list] = mapped_column(JSONType, default=list)
    daily_budget_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekly_budget_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_offers_per_day: Mapped[int] = mapped_column(Integer, default=3)
    max_redemptions_per_offer: Mapped[int] = mapped_column(Integer, default=50)
    allowed_hours: Mapped[dict] = mapped_column(JSONType, default=lambda: {"start": "08:00", "end": "21:00"})
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)


class Item(Base):
    __tablename__ = "items"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40), default="general")
    price_minor: Mapped[int] = mapped_column(Integer)
    regular_price_minor: Mapped[int] = mapped_column(Integer)
    regular_price_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created()


class ItemPriceHistory(Base):
    __tablename__ = "item_price_history"
    id: Mapped[uuid.UUID] = pk()
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id"), index=True)
    price_minor: Mapped[int] = mapped_column(Integer)  # regular price from changed_at onwards
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    type: Mapped[str] = mapped_column(String(16))  # quiet|expiry|manual|simulated
    window: Mapped[dict] = mapped_column(JSONType, default=dict)
    baseline: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = created()


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = pk()
    agent: Mapped[str] = mapped_column(String(40))
    shop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shops.id"), nullable=True, index=True)
    input_summary: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list] = mapped_column(JSONType, default=list)
    output: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_micro_usd: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created()


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    items: Mapped[list] = mapped_column(JSONType, default=list)
    proposed_pct: Mapped[int] = mapped_column(Integer)
    original_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)  # what the AI asked before clamp
    final_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime())
    window_end: Mapped[datetime] = mapped_column(UTCDateTime())
    cap: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(8), default="rules")  # ai|rules
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)  # dashboard|mcp_confirmed
    reject_reason: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reject_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    guardrail_saves: Mapped[list] = mapped_column(JSONType, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = created()


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[uuid.UUID] = pk()
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proposals.id"), nullable=True, unique=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("market_areas.id"), nullable=True)
    geohash6: Mapped[str | None] = mapped_column(String(6), nullable=True)
    items: Mapped[list] = mapped_column(JSONType, default=list)
    pct: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime())
    cap: Mapped[int] = mapped_column(Integer)
    redeemed_count: Mapped[int] = mapped_column(Integer, default=0)
    claimed_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|ended|sold_out
    ended_reason: Mapped[str | None] = mapped_column(String(24), nullable=True)
    copy: Mapped[dict] = mapped_column(JSONType, default=dict)  # lang -> text
    copy_source: Mapped[str] = mapped_column(String(10), default="template")  # ai|template
    brand_campaign_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = created()
    __table_args__ = (Index("ix_offers_status_ends_at", "status", "ends_at"),)


class ShopLearning(Base):
    __tablename__ = "shop_learning"
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), primary_key=True)
    category_pct: Mapped[dict] = mapped_column(JSONType, default=dict)  # category -> EWMA final pct
    accepted_hours: Mapped[dict] = mapped_column(JSONType, default=dict)  # local hour -> count
    reject_counts: Mapped[dict] = mapped_column(JSONType, default=dict)  # reason -> count
    weekly: Mapped[list] = mapped_column(JSONType, default=list)  # [{week, proposals, approved, rate, avg_edit}]
    decisions: Mapped[int] = mapped_column(Integer, default=0)
    applied_ids: Mapped[list] = mapped_column(JSONType, default=list)  # proposal ids already applied (idempotent)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)


class ApprovalConfirmation(Base):
    __tablename__ = "approval_confirmations"
    id: Mapped[uuid.UUID] = pk()
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposals.id"), index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    final_pct: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict] = mapped_column(JSONType, default=dict)  # window/cap overrides
    status: Mapped[str] = mapped_column(String(16), default="awaiting")  # awaiting|confirmed|declined|expired
    requested_via_token_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = created()
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shops.id"), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    actor_kind: Mapped[str] = mapped_column(String(16), default="user")  # user|agent|system|mcp
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = created()


class PersonalAccessToken(Base):
    __tablename__ = "personal_access_tokens"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(12), default="")
    scopes: Mapped[list] = mapped_column(JSONType, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = created()


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    plan: Mapped[str] = mapped_column(String(16), default="free")
    status: Mapped[str] = mapped_column(String(24), default="active")
    current_period_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = created()


class MeterEvent(Base):
    __tablename__ = "meter_events"
    id: Mapped[uuid.UUID] = pk()
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    redemption_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    identifier: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|sent|skipped|failed
    stripe_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created()
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class StripeEvent(Base):
    """Webhook replay protection: each Stripe event id is processed once."""

    __tablename__ = "stripe_events"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    type: Mapped[str] = mapped_column(String(80))
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)


class ShopPushSubscription(Base):
    __tablename__ = "shop_push_subscriptions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = created()


class CategoryTemplate(Base):
    __tablename__ = "category_templates"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    items: Mapped[list] = mapped_column(JSONType, default=list)
    guardrails: Mapped[dict] = mapped_column(JSONType, default=dict)
    quiet_grid: Mapped[dict] = mapped_column(JSONType, default=dict)


class Claim(Base):
    """Plan 1 creates, Plan 2 redeems."""

    __tablename__ = "claims"
    id: Mapped[uuid.UUID] = pk()
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"), index=True)
    install_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    token_jti: Mapped[str] = mapped_column(String(64), unique=True)
    short_code: Mapped[str] = mapped_column(String(6), index=True)
    status: Mapped[str] = mapped_column(String(12), default="issued")  # issued|redeemed|expired
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = created()


class Redemption(Base):
    __tablename__ = "redemptions"
    id: Mapped[uuid.UUID] = pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id"), unique=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"), index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), index=True)
    install_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    billable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    waste_units: Mapped[int] = mapped_column(Integer, default=0)
    redeemed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)


class OfferReachStat(Base):
    """Plan 1 maintains: aggregate reach/notified per offer. Plan 2 reads (shows only when >= 10)."""

    __tablename__ = "offer_reach_stats"
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    notified: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)


# ── Plan 1 tables ───────────────────────────────────────────────────────
class Shopper(Base):
    __tablename__ = "shoppers"
    install_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    geohash6: Mapped[str | None] = mapped_column(String(6), nullable=True)
    area_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    languages: Mapped[list] = mapped_column(JSONType, default=lambda: ["en"])
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    created_at: Mapped[datetime] = created()
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[uuid.UUID] = pk()
    install_id: Mapped[uuid.UUID] = mapped_column(index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    granted_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)
    withdrawn_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(16), default="1")


class ShopperPreference(Base):
    __tablename__ = "shopper_preferences"
    install_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_now)


class ShoppingList(Base):
    __tablename__ = "shopping_lists"
    id: Mapped[uuid.UUID] = pk()
    install_id: Mapped[uuid.UUID] = mapped_column(index=True)
    items: Mapped[list] = mapped_column(JSONType, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ShopperPushToken(Base):
    __tablename__ = "shopper_push_tokens"
    id: Mapped[uuid.UUID] = pk()
    install_id: Mapped[uuid.UUID] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(10))  # fcm|webpush
    token: Mapped[str] = mapped_column(Text)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = pk()
    install_id: Mapped[uuid.UUID] = mapped_column(index=True)
    offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("offers.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = created()
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ShopperEvent(Base):
    __tablename__ = "shopper_events"
    id: Mapped[uuid.UUID] = pk()
    install_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = created()
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ShopperAffinity(Base):
    __tablename__ = "shopper_affinity"
    id: Mapped[uuid.UUID] = pk()
    install_id: Mapped[uuid.UUID] = mapped_column(index=True)
    category: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


ALL_TABLE_NAMES = sorted(Base.metadata.tables.keys())
_ = BigInteger  # re-exported for migrations that need it
