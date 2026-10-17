"""One error shape and one code enum for every API response."""
from __future__ import annotations

import enum
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("shopnod.errors")


class ErrorCode(str, enum.Enum):
    unauthorized = "unauthorized"
    forbidden = "forbidden"
    not_found = "not_found"
    validation_error = "validation_error"
    idempotency_key_required = "idempotency_key_required"
    request_in_progress = "request_in_progress"
    rate_limited = "rate_limited"
    internal_error = "internal_error"
    guardrail_violation = "guardrail_violation"
    proposal_not_pending = "proposal_not_pending"
    proposal_expired = "proposal_expired"
    confirmation_expired = "confirmation_expired"
    confirmation_not_awaiting = "confirmation_not_awaiting"
    onboarding_incomplete = "onboarding_incomplete"
    offer_ended = "offer_ended"
    offer_sold_out = "offer_sold_out"
    offer_not_active = "offer_not_active"
    claim_invalid = "claim_invalid"
    claim_expired = "claim_expired"
    wrong_shop = "wrong_shop"
    already_redeemed = "already_redeemed"
    scope_missing = "scope_missing"
    demo_only = "demo_only"
    conflict = "conflict"
    consent_required = "consent_required"
    age_required = "age_required"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        self.details = details or {}


def not_found(what: str = "That") -> AppError:
    return AppError(ErrorCode.not_found, f"{what} was not found.", 404)


def forbidden(msg: str = "You can't do that.") -> AppError:
    return AppError(ErrorCode.forbidden, msg, 403)


def unauthorized(msg: str = "Please sign in.") -> AppError:
    return AppError(ErrorCode.unauthorized, msg, 401)


def error_body(
    request_id: str | None, code: str, message: str, retryable: bool, details: dict | None = None
) -> dict:
    err: dict[str, Any] = {"code": code, "message": message, "retryable": retryable, "request_id": request_id}
    if details:
        err["details"] = details
    return {"error": err}


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            error_body(_rid(request), exc.code.value, exc.message, exc.retryable, exc.details),
            status_code=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = [{"loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg", "")} for e in exc.errors()]
        return JSONResponse(
            error_body(_rid(request), "validation_error", "Some fields look wrong.", False, {"fields": fields}),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 429: "rate_limited"}.get(
            exc.status_code, "internal_error" if exc.status_code >= 500 else "validation_error"
        )
        return JSONResponse(
            error_body(_rid(request), code, str(exc.detail), exc.status_code >= 500),
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"request_id": _rid(request)})
        return JSONResponse(
            error_body(_rid(request), "internal_error", "Something went wrong on our side. Please try again.", True),
            status_code=500,
        )
