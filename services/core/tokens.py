"""Signed QR claim tokens (Ed25519 JWS) and shop-side verification (Plan 3 §0.7).

The token holds jti, oid (offer), sid (shop), exp. It does NOT hold the install id.
"""
from __future__ import annotations

import base64
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .models import Claim, Offer
from .settings import get_settings

QR_PREFIX = "SN1:"
SHORT_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L look-alikes


def _private_key() -> Ed25519PrivateKey:
    raw = get_settings().QR_SIGNING_KEY
    if raw:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw))
    # Dev only: deterministic key so api and worker agree without configuration.
    seed = hashlib.sha256(b"shopnod-dev-qr-key|" + get_settings().JWT_SIGNING_KEY.encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_key_pem() -> bytes:
    return _private_key().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def generate_qr_signing_key() -> str:
    k = Ed25519PrivateKey.generate()
    return base64.b64encode(
        k.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
        )
    ).decode()


def issue_claim(claim: Claim, offer: Offer) -> str:
    """Return the QR text `SN1:<jws>`."""
    priv = _private_key()
    pem = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    token = jwt.encode(
        {
            "jti": claim.token_jti,
            "oid": str(offer.id),
            "sid": str(offer.shop_id),
            "exp": int(claim.expires_at.timestamp()),
        },
        pem,
        algorithm="EdDSA",
    )
    return QR_PREFIX + token


def new_short_code() -> str:
    import secrets

    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(6))


def new_jti() -> str:
    return uuid.uuid4().hex


@dataclass
class ClaimCheck:
    result: str  # ok|invalid|expired|wrong_shop|already_redeemed|offer_ended
    claim: Claim | None = None
    offer: Offer | None = None


async def _load(session: AsyncSession, claim_id_where, lock: bool) -> tuple[Claim | None, Offer | None]:
    stmt = select(Claim).where(claim_id_where)
    if lock:
        stmt = stmt.with_for_update()
    claim = (await session.execute(stmt)).scalar_one_or_none()
    offer = await session.get(Offer, claim.offer_id) if claim else None
    return claim, offer


def _evaluate(claim: Claim | None, offer: Offer | None, shop_id: uuid.UUID) -> ClaimCheck:
    if claim is None or offer is None:
        return ClaimCheck("invalid")
    if offer.shop_id != shop_id:
        return ClaimCheck("wrong_shop", claim, offer)
    if claim.status == "redeemed":
        return ClaimCheck("already_redeemed", claim, offer)
    if offer.status in ("ended", "sold_out") and claim.status != "redeemed":
        # sold_out: claims already issued still work until they expire (Plan 3 S6)
        if offer.status == "ended":
            return ClaimCheck("offer_ended", claim, offer)
    now = clock.now()
    if claim.status == "expired" or claim.expires_at <= now:
        return ClaimCheck("offer_ended" if offer.status == "ended" else "expired", claim, offer)
    return ClaimCheck("ok", claim, offer)


async def verify_claim(
    session: AsyncSession, payload: str | None, shop_id: uuid.UUID, *, short_code: str | None = None,
    lock: bool = True,
) -> ClaimCheck:
    """Verify QR text (or a short code) for a shop. Locks the claim row (SELECT … FOR UPDATE)."""
    if payload:
        text = payload.strip()
        if not text.startswith(QR_PREFIX):
            return ClaimCheck("invalid")
        try:
            claims: dict[str, Any] = jwt.decode(
                text[len(QR_PREFIX):],
                _private_key().public_key(),
                algorithms=["EdDSA"],
                options={"verify_exp": False, "require": ["jti", "oid", "sid", "exp"]},
            )
        except jwt.PyJWTError:
            return ClaimCheck("invalid")
        claim, offer = await _load(session, Claim.token_jti == claims["jti"], lock)
        if claim is None or offer is None:
            return ClaimCheck("invalid")
        if str(offer.id) != claims["oid"] or str(offer.shop_id) != claims["sid"]:
            return ClaimCheck("invalid")
        if datetime.fromtimestamp(claims["exp"], tz=timezone.utc) <= clock.now() and claim.status != "redeemed":
            if offer.shop_id != shop_id:
                return ClaimCheck("wrong_shop", claim, offer)
            return ClaimCheck("offer_ended" if offer.status == "ended" else "expired", claim, offer)
        return _evaluate(claim, offer, shop_id)
    if short_code:
        code = short_code.strip().upper().replace(" ", "")
        stmt = select(Claim).where(Claim.short_code == code)
        rows = (await session.execute(stmt)).scalars().all()
        if not rows:
            return ClaimCheck("invalid")
        # Prefer a claim at this shop; otherwise report wrong_shop.
        picked: tuple[Claim, Offer] | None = None
        other: tuple[Claim, Offer] | None = None
        for c in rows:
            o = await session.get(Offer, c.offer_id)
            if o is None:
                continue
            if o.shop_id == shop_id:
                if c.status == "issued" or picked is None:
                    picked = (c, o)
            else:
                other = (c, o)
        if picked is None:
            return ClaimCheck("wrong_shop", other[0], other[1]) if other else ClaimCheck("invalid")
        claim, offer = await _load(session, Claim.id == picked[0].id, lock)
        return _evaluate(claim, offer, shop_id)
    return ClaimCheck("invalid")
