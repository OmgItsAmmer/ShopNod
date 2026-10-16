"""Feature flags stored in Postgres: `ai_outage`, `sim_enabled` (see Plan 2 Phase 7)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from . import clock
from .db import get_maker
from .models import FeatureFlag

AI_OUTAGE = "ai_outage"
SIM_ENABLED = "sim_enabled"


async def get_flag(key: str, session: AsyncSession | None = None) -> bool:
    if session is not None:
        row = await session.get(FeatureFlag, key)
        return bool(row and row.enabled)
    async with get_maker()() as s:
        row = await s.get(FeatureFlag, key)
        return bool(row and row.enabled)


async def set_flag(session: AsyncSession, key: str, enabled: bool) -> None:
    row = await session.get(FeatureFlag, key)
    if row is None:
        session.add(FeatureFlag(key=key, enabled=enabled, updated_at=clock.now()))
    else:
        row.enabled = enabled
        row.updated_at = clock.now()
    await session.flush()
