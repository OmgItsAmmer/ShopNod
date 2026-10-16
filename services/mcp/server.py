"""ShopNod MCP server (Streamable HTTP at /mcp). The tool layer for the Shop Agent AND the shopkeeper's own assistant.

It reads and writes the database directly through shopnod_core (it does not call the API over HTTP).
Auth: `Authorization: Bearer <token>`. A personal access token (`snpat_…`, scopes shopkeeper:read / :approve) or a
per-run agent token (scope agent:propose only, tied to one shop, 5 minutes). Every tool checks the scope and the shop.
There is NO tool that publishes an offer: `approve_proposal` only asks the shopkeeper to confirm in the dashboard.
"""
from __future__ import annotations

import logging
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from shopnod_core import auth, shop_tools
from shopnod_core.db import session_scope
from shopnod_core.errors import AppError
from shopnod_core.logging_setup import setup_logging
from shopnod_core.settings import get_settings

log = logging.getLogger("shopnod.mcp")

INSTRUCTIONS = (
    "ShopNod lets a local shop review and approve discount offers. You can read the shop's status and pending "
    "proposals. Approving a proposal never publishes by itself: the shopkeeper must confirm it in the ShopNod dashboard."
)

mcp = MCPServer("ShopNod", instructions=INSTRUCTIONS)


async def _principal(ctx: Context, session) -> auth.Principal:
    raw = ""
    try:
        raw = ctx.headers.get("authorization", "") if ctx.headers else ""
    except Exception:  # noqa: BLE001
        raw = ""
    if not raw.lower().startswith("bearer "):
        raise ValueError("unauthorized: send 'Authorization: Bearer <token>'.")
    try:
        return await auth.principal_from_bearer(session, raw[7:])
    except AppError as exc:
        raise ValueError(f"{exc.code.value}: {exc.message}") from None


async def _run(ctx: Context, fn, *args, **kwargs) -> Any:
    """Resolve the caller, run a tool function in a transaction, and turn AppErrors into readable tool errors."""
    try:
        async with session_scope() as s:
            p = await _principal(ctx, s)
            return await fn(s, p, *args, **kwargs)
    except AppError as exc:
        details = f" ({exc.details})" if exc.details else ""
        raise ValueError(f"{exc.code.value}: {exc.message}{details}") from None


@mcp.tool()
async def get_shop_profile(ctx: Context) -> dict:
    """The shop's profile: name, category, hours, languages, time zone and currency."""
    return await _run(ctx, shop_tools.get_shop_profile)


@mcp.tool()
async def get_guardrails(ctx: Context) -> dict:
    """The limits every offer must respect (read-only): max discount %, minimum price, budgets, allowed hours."""
    return await _run(ctx, shop_tools.get_guardrails)


@mcp.tool()
async def get_activity(ctx: Context, window_minutes: int = 60) -> dict:
    """Recent redemptions versus the usual number for this weekday and hour, plus recent quiet signals."""
    return await _run(ctx, shop_tools.get_activity, window_minutes)


@mcp.tool()
async def get_expiring_items(ctx: Context) -> dict:
    """Items that expire within 48 hours, with quantity left."""
    return await _run(ctx, shop_tools.get_expiring_items)


@mcp.tool()
async def list_items(ctx: Context) -> list:
    """The shop's active items (ids are needed for submit_proposal)."""
    return await _run(ctx, shop_tools.list_items)


@mcp.tool()
async def get_decision_history(ctx: Context) -> dict:
    """Past proposals and what the shopkeeper did, plus the learned discount % per category. Agents only."""
    return await _run(ctx, shop_tools.get_decision_history)


@mcp.tool()
async def submit_proposal(ctx: Context, item_ids: list[str], pct: int, window_start: str, window_end: str, cap: int, reason: str) -> dict:
    """Create a PENDING proposal for the shopkeeper to review. It is validated and clamped to the guardrails.
    This cannot publish anything. Times are ISO 8601 (UTC). Agents only."""
    return await _run(ctx, shop_tools.submit_proposal, item_ids, pct, window_start, window_end, cap, reason)


@mcp.tool()
async def list_pending_proposals(ctx: Context) -> dict:
    """The shopkeeper's inbox: proposals waiting for a decision."""
    return await _run(ctx, shop_tools.list_pending_proposals)


@mcp.tool()
async def approve_proposal(
    ctx: Context, proposal_id: str, final_pct: int | None = None, window_start: str | None = None,
    window_end: str | None = None, cap: int | None = None,
) -> dict:
    """Ask to approve a proposal (optionally with an edited %, time or cap). The offer is NOT published yet:
    the shopkeeper gets a confirmation card in the ShopNod dashboard and must confirm there."""
    return await _run(ctx, shop_tools.approve_proposal, proposal_id, final_pct, window_start, window_end, cap)


@mcp.tool()
async def reject_proposal(ctx: Context, proposal_id: str, reason: str, note: str | None = None) -> dict:
    """Reject a proposal. reason is one of: wrong_items, wrong_time, too_generous, other."""
    return await _run(ctx, shop_tools.reject_proposal, proposal_id, reason, note)


@mcp.tool()
async def get_offer_stats(ctx: Context, offer_id: str) -> dict:
    """Results for one offer: claims, redemptions, discount given (audience numbers appear only when 10 or more)."""
    return await _run(ctx, shop_tools.get_offer_stats, offer_id)


@mcp.tool()
async def get_confirmation_status(ctx: Context, confirmation_id: str) -> dict:
    """Whether the shopkeeper has confirmed an approval you requested (awaiting, confirmed, declined, expired)."""
    return await _run(ctx, shop_tools.get_confirmation_status, confirmation_id)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/readyz", methods=["GET"])
async def readyz(_: Request) -> JSONResponse:
    from sqlalchemy import text

    from shopnod_core.db import get_maker

    try:
        async with get_maker()() as s:
            await s.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "unavailable", "error": type(exc).__name__}, status_code=503)
    return JSONResponse({"status": "ready"})


def create_app():
    setup_logging(get_settings().LOG_LEVEL)
    # Bearer-token auth protects the endpoint; the platform's public hostnames are not known up front,
    # so DNS-rebinding host checks are off (they only matter for unauthenticated localhost servers).
    return mcp.streamable_http_app(
        stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


app = create_app()
