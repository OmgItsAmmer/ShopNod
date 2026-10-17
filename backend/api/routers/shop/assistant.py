"""'Ask your shop': a small assistant on the dashboard that runs the same tools the MCP server exposes.

It works without an AI key (keyword intents), shows every tool it called, and can only *request* an approval:
the shopkeeper still confirms on the confirmation card, exactly as with an external MCP client.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shopnod_core import auth, shop_tools
from shopnod_core.db import DB
from shopnod_core.errors import AppError

router = APIRouter()


class AskIn(BaseModel):
    message: str = Field(min_length=1, max_length=300)


class ToolCallOut(BaseModel):
    tool: str
    args: dict[str, Any] = {}
    result: Any = None
    ok: bool = True


class AskOut(BaseModel):
    reply: str
    tool_calls: list[ToolCallOut]
    needs_confirmation: bool = False


HELP = "Try: “what's pending?”, “how busy are we?”, “what expires soon?”, “what are my limits?”, “approve it at 10%”, “reject it”."


@router.post("/assistant", response_model=AskOut)
async def ask(body: AskIn, su: auth.ShopUser = Depends(auth.shop_user_complete), db: AsyncSession = DB):
    shop = su.shop_required
    p = auth.Principal("user", shop.id, frozenset({auth.SCOPE_READ, auth.SCOPE_APPROVE}), su.user.id)
    q = body.message.lower()
    calls: list[ToolCallOut] = []

    async def use(name: str, *args: Any) -> Any:
        try:
            out = await getattr(shop_tools, name)(db, p, *args)
            calls.append(ToolCallOut(tool=name, args={"args": list(args)} if args else {}, result=out))
            return out
        except AppError as exc:
            calls.append(ToolCallOut(tool=name, args={"args": list(args)} if args else {}, result=exc.message, ok=False))
            raise

    async def first_pending() -> dict | None:
        rows = (await use("list_pending_proposals"))["proposals"]
        return next((r for r in rows if r["status"] == "pending"), None)

    try:
        if re.search(r"\b(approve|accept|yes|go ahead)\b", q):
            prop = await first_pending()
            if prop is None:
                return AskOut(reply="There is nothing waiting for you to approve.", tool_calls=calls)
            m = re.search(r"(\d{1,2})\s*%?", q)
            pct = int(m.group(1)) if m else None
            await use("approve_proposal", str(prop["id"]), pct)
            return AskOut(
                reply=f"Done on my side. I asked for approval at {pct or prop['proposed_pct']}%. Nothing is live until you tap Confirm on the confirmation card.",
                tool_calls=calls, needs_confirmation=True,
            )
        if re.search(r"\b(reject|decline|no|skip)\b", q):
            prop = await first_pending()
            if prop is None:
                return AskOut(reply="There is nothing waiting to reject.", tool_calls=calls)
            await use("reject_proposal", str(prop["id"]), "other", "from the assistant")
            return AskOut(reply="Rejected. I will remember that for next time.", tool_calls=calls)
        if re.search(r"pending|proposal|inbox|waiting|suggest", q):
            prop = await first_pending()
            if prop is None:
                return AskOut(reply="Nothing is waiting. ShopNod will propose an offer when it gets quiet.", tool_calls=calls)
            names = ", ".join(i.get("name", "item") for i in prop["items"])
            return AskOut(reply=f"{prop['proposed_pct']}% off {names}. {prop['reason']} Say “approve it” to confirm or “reject it”.", tool_calls=calls)
        if re.search(r"busy|quiet|activity|customers|sales|slow", q):
            a = await use("get_activity")
            usual = a.get("usual_for_this_hour")
            tail = f", usually {usual:g} at this time." if usual is not None else ". Not enough history yet for a usual number."
            return AskOut(reply=f"Redemptions in the last hour: {a['redemptions_last_60_min']}{tail}", tool_calls=calls)
        if re.search(r"expir|stock|waste|left", q):
            e = (await use("get_expiring_items"))["items"]
            if not e:
                return AskOut(reply="Nothing expires in the next 48 hours.", tool_calls=calls)
            return AskOut(reply="Expiring soon: " + "; ".join(f"{i['quantity']} × {i['name']} ({i['hours_left']}h left)" for i in e[:5]), tool_calls=calls)
        if re.search(r"limit|guardrail|rule|max|budget", q):
            g = await use("get_guardrails")
            return AskOut(reply=f"Never more than {g.get('max_discount_pct')}% off, at most {g.get('max_offers_per_day')} offers a day. The AI can read these but never change them.", tool_calls=calls)
    except AppError as exc:
        return AskOut(reply=exc.message, tool_calls=calls)
    return AskOut(reply=HELP, tool_calls=calls)
