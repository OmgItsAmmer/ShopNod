"""Outbox handlers owned by Plan 1: match + notify, shopper push, "Redeemed!", offer ended. All safe to run twice."""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import delete, select, update

from shopnod_core import clock, outbox, push, sse
from shopnod_core import shopper as sh
from shopnod_core.db import session_scope
from shopnod_core.models import Claim, Notification, Offer, ShopperPushToken

from .matching import SHOPPER_PUSH, match_and_notify

log = logging.getLogger("shopnod.shopper")


def _uuid(v) -> uuid.UUID:
    return uuid.UUID(str(v))


@outbox.handler(outbox.OFFER_PUBLISHED, "match_and_notify")
async def on_offer_published(p: dict) -> None:
    sh.clear_feed_cache()
    await match_and_notify(_uuid(p["offer_id"]))


@outbox.handler(SHOPPER_PUSH, "send")
async def send_shopper_push(p: dict) -> None:
    """One push per device. Skipped (not retried) when push isn't configured; gone tokens are removed."""
    iid = _uuid(p["install_id"])
    async with session_scope() as s:
        rows = (await s.execute(select(ShopperPushToken).where(ShopperPushToken.install_id == iid))).scalars().all()
        targets = [(r.id, r.kind, r.token) for r in rows]
    title, body = str(p.get("title", "ShopNod")), str(p.get("body", ""))
    data = {"offer_id": str(p.get("offer_id", "")), "url": f"/offer/{p.get('offer_id', '')}"}
    gone, errors, sent = [], [], 0
    for tid, kind, token in targets:
        try:
            if kind == "webpush":
                sub = json.loads(token)
                keys = sub.get("keys", {})
                await push.send_webpush(sub["endpoint"], keys.get("p256dh", ""), keys.get("auth", ""), {"title": title, "body": body, **data})
            else:
                await push.send_fcm(token, title, body, data)
            sent += 1
        except (push.SubscriptionGone, push.TokenGone):
            gone.append(tid)
        except push.PushUnavailable:
            continue
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{kind}: {exc}")
    if gone:
        async with session_scope() as s:
            await s.execute(delete(ShopperPushToken).where(ShopperPushToken.id.in_(gone)))
    if errors and not sent:
        raise RuntimeError("; ".join(errors)[:300])  # the outbox retries with backoff


@outbox.handler(outbox.REDEMPTION_RECORDED, "shopper")
async def on_redemption(p: dict) -> None:
    """Live "Redeemed! You saved X" on the QR screen. (What it says about their taste is picked up from the redemption
    row itself the next time we predict, so there is nothing to update here.)"""
    sh.clear_feed_cache()
    if not p.get("install_id"):
        return
    iid = _uuid(p["install_id"])
    async with session_scope() as s:
        claim = await s.get(Claim, _uuid(p["claim_id"]))
        if claim is not None and claim.status != "redeemed":
            claim.status = "redeemed"
    await sse.publish(
        sse.shopper_channel(iid), "claim.redeemed",
        {"claim_id": str(p["claim_id"]), "offer_id": str(p["offer_id"]), "saved_minor": int(p.get("discount_minor") or 0)},
    )


async def _ended(offer_id: uuid.UUID, reason: str, *, expire_claims: bool) -> None:
    sh.clear_feed_cache()
    async with session_scope() as s:
        if await s.get(Offer, offer_id) is None:
            return  # deleted (demo reset): feeds stop showing it on their own
        installs = set(
            (await s.execute(select(Claim.install_id).where(Claim.offer_id == offer_id, Claim.install_id.is_not(None)))).scalars().all()
        ) | set((await s.execute(select(Notification.install_id).where(Notification.offer_id == offer_id))).scalars().all())
        if expire_claims:
            await s.execute(update(Claim).where(Claim.offer_id == offer_id, Claim.status == "issued").values(status="expired"))
    for iid in installs:
        await sse.publish(sse.shopper_channel(iid), "offer.ended", {"offer_id": str(offer_id), "reason": reason})


@outbox.handler(outbox.OFFER_ENDED, "shopper")
async def on_offer_ended(p: dict) -> None:
    """Open claims expire and the offer leaves feeds."""
    await _ended(_uuid(p["offer_id"]), str(p.get("reason") or "ended"), expire_claims=True)


@outbox.handler("offer.sold_out", "shopper")
async def on_offer_sold_out(p: dict) -> None:
    """Sold out: no new claims, but claims already issued still work until they expire (Plan 3 S6)."""
    await _ended(_uuid(p["offer_id"]), "sold_out", expire_claims=False)


_ = clock
