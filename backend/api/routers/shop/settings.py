"""MCP tokens ("Connect your AI assistant") and shopkeeper Web Push subscriptions."""
from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import (
    OkOut,
    PushSubscriptionIn,
    PushUnsubscribeIn,
    TokenCreatedOut,
    TokenCreateIn,
    TokenOut,
)
from shopnod_core import audit, auth, clock
from shopnod_core.db import DB
from shopnod_core.errors import not_found
from shopnod_core.models import PersonalAccessToken, ShopPushSubscription
from shopnod_core.settings import get_settings

router = APIRouter()


def _token_out(t: PersonalAccessToken) -> dict:
    return dict(
        id=t.id, name=t.name, prefix=t.prefix, scopes=list(t.scopes or []), created_at=t.created_at,
        expires_at=t.expires_at, last_used_at=t.last_used_at, revoked=t.revoked_at is not None,
    )


@router.get("/tokens", response_model=list[TokenOut])
async def list_tokens(su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    rows = (
        await db.execute(select(PersonalAccessToken).where(PersonalAccessToken.shop_id == su.shop_required.id).order_by(PersonalAccessToken.created_at.desc(), PersonalAccessToken.id.desc()))
    ).scalars().all()
    return [TokenOut(**_token_out(t)) for t in rows]


@router.post("/tokens", response_model=TokenCreatedOut, status_code=201)
async def create_token(body: TokenCreateIn, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    """The token is shown ONCE; only its hash is stored."""
    shop = su.shop_required
    raw, hashed, prefix = auth.new_pat()
    scopes = sorted(set(body.scopes) | {auth.SCOPE_READ})  # approving implies reading
    t = PersonalAccessToken(
        shop_id=shop.id, user_id=su.user.id, name=body.name.strip(), token_hash=hashed, prefix=prefix, scopes=scopes,
        expires_at=clock.now() + timedelta(days=body.expires_in_days) if body.expires_in_days else None,
    )
    db.add(t)
    await db.flush()
    await audit.record(db, shop_id=shop.id, action="token.created", actor_user_id=su.user.id, entity_type="token", entity_id=t.id, channel="dashboard", data={"name": t.name, "scopes": scopes})
    cfg = {"mcpServers": {"shopnod": {"type": "http", "url": f"{get_settings().MCP_PUBLIC_URL.rstrip('/')}/mcp", "headers": {"Authorization": f"Bearer {raw}"}}}}
    return TokenCreatedOut(**_token_out(t), token=raw, mcp_config=cfg)


@router.delete("/tokens/{token_id}", response_model=OkOut)
async def revoke_token(token_id: uuid.UUID, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    shop = su.shop_required
    t = await db.get(PersonalAccessToken, token_id)
    if t is None or t.shop_id != shop.id:
        raise not_found("That token")
    if t.revoked_at is None:
        t.revoked_at = clock.now()
        await audit.record(db, shop_id=shop.id, action="token.revoked", actor_user_id=su.user.id, entity_type="token", entity_id=t.id, channel="dashboard")
    return OkOut()


@router.post("/push-subscriptions", response_model=OkOut, status_code=201)
async def subscribe_push(body: PushSubscriptionIn, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    shop = su.shop_required
    existing = (await db.execute(select(ShopPushSubscription).where(ShopPushSubscription.endpoint == body.endpoint))).scalar_one_or_none()
    if existing is None:
        db.add(ShopPushSubscription(user_id=su.user.id, shop_id=shop.id, endpoint=body.endpoint, p256dh=body.p256dh, auth=body.auth))
    else:
        existing.user_id, existing.shop_id, existing.p256dh, existing.auth = su.user.id, shop.id, body.p256dh, body.auth
    return OkOut()


@router.delete("/push-subscriptions", response_model=OkOut)
async def unsubscribe_push(body: PushUnsubscribeIn, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    await db.execute(delete(ShopPushSubscription).where(ShopPushSubscription.endpoint == body.endpoint, ShopPushSubscription.shop_id == su.shop_required.id))
    return OkOut()


@router.get("/push-config")
async def push_config(_: auth.ShopUser = Depends(auth.shop_user)) -> dict:
    s = get_settings()
    return {"vapid_public_key": s.VAPID_PUBLIC_KEY or None, "enabled": bool(s.VAPID_PUBLIC_KEY and s.VAPID_PRIVATE_KEY)}


_ = Response
