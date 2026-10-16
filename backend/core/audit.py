"""Audit log helper. Every approval (and its channel) and every guardrail change goes here."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .jsonutil import jsonable
from .models import AuditLog


async def record(
    session: AsyncSession,
    *,
    shop_id: uuid.UUID | None,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    actor_kind: str = "user",
    entity_type: str | None = None,
    entity_id: Any = None,
    channel: str | None = None,
    data: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        shop_id=shop_id,
        actor_user_id=actor_user_id,
        actor_kind=actor_kind,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        channel=channel,
        data=jsonable(data or {}),
    )
    session.add(row)
    await session.flush()
    return row
