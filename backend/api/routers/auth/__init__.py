import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_api.schemas import MagicLinkIn, MeOut, OkOut, ShopSummary, UserOut
from shopnod_core import auth, clock
from shopnod_core.db import DB
from shopnod_core.errors import AppError, ErrorCode
from shopnod_core.models import IdempotencyKey, User
from shopnod_core.redis_util import rate_limit
from shopnod_core.settings import get_settings

log = logging.getLogger("shopnod.auth")
router = APIRouter()


def _set_cookie(resp: Response, user_id) -> None:
    resp.set_cookie(auth.SESSION_COOKIE, auth.create_session_token(user_id), **auth.cookie_kwargs())


@router.post("/demo-login", response_model=MeOut)
async def demo_login(request: Request, response: Response, db: AsyncSession = DB):
    """Create a throwaway demo user + session cookie. Rate-limited."""
    s = get_settings()
    if not s.DEMO_MODE:
        raise AppError(ErrorCode.demo_only, "Demo login is turned off.", 403)
    ip = request.client.host if request.client else "unknown"
    if not await rate_limit(f"demo-login:{ip}", s.DEMO_LOGIN_PER_MINUTE, 60):
        raise AppError(ErrorCode.rate_limited, "Too many demo logins. Please wait a minute.", 429, True)
    user = User(is_demo=True, is_admin=True)  # demo users may use the admin/status page
    db.add(user)
    await db.flush()
    _set_cookie(response, user.id)
    return MeOut(user=UserOut.model_validate(user), shop=None)


async def _send_magic_email(email: str, link: str) -> None:
    s = get_settings()
    if not s.EMAIL_PROVIDER_KEY:
        log.info("MAGIC LINK (no EMAIL_PROVIDER_KEY set): %s -> %s", email, link)
        print(f"[magic-link] {email}: {link}", flush=True)
        return
    import httpx

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {s.EMAIL_PROVIDER_KEY}"},
            json={"from": "ShopNod <login@shopnod.app>", "to": [email], "subject": "Your ShopNod sign-in link",
                  "html": f'<p>Tap to sign in (valid for 15 minutes):</p><p><a href="{link}">Sign in to ShopNod</a></p>'},
        )
        r.raise_for_status()


@router.post("/magic-link", response_model=OkOut, status_code=202)
async def magic_link(body: MagicLinkIn, request: Request):
    s = get_settings()
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    if not await rate_limit(f"magic:{ip}", 10, 60) or not await rate_limit(f"magic-email:{email}", 5, 600):
        raise AppError(ErrorCode.rate_limited, "Too many sign-in requests. Please wait a bit.", 429, True)
    token, _ = auth.create_magic_token(email)
    link = f"{s.SHOP_WEB_URL.rstrip('/')}/api/v1/auth/magic-link/verify?token={token}"
    try:
        await _send_magic_email(email, link)
    except Exception:  # noqa: BLE001 - never reveal whether sending worked
        log.exception("could not send magic link")
    return OkOut()


@router.get("/magic-link/verify")
async def magic_link_verify(token: str = Query(min_length=10), db: AsyncSession = DB):
    data = auth.decode_magic_token(token)
    if data is None:
        return RedirectResponse("/login?error=link", status_code=303)
    # single use: the jti may be spent only once
    db.add(IdempotencyKey(scope="magic-link", key=data["jti"], status="done", expires_at=clock.now() + timedelta(hours=1)))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return RedirectResponse("/login?error=used", status_code=303)
    email = data["email"].lower()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, is_demo=False, is_admin=False)
        db.add(user)
        await db.flush()
    resp = RedirectResponse("/dashboard", status_code=303)
    _set_cookie(resp, user.id)
    return resp


@router.get("/me", response_model=MeOut)
async def me(su: auth.ShopUser = Depends(auth.shop_user)):
    return MeOut(
        user=UserOut.model_validate(su.user),
        shop=ShopSummary.model_validate(su.shop) if su.shop is not None else None,
    )


@router.post("/logout", response_model=OkOut)
async def logout(response: Response):
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return OkOut()
