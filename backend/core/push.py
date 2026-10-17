"""Push senders: Web Push (VAPID) for the shopkeeper PWA and the shopper web app, FCM for the Flutter mobile app."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from .breaker import get_breaker
from .settings import get_settings

log = logging.getLogger("shopnod.push")
EXPO_URL = "https://exp.host/--/api/v2/push/send"


class PushUnavailable(Exception):
    """Push is not configured. Callers treat this as 'skipped', not as an error to retry."""


class SubscriptionGone(Exception):
    """The browser subscription expired (HTTP 404/410): remove it."""


def webpush_configured() -> bool:
    s = get_settings()
    return bool(s.VAPID_PRIVATE_KEY and s.VAPID_PUBLIC_KEY)


async def send_webpush(endpoint: str, p256dh: str, auth: str, payload: dict[str, Any], ttl: int = 3600) -> None:
    s = get_settings()
    if not webpush_configured():
        raise PushUnavailable("VAPID keys not set")
    breaker = get_breaker("push")
    if not breaker.allow():
        raise RuntimeError("push circuit open")

    def _send() -> None:
        from pywebpush import WebPushException, webpush

        try:
            webpush(
                subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                data=json.dumps(payload),
                vapid_private_key=s.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": s.VAPID_SUBJECT},
                ttl=ttl,
                timeout=10,
            )
        except WebPushException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code in (404, 410):
                raise SubscriptionGone(endpoint) from exc
            raise

    try:
        await asyncio.to_thread(_send)
    except SubscriptionGone:
        raise
    except Exception:
        breaker.record_failure()
        raise
    breaker.record_success()


async def send_expo(tokens: list[str], title: str, body: str, data: dict[str, Any] | None = None) -> None:
    s = get_settings()
    breaker = get_breaker("push")
    if not breaker.allow():
        raise RuntimeError("push circuit open")
    headers = {"Accept": "application/json"}
    if s.EXPO_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {s.EXPO_ACCESS_TOKEN}"
    msgs = [{"to": t, "title": title, "body": body, "data": data or {}} for t in tokens]
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(EXPO_URL, json=msgs, headers=headers)
            r.raise_for_status()
    except Exception:
        breaker.record_failure()
        raise
    breaker.record_success()


def fcm_configured() -> bool:
    return bool(get_settings().FIREBASE_CREDENTIALS)


class TokenGone(Exception):
    """The FCM registration token is no longer valid: remove it."""


_fcm_app = None


async def send_fcm(token: str, title: str, body: str, data: dict[str, str] | None = None) -> None:
    """One FCM message to the Flutter app. Needs FIREBASE_CREDENTIALS and the optional `firebase-admin` package."""
    if not fcm_configured():
        raise PushUnavailable("FIREBASE_CREDENTIALS not set")
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError as exc:
        raise PushUnavailable("firebase-admin is not installed (pip install '.[push]')") from exc
    breaker = get_breaker("push")
    if not breaker.allow():
        raise RuntimeError("push circuit open")
    global _fcm_app
    if _fcm_app is None:
        import base64

        info = json.loads(base64.b64decode(get_settings().FIREBASE_CREDENTIALS))
        _fcm_app = firebase_admin.initialize_app(credentials.Certificate(info), name="shopnod")

    def _send() -> None:
        msg = messaging.Message(token=token, notification=messaging.Notification(title=title, body=body), data=data or {})
        try:
            messaging.send(msg, app=_fcm_app)
        except (messaging.UnregisteredError, messaging.SenderIdMismatchError) as exc:
            raise TokenGone(token) from exc

    try:
        await asyncio.to_thread(_send)
    except TokenGone:
        raise
    except Exception:
        breaker.record_failure()
        raise
    breaker.record_success()
