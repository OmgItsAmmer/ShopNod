"""Idempotency-Key handling. Required on approve, confirm, claim, redeem and end-offer.
The result is stored for 24 h; a repeat with the same key gets the saved result."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Awaitable, Callable

from fastapi import Header
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .db import get_maker
from .errors import AppError, ErrorCode
from .models import IdempotencyKey

TTL = timedelta(hours=24)


def require_key(idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise AppError(
            ErrorCode.idempotency_key_required,
            "This action needs an Idempotency-Key header so a double click can't repeat it.",
            400,
        )
    return idempotency_key.strip()[:200]


async def run_idempotent(
    scope: str,
    key: str,
    fn: Callable[[], Awaitable[tuple[int, dict[str, Any]]]],
) -> tuple[int, dict[str, Any]]:
    """Run `fn` once per (scope, key). `fn` returns (status, json body).

    The key row is reserved in its own transaction first, so concurrent duplicates see
    `in_progress` (409) instead of racing. Failed attempts release the key so the caller can retry.
    """
    maker = get_maker()
    async with maker() as s:
        existing = (
            await s.execute(select(IdempotencyKey).where(IdempotencyKey.scope == scope, IdempotencyKey.key == key))
        ).scalar_one_or_none()
        if existing is not None and existing.expires_at <= clock.now():
            await s.delete(existing)
            await s.commit()
            existing = None
        if existing is not None:
            if existing.status == "done":
                return existing.response_status or 200, existing.response_body or {}
            raise AppError(ErrorCode.request_in_progress, "That request is already being processed.", 409, True)
        s.add(IdempotencyKey(scope=scope, key=key, status="in_progress", expires_at=clock.now() + TTL))
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            raise AppError(ErrorCode.request_in_progress, "That request is already being processed.", 409, True)

    async def _release() -> None:
        async with maker() as s2:
            row = (
                await s2.execute(select(IdempotencyKey).where(IdempotencyKey.scope == scope, IdempotencyKey.key == key))
            ).scalar_one_or_none()
            if row is not None and row.status == "in_progress":
                await s2.delete(row)
                await s2.commit()

    try:
        status, body = await fn()
    except AppError as exc:
        # Deterministic refusals (422 guardrail etc.) are not saved; the caller may fix and retry.
        await _release()
        raise exc
    except BaseException:
        await _release()
        raise

    async with maker() as s3:
        row = (
            await s3.execute(select(IdempotencyKey).where(IdempotencyKey.scope == scope, IdempotencyKey.key == key))
        ).scalar_one()
        row.status = "done"
        row.response_status = status
        row.response_body = body
        await s3.commit()
    return status, body


async def purge_expired(session: AsyncSession) -> int:
    rows = (await session.execute(select(IdempotencyKey).where(IdempotencyKey.expires_at <= clock.now()))).scalars().all()
    for r in rows:
        await session.delete(r)
    return len(rows)
