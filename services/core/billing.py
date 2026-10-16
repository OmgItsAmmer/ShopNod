"""Stripe (test mode): a customer per shop, one meter event per billable redemption, Pro via Checkout.

Everything degrades gracefully without STRIPE_SECRET_KEY: meter events are recorded as `skipped`
and the billing page still shows honest usage numbers.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import audit, clock
from .breaker import get_breaker
from .db import session_scope
from .errors import AppError, ErrorCode
from .guardrails.windows import local_day_bounds
from .models import MeterEvent, Redemption, Shop, StripeEvent, Subscription, User
from .settings import get_settings

log = logging.getLogger("shopnod.billing")


def stripe_configured() -> bool:
    return bool(get_settings().STRIPE_SECRET_KEY)


def _stripe():
    import stripe

    stripe.api_key = get_settings().STRIPE_SECRET_KEY
    stripe.max_network_retries = 2
    return stripe


async def _call(fn, *args, **kwargs):
    breaker = get_breaker("stripe")
    if not breaker.allow():
        raise RuntimeError("stripe circuit open")
    try:
        result = await asyncio.to_thread(fn, *args, **kwargs)
    except Exception:
        breaker.record_failure()
        raise
    breaker.record_success()
    return result


async def create_stripe_customer(shop_id: uuid.UUID) -> str | None:
    """Create the test-mode customer (with the metered price). Safe to run twice."""
    async with session_scope() as s:
        shop = await s.get(Shop, shop_id)
        if shop is None:
            return None
        if shop.stripe_customer_id:
            return shop.stripe_customer_id
        owner = await s.get(User, shop.owner_id)
        name, email = shop.name, owner.email if owner else None
    if not stripe_configured():
        log.info("stripe not configured; skipping customer creation", extra={"shop_id": str(shop_id)})
        return None
    stripe = _stripe()
    settings = get_settings()
    cust = await _call(
        stripe.Customer.create, name=name, email=email or None, metadata={"shop_id": str(shop_id)},
        idempotency_key=f"shopnod-customer-{shop_id}",
    )
    sub_id = None
    if settings.STRIPE_METERED_PRICE_ID:
        sub = await _call(
            stripe.Subscription.create, customer=cust["id"], items=[{"price": settings.STRIPE_METERED_PRICE_ID}],
            idempotency_key=f"shopnod-metered-sub-{shop_id}",
        )
        sub_id = sub["id"]
    async with session_scope() as s:
        shop = await s.get(Shop, shop_id)
        shop.stripe_customer_id = cust["id"]
        s.add(Subscription(shop_id=shop_id, stripe_subscription_id=sub_id, stripe_customer_id=cust["id"], plan="metered", status="active"))
    return cust["id"]


async def meter_redemption(redemption_id: uuid.UUID) -> str:
    """Send one meter event (Stripe ignores duplicates via `identifier`). Returns the meter row status."""
    settings = get_settings()
    identifier = str(redemption_id)
    async with session_scope() as s:
        red = await s.get(Redemption, redemption_id)
        if red is None or not red.billable:
            return "skipped"
        ev = (await s.execute(select(MeterEvent).where(MeterEvent.redemption_id == redemption_id))).scalar_one_or_none()
        if ev is None:
            ev = MeterEvent(shop_id=red.shop_id, redemption_id=redemption_id, identifier=identifier, status="pending")
            s.add(ev)
            await s.flush()
        if ev.status == "sent":
            return "sent"
        shop = await s.get(Shop, red.shop_id)
        customer = shop.stripe_customer_id if shop else None
        if not stripe_configured() or not customer:
            ev.status = "skipped"
            ev.error = "stripe not configured" if not stripe_configured() else "shop has no stripe customer yet"
            return "skipped"
    try:
        stripe = _stripe()
        res = await _call(
            stripe.billing.MeterEvent.create, event_name=settings.STRIPE_METER_EVENT_NAME,
            payload={"stripe_customer_id": customer, "value": "1"}, identifier=identifier,
        )
    except Exception as exc:
        async with session_scope() as s:
            ev = (await s.execute(select(MeterEvent).where(MeterEvent.redemption_id == redemption_id))).scalar_one()
            ev.status, ev.error = "failed", str(exc)[:300]
        raise
    async with session_scope() as s:
        ev = (await s.execute(select(MeterEvent).where(MeterEvent.redemption_id == redemption_id))).scalar_one()
        ev.status, ev.sent_at, ev.error = "sent", clock.now(), None
        ev.stripe_ref = str(res.get("identifier", identifier)) if hasattr(res, "get") else identifier
    return "sent"


async def overview(session: AsyncSession, shop: Shop, now: datetime | None = None) -> dict[str, Any]:
    now = now or clock.now()
    local = now.astimezone(timezone.utc)
    month_start = datetime(local.year, local.month, 1, tzinfo=timezone.utc)
    billable = int(
        (await session.execute(select(func.count()).select_from(Redemption).where(Redemption.shop_id == shop.id, Redemption.billable.is_(True), Redemption.redeemed_at >= month_start))).scalar_one()
    )
    sent = int(
        (await session.execute(select(func.count()).select_from(MeterEvent).where(MeterEvent.shop_id == shop.id, MeterEvent.status == "sent", MeterEvent.created_at >= month_start))).scalar_one()
    )
    today_start, today_end = local_day_bounds(now, shop.timezone)
    today = int(
        (await session.execute(select(func.count()).select_from(Redemption).where(Redemption.shop_id == shop.id, Redemption.redeemed_at >= today_start, Redemption.redeemed_at < today_end))).scalar_one()
    )
    settings = get_settings()
    sub = (await session.execute(select(Subscription).where(Subscription.shop_id == shop.id).order_by(Subscription.created_at.desc()))).scalars().first()
    fee = settings.REDEMPTION_FEE_USD_CENTS
    return {
        "plan": shop.plan,
        "stripe_configured": stripe_configured(),
        "stripe_customer": bool(shop.stripe_customer_id),
        "month": month_start.strftime("%Y-%m"),
        "billable_redemptions": billable,
        "meter_events_sent": sent,
        "redemptions_today": today,
        "fee_per_redemption_usd_cents": fee,
        "upcoming_invoice_usd_cents": 0 if shop.plan == "pro" else billable * fee,
        "pro_unlocks": ["Unlimited offers", "Auto-approve rules", "WhatsApp alerts", "Multi-language copy", "Analytics"],
        "subscription_status": sub.status if sub else None,
        "test_mode": True,
    }


async def checkout_pro(shop_id: uuid.UUID) -> str:
    settings = get_settings()
    if not stripe_configured() or not settings.STRIPE_PRO_PRICE_ID:
        raise AppError(ErrorCode.billing_unavailable, "Upgrading isn't set up yet in this demo (Stripe test keys are missing).", 503)
    async with session_scope() as s:
        shop = await s.get(Shop, shop_id)
        customer = shop.stripe_customer_id
    stripe = _stripe()
    if not customer:
        customer = await create_stripe_customer(shop_id)
    sess = await _call(
        stripe.checkout.Session.create, mode="subscription", customer=customer,
        line_items=[{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
        success_url=f"{settings.SHOP_WEB_URL}/billing?upgraded=1", cancel_url=f"{settings.SHOP_WEB_URL}/billing",
        client_reference_id=str(shop_id), metadata={"shop_id": str(shop_id)},
    )
    return sess["url"]


async def portal(shop_id: uuid.UUID) -> str:
    if not stripe_configured():
        raise AppError(ErrorCode.billing_unavailable, "The billing portal isn't available in this demo.", 503)
    async with session_scope() as s:
        shop = await s.get(Shop, shop_id)
        customer = shop.stripe_customer_id
    if not customer:
        raise AppError(ErrorCode.billing_unavailable, "No billing account yet. Finish a redemption first.", 409)
    stripe = _stripe()
    sess = await _call(stripe.billing_portal.Session.create, customer=customer, return_url=f"{get_settings().SHOP_WEB_URL}/billing")
    return sess["url"]


# ── webhooks ─────────────────────────────────────────────────────────────
def verify_webhook(payload: bytes, signature_header: str | None, tolerance_s: int = 300) -> dict[str, Any]:
    """Check Stripe's signature (HMAC-SHA256 over `timestamp.payload`) and return the parsed event."""
    import json

    secret = get_settings().STRIPE_WEBHOOK_SECRET
    if not secret or not signature_header:
        raise AppError(ErrorCode.webhook_signature_invalid, "Missing webhook signature.", 400)
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    ts = parts.get("t")
    sigs = [v for k, v in (p.split("=", 1) for p in signature_header.split(",") if "=" in p) if k == "v1"]
    if not ts or not sigs:
        raise AppError(ErrorCode.webhook_signature_invalid, "Bad webhook signature.", 400)
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, "sha256").hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise AppError(ErrorCode.webhook_signature_invalid, "Bad webhook signature.", 400)
    if abs(clock.now().timestamp() - int(ts)) > tolerance_s:
        raise AppError(ErrorCode.webhook_signature_invalid, "Webhook timestamp is too old.", 400)
    return json.loads(payload)


