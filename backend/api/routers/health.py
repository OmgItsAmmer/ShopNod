from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from shopnod_core.db import get_maker
from shopnod_core.redis_util import get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """Process is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """DB and Redis (when configured) are reachable."""
    checks: dict[str, str] = {}
    ok = True
    try:
        async with get_maker()() as s:
            await s.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        ok, checks["database"] = False, f"error: {type(exc).__name__}"
    r = get_redis()
    if r is None:
        checks["redis"] = "not configured"
    else:
        try:
            await r.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            ok, checks["redis"] = False, f"error: {type(exc).__name__}"
    return JSONResponse({"status": "ready" if ok else "unavailable", "checks": checks}, status_code=200 if ok else 503)
