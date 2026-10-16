"""Create a claim for a shop's offer and print its QR text and short code. For testing the scan page
before Plan 1's shopper app exists.

    python infra/seed/dev_claim.py                     # newest active offer of the first demo shop
    python infra/seed/dev_claim.py --shop <shop_id>    # newest active offer of a specific shop
    python infra/seed/dev_claim.py --offer <offer_id>
"""
from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import timedelta

from sqlalchemy import select

from shopnod_core import clock, db, tokens
from shopnod_core.models import Claim, Offer, Shop

CLAIM_TTL = timedelta(minutes=30)


async def make_claim(offer_id: str | None = None, shop_id: str | None = None) -> dict[str, str]:
    async with db.session_scope() as s:
        if offer_id:
            offer = await s.get(Offer, uuid.UUID(offer_id))
        else:
            stmt = select(Offer).where(Offer.status == "active")
            if shop_id:
                stmt = stmt.where(Offer.shop_id == uuid.UUID(shop_id))
            offer = (await s.execute(stmt.order_by(Offer.created_at.desc()))).scalars().first()
        if offer is None:
            raise SystemExit("No active offer found. Approve a proposal in the dashboard first.")
        shop = await s.get(Shop, offer.shop_id)
        expires = min(clock.now() + CLAIM_TTL, offer.ends_at)
        claim = Claim(
            offer_id=offer.id, install_id=uuid.uuid4(), token_jti=tokens.new_jti(), short_code=tokens.new_short_code(),
            status="issued", expires_at=expires,
        )
        s.add(claim)
        await s.flush()
        qr = tokens.issue_claim(claim, offer)
        return {"shop": shop.name if shop else "?", "offer_id": str(offer.id), "pct": str(offer.pct),
                "short_code": claim.short_code, "qr_text": qr, "expires_at": expires.isoformat()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offer")
    ap.add_argument("--shop")
    a = ap.parse_args()
    out = asyncio.run(make_claim(a.offer, a.shop))
    for k, v in out.items():
        print(f"{k:>10}: {v}")
