"""FastAPI app: REST + SSE for the shopkeeper web app (and, in Plan 1, the shopper app)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shopnod_core import db
from shopnod_core.errors import error_body, install_error_handlers
from shopnod_core.logging_setup import RequestIdMiddleware, setup_logging
from shopnod_core.settings import get_settings

log = logging.getLogger("shopnod.api")
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def _allowed_origins() -> set[str]:
    s = get_settings()
    return {o.rstrip("/") for o in [*s.cors_origin_list, s.SHOP_WEB_URL, s.API_PUBLIC_URL]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.LOG_LEVEL)
    if s.SENTRY_DSN:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=s.SENTRY_DSN, environment=s.APP_ENV, traces_sample_rate=0.1)
        except ImportError:
            log.warning("SENTRY_DSN set but sentry-sdk is not installed")
    # In inline mode (no Redis) the API process also runs the outbox handlers and tasks.
    import shopnod_worker.tasks.ops  # noqa: F401
    import shopnod_worker.tasks.shop  # noqa: F401

    yield
    await db.dispose_engine()


def create_app() -> FastAPI:
    from shopnod_api.routers import health
    from shopnod_api.routers.admin import router as admin_router
    from shopnod_api.routers.auth import router as auth_router
    from shopnod_api.routers.shop import router as shop_router
    from shopnod_api.routers.webhooks import router as webhooks_router

    app = FastAPI(title="ShopNod API", version="0.1.0", lifespan=lifespan)
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)

    @app.middleware("http")
    async def origin_check(request: Request, call_next):
        """Cookie-authenticated unsafe requests must come from our own web app (CSRF defence in depth)."""
        origin = request.headers.get("origin")
        if request.method in UNSAFE and origin and request.cookies.get("sn_session") and origin.rstrip("/") not in _allowed_origins():
            return JSONResponse(
                error_body(getattr(request.state, "request_id", None), "forbidden", "That request came from an unknown site.", False),
                status_code=403,
            )
        return await call_next(request)

    app.include_router(health.router)
    app.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
    app.include_router(shop_router, prefix="/v1/shop", tags=["shop"])
    app.include_router(admin_router, prefix="/v1/admin", tags=["admin"])
    app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
    return app


app = create_app()