async def handle_event(event: dict[str, Any]) -> bool:
    """Process each Stripe event id only once. Returns False for a replay."""
    from sqlalchemy.exc import IntegrityError

    async with session_scope() as s:
        s.add(StripeEvent(id=event["id"], type=event.get("type", ""), received_at=clock.now()))
        try:
            await s.flush()
        except IntegrityError:
            await s.rollback()
            return False
        obj = (event.get("data") or {}).get("object") or {}
        typ = event.get("type", "")
        if typ == "checkout.session.completed":
            shop_id = (obj.get("metadata") or {}).get("shop_id") or obj.get("client_reference_id")
            if shop_id:
                shop = await s.get(Shop, uuid.UUID(shop_id))
                if shop is not None:
                    shop.plan = "pro"
                    if obj.get("customer") and not shop.stripe_customer_id:
                        shop.stripe_customer_id = obj["customer"]
                    s.add(Subscription(shop_id=shop.id, stripe_subscription_id=obj.get("subscription"), stripe_customer_id=obj.get("customer"), plan="pro", status="active"))
                    await audit.record(s, shop_id=shop.id, action="billing.upgraded", actor_kind="system", data={"event": event["id"]})
        elif typ in ("customer.subscription.updated", "customer.subscription.deleted"):
            sub = (await s.execute(select(Subscription).where(Subscription.stripe_subscription_id == obj.get("id")))).scalars().first()
            if sub is not None:
                sub.status = obj.get("status", sub.status)
                shop = await s.get(Shop, sub.shop_id)
                if shop is not None and sub.plan == "pro":
                    shop.plan = "pro" if sub.status in ("active", "trialing") and typ != "customer.subscription.deleted" else "free"
    return True
