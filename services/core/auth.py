"""Authentication: shopkeeper session cookie, personal access tokens (PAT) and per-run agent tokens."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .db import get_maker
from .errors import AppError, ErrorCode, forbidden, unauthorized
from .models import PersonalAccessToken, Shop, User
from .settings import get_settings

SESSION_COOKIE = "sn_session"
SCOPE_AGENT_PROPOSE = "agent:propose"
SCOPE_READ = "shopkeeper:read"
SCOPE_APPROVE = "shopkeeper:approve"
USER_SCOPES = (SCOPE_READ, SCOPE_APPROVE)
PAT_PREFIX = "snpat_"
AGENT_TOKEN_TTL = timedelta(minutes=5)


# ── Session JWT (cookie) ─────────────────────────────────────────────────
def create_session_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    now = clock.now()
    return jwt.encode(
        {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=s.SESSION_TTL_HOURS)).timestamp()), "typ": "session"},
        s.JWT_SIGNING_KEY,
        algorithm="HS256",
    )


def decode_session_token(token: str) -> uuid.UUID | None:
    try:
        data = jwt.decode(token, get_settings().JWT_SIGNING_KEY, algorithms=["HS256"], options={"verify_exp": False})
    except jwt.PyJWTError:
        return None
    if data.get("typ") != "session":
        return None
    if data.get("exp", 0) <= int(clock.now().timestamp()):
        return None
    try:
        return uuid.UUID(data["sub"])
    except (KeyError, ValueError):
        return None


def cookie_kwargs() -> dict:
    s = get_settings()
    return {
        "httponly": True,
        "secure": s.is_prod,
        "samesite": "lax",
        "path": "/",
        "max_age": s.SESSION_TTL_HOURS * 3600,
    }


def create_magic_token(email: str) -> tuple[str, str]:
    s = get_settings()
    now = clock.now()
    jti = secrets.token_hex(12)
    tok = jwt.encode(
        {"email": email, "jti": jti, "typ": "magic", "exp": int((now + timedelta(minutes=15)).timestamp())},
        s.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    return tok, jti


def decode_magic_token(token: str) -> dict | None:
    try:
        data = jwt.decode(token, get_settings().JWT_SIGNING_KEY, algorithms=["HS256"], options={"verify_exp": False})
    except jwt.PyJWTError:
        return None
    if data.get("typ") != "magic" or data.get("exp", 0) <= int(clock.now().timestamp()):
        return None
    return data


# ── Personal access tokens ───────────────────────────────────────────────
def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_pat() -> tuple[str, str, str]:
    """(raw token shown once, sha256 hash, display prefix)"""
    raw = PAT_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_token(raw), raw[:12]


def create_agent_token(shop_id: uuid.UUID, run_id: str | None = None) -> str:
    """Fresh per run, tied to one shop, scope agent:propose only, 5 minutes."""
    s = get_settings()
    now = clock.now()
    return jwt.encode(
        {
            "typ": "agent",
            "sid": str(shop_id),
            "scopes": [SCOPE_AGENT_PROPOSE],
            "run": run_id,
            "iat": int(now.timestamp()),
            "exp": int((now + AGENT_TOKEN_TTL).timestamp()),
        },
        s.MCP_AGENT_TOKEN_SECRET,
        algorithm="HS256",
    )


@dataclass
class Principal:
    """Who is calling MCP / an API route, and what they may do."""

    kind: str  # user|pat|agent
    shop_id: uuid.UUID
    scopes: frozenset[str]
    user_id: uuid.UUID | None = None
    token_id: uuid.UUID | None = None
    extra: dict = field(default_factory=dict)

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise AppError(ErrorCode.scope_missing, f"This token is missing the '{scope}' permission.", 403)


async def principal_from_bearer(session: AsyncSession, raw: str) -> Principal:
    """Resolve an `Authorization: Bearer` value for the MCP server."""
    raw = raw.strip()
    if raw.startswith(PAT_PREFIX):
        row = (
            await session.execute(select(PersonalAccessToken).where(PersonalAccessToken.token_hash == hash_token(raw)))
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None or (row.expires_at and row.expires_at <= clock.now()):
            raise unauthorized("That token is not valid.")
        row.last_used_at = clock.now()
        await session.flush()
        return Principal("pat", row.shop_id, frozenset(row.scopes), row.user_id, row.id)
    try:
        data = jwt.decode(raw, get_settings().MCP_AGENT_TOKEN_SECRET, algorithms=["HS256"], options={"verify_exp": False})
    except jwt.PyJWTError:
        raise unauthorized("That token is not valid.") from None
    if data.get("typ") != "agent" or data.get("exp", 0) <= int(clock.now().timestamp()):
        raise unauthorized("That token is not valid.")
    return Principal("agent", uuid.UUID(data["sid"]), frozenset(data.get("scopes", [])), extra={"run": data.get("run")})


# ── FastAPI dependencies for the shopkeeper browser app ─────────────────
@dataclass
class ShopUser:
    user: User
    shop: Shop | None

    @property
    def shop_required(self) -> Shop:
        if self.shop is None:
            raise AppError(ErrorCode.onboarding_incomplete, "Set up your shop first.", 409)
        return self.shop


async def _load_user(request: Request) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise unauthorized()
    uid = decode_session_token(token)
    if uid is None:
        raise unauthorized("Your session has ended. Please sign in again.")
    async with get_maker()() as s:
        user = await s.get(User, uid)
    if user is None:
        raise unauthorized()
    return user


async def shop_user(request: Request) -> ShopUser:
    """The signed-in shopkeeper and their shop (shop may be None before onboarding)."""
    user = await _load_user(request)
    async with get_maker()() as s:
        shop = (
            await s.execute(select(Shop).where(Shop.owner_id == user.id).order_by(Shop.created_at.desc()))
        ).scalars().first()
    request.state.user_id = user.id
    return ShopUser(user, shop)


async def shop_user_complete(su: ShopUser = Depends(shop_user)) -> ShopUser:
    """Signed in AND the shop finished onboarding."""
    shop = su.shop_required
    if shop.onboarding_status != "complete":
        raise AppError(ErrorCode.onboarding_incomplete, "Finish setting up your shop first.", 409)
    return su


async def admin_user(su: ShopUser = Depends(shop_user)) -> ShopUser:
    if not su.user.is_admin:
        raise forbidden("Admins only.")
    return su
