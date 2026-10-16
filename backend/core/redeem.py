"""Redeem a claim at the counter (Plan 2 Phase 5, Plan 3 §0.7).

Locks the claim row (SELECT … FOR UPDATE), then inserts the redemption. `redemptions.claim_id` is
unique, so a claim can never be redeemed twice, even if every other check fails.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import audit, clock, outbox, tokens
from .db import session_scope
from .models import Item, Redemption

RESULT_MESSAGES = {
    "ok": "Apply {pct}% to this customer's items.",
    "invalid": "This code isn't valid.",
    "expired": "This code has expired.",
    "wrong_shop": "This code is for a different shop.",
    "already_redeemed": "Already redeemed.",
    "offer_ended": "This offer has ended.",
}


def _offer_summary(offer) -> dict[str, Any]:
    return {"id": str(offer.id), "pct": offer.pct, "shop_id": str(offer.shop_id), "status": offer.status,
            "ends_at": offer.ends_at.isoformat()}


def _discount_per_redemption(offer) -> int:
    diffs = [int(i.get("was_minor", 0)) - int(i.get("new_price_minor", 0)) for i in (offer.items or [])]
    return max(sum(diffs) // max(len(diffs), 1), 0)


async def redeem(
    shop_id: uuid.UUID,
    *,
    payload: str | None = None,
    short_code: str | None = None,
    idempotency_key: str | None = None,
    is_simulated: bool = False,
    actor_user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Returns {result, discount_pct, items, offer, message[, redemption_id]}. Never raises for a bad code."""
    async with session_scope() as s:
        check = await tokens.verify_claim(s, payload, shop_id, short_code=short_code, lock=True)
        offer = check.offer
        if check.result != "ok" or check.claim is None or offer is None:
            return {
                "result": check.result,
                "discount_pct": None,
                "items": [],
                "offer": _offer_summary(offer) if offer and offer.shop_id == shop_id else None,
                "message": RESULT_MESSAGES.get(check.result, "Not valid."),
            }
        claim = check.claim
        now = clock.now()
        item_ids = [uuid.UUID(i["item_id"]) for i in (offer.items or []) if i.get("item_id")]
        waste = 0
        if item_ids:
            rows = (await s.execute(select(Item).where(Item.id.in_(item_ids), Item.shop_id == shop_id))).scalars().all()
            if any(r.expires_at and now < r.expires_at <= now + timedelta(hours=24) for r in rows):
                waste = 1
        red = Redemption(
            claim_id=claim.id, offer_id=offer.id, shop_id=shop_id, install_id=claim.install_id,
            discount_minor=_discount_per_redemption(offer), billable=True, is_simulated=is_simulated,
            waste_units=waste, redeemed_at=now, idempotency_key=idempotency_key,
        )
        try:
            async with s.begin_nested():
                s.add(red)
                await s.flush()
        except IntegrityError:
            return {"result": "already_redeemed", "discount_pct": None, "items": [], "offer": _offer_summary(offer),
                    "message": RESULT_MESSAGES["already_redeemed"]}
        claim.status = "redeemed"
        offer.redeemed_count += 1
        sold_out = offer.status == "active" and offer.redeemed_count >= offer.cap
        if sold_out:
            offer.status, offer.ended_reason = "sold_out", "cap_reached"
            await outbox.emit(s, "offer.sold_out", {"offer_id": offer.id, "shop_id": shop_id})
        await audit.record(
            s, shop_id=shop_id, action="redemption.recorded", actor_user_id=actor_user_id,
            actor_kind="system" if is_simulated else "user", entity_type="redemption", entity_id=red.id, channel="dashboard",
            data={"offer_id": offer.id, "claim_id": claim.id, "simulated": is_simulated},
        )
        await outbox.emit(
            s, outbox.REDEMPTION_RECORDED,
            {"redemption_id": red.id, "claim_id": claim.id, "offer_id": offer.id, "shop_id": shop_id,
             "install_id": claim.install_id, "discount_minor": red.discount_minor, "billable": red.billable},
        )
        items = [{"name": i["name"], "was_minor": i["was_minor"], "new_price_minor": i["new_price_minor"]} for i in offer.items]
        result = {
            "result": "ok", "discount_pct": offer.pct, "items": items, "offer": _offer_summary(offer),
            "message": RESULT_MESSAGES["ok"].format(pct=offer.pct), "redemption_id": str(red.id),
        }
    outbox.kick()
    return result
