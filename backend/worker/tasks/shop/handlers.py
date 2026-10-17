"""Outbox handlers owned by Plan 2: live updates (SSE), shopkeeper push, learning, billing."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete, select

from shopnod_core import billing, learning, outbox, push, sse
from shopnod_core.copyagent import fmt_money
from shopnod_core.db import session_scope
from shopnod_core.guardrails.windows import local_hour  # noqa: F401
from shopnod_core.models import Offer, Proposal, Shop, ShopPushSubscription

log = logging.getLogger("shopnod.handlers")


def _sid(p: dict[str, Any]) -> uuid.UUID:
    return uuid.UUID(str(p["shop_id"]))


# ── live updates (SSE) ───────────────────────────────────────────────────
@outbox.handler(outbox.PROPOSAL_CREATED, "sse")
async def sse_proposal_created(p: dict) -> None:
    await sse.publish_shop(_sid(p), "proposal.created", {"proposal_id": p["proposal_id"], "source": p.get("source")})


@outbox.handler(outbox.PROPOSAL_DECIDED, "sse")
async def sse_proposal_decided(p: dict) -> None:
    await sse.publish_shop(
        _sid(p), "proposal.decided",
        {"proposal_id": p["proposal_id"], "decision": p["decision"], "final_pct": p.get("final_pct"), "channel": p.get("channel")},
    )


@outbox.handler("proposal.expired", "sse")
async def sse_proposal_expired(p: dict) -> None:
    await sse.publish_shop(_sid(p), "proposal.decided", {"proposal_id": p["proposal_id"], "decision": "expired"})


@outbox.handler(outbox.CONFIRMATION_REQUESTED, "sse")
async def sse_confirmation(p: dict) -> None:
    await sse.publish_shop(
        _sid(p), "confirmation.requested",
        {"confirmation_id": p["confirmation_id"], "proposal_id": p["proposal_id"], "final_pct": p.get("final_pct")},
    )


@outbox.handler(outbox.OFFER_PUBLISHED, "shop_sse")
async def sse_offer_published(p: dict) -> None:
    await sse.publish_shop(_sid(p), "offer.published", {"offer_id": p["offer_id"]})


@outbox.handler(outbox.OFFER_ENDED, "shop_sse")
async def sse_offer_ended(p: dict) -> None:
    await sse.publish_shop(_sid(p), "offer.ended", {"offer_id": p["offer_id"], "reason": p.get("reason")})


@outbox.handler("offer.sold_out", "shop_sse")
async def sse_offer_sold_out(p: dict) -> None:
    await sse.publish_shop(_sid(p), "offer.ended", {"offer_id": p["offer_id"], "reason": "sold_out"})


@outbox.handler(outbox.REDEMPTION_RECORDED, "shop_sse")
async def sse_redemption(p: dict) -> None:
    await sse.publish_shop(
        _sid(p), "redemption.recorded", {"redemption_id": p["redemption_id"], "offer_id": p["offer_id"], "discount_minor": p.get("discount_minor")}
    )


@outbox.handler(outbox.CLAIM_CREATED, "shop_sse")
async def sse_claim(p: dict) -> None:
    async with session_scope() as s:
        offer = await s.get(Offer, uuid.UUID(str(p["offer_id"])))
    if offer is not None:
        await sse.publish_shop(offer.shop_id, "claim.created", {"offer_id": p["offer_id"], "claim_id": p.get("claim_id")})


# ── learning (right after each decision) ────────────────────────────────
@outbox.handler(outbox.PROPOSAL_DECIDED, "learning")
async def learn(p: dict) -> None:
    async with session_scope() as s:
        await learning.update_learning(s, uuid.UUID(str(p["proposal_id"])))


# ── billing ──────────────────────────────────────────────────────────────
@outbox.handler(outbox.REDEMPTION_RECORDED, "meter")
async def meter(p: dict) -> None:
    """One row in the usage ledger per billable redemption."""
    await billing.meter_redemption(uuid.UUID(str(p["redemption_id"])))



# ── shopkeeper push (notify_shopkeeper sender) ───────────────────────────
async def notify_shopkeeper(shop_id: uuid.UUID, title: str, body: str, url: str = "/dashboard", tag: str | None = None) -> int:
    """Send a Web Push to every subscription of the shop. Returns the number sent."""
    if not push.webpush_configured():
        return 0
    async with session_scope() as s:
        subs = (await s.execute(select(ShopPushSubscription).where(ShopPushSubscription.shop_id == shop_id))).scalars().all()
        targets = [(x.id, x.endpoint, x.p256dh, x.auth) for x in subs]
    sent, gone = 0, []
    errors: list[str] = []
    for sid, endpoint, p256dh, auth in targets:
        try:
            await push.send_webpush(endpoint, p256dh, auth, {"title": title, "body": body, "url": url, "tag": tag or "shopnod"})
            sent += 1
        except push.SubscriptionGone:
            gone.append(sid)
        except push.PushUnavailable:
            return sent
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    if gone:
        async with session_scope() as s:
            await s.execute(delete(ShopPushSubscription).where(ShopPushSubscription.id.in_(gone)))
    if errors and not sent:
        raise RuntimeError("; ".join(errors)[:300])  # outbox retries with backoff
    return sent


def _fmt_window(shop: Shop, start, end) -> str:
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(shop.timezone)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    return f"{start.astimezone(tz):%H:%M}–{end.astimezone(tz):%H:%M}"


@outbox.handler(outbox.PROPOSAL_CREATED, "notify_shopkeeper")
async def push_proposal_created(p: dict) -> None:
    async with session_scope() as s:
        prop = await s.get(Proposal, uuid.UUID(str(p["proposal_id"])))
        if prop is None or prop.status != "pending":
            return
        shop = await s.get(Shop, prop.shop_id)
        cats = sorted({i.get("name", "") for i in prop.items})[:2]
        body = f"New offer to approve: {prop.proposed_pct}% {', '.join(cats)}, {_fmt_window(shop, prop.window_start, prop.window_end)}"
        shop_id = prop.shop_id
    await notify_shopkeeper(shop_id, "ShopNod", body, "/dashboard", tag=f"proposal-{p['proposal_id']}")


@outbox.handler(outbox.CONFIRMATION_REQUESTED, "notify_shopkeeper")
async def push_confirmation(p: dict) -> None:
    await notify_shopkeeper(
        _sid(p), "ShopNod", f"Your AI assistant asked to publish a {p.get('final_pct')}% offer. Confirm it in the dashboard.",
        "/dashboard", tag=f"confirm-{p['confirmation_id']}",
    )


_ = fmt_money  # re-exported for tests
