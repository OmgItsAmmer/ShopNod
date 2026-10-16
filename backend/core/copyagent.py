"""Copy Agent: short offer text in each of the shop's languages, using ONLY facts from the data.

A banned-phrase check runs on the output (no fake urgency like "only 2 left!").
If anything is off, the template text is used (Plan 2 Phase 4).
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from . import ai
from .agents.openai_runner import run_openai_agent
from .settings import get_settings

log = logging.getLogger("shopnod.copy")

BANNED_PATTERNS = [
    r"\bonly\s+\d+\s+(left|remaining)\b",
    r"\blast\s+(chance|few|ones?)\b",
    r"\bhurry\b",
    r"\bact\s+now\b",
    r"\bdon'?t\s+miss\b",
    r"\bwhile\s+(stocks?|supplies)\s+last\b",
    r"\bselling\s+fast\b",
    r"\bnever\s+again\b",
    r"\bbest\s+price\b",
    r"\bcheapest\b",
    r"\bfree\b",
    r"\bguarantee",
    r"\blimited\s+(time|stock|supply)\b",
    r"\bexclusive\b",
    r"\bgoing\s+fast\b",
    r"\bwon'?t\s+last\b",
    r"\bnow\s+or\s+never\b",
]
_BANNED_RE = re.compile("|".join(BANNED_PATTERNS), re.IGNORECASE)

TEMPLATES = {
    "en": "{pct}% off {items} at {shop}, {start}–{end}.",
    "ur": "{shop} پر {items} پر {pct}% رعایت، {start}–{end}۔",
    "ar": "خصم {pct}% على {items} في {shop}، {start}–{end}.",
    "es": "{pct}% de descuento en {items} en {shop}, {start}–{end}.",
}


class CopyOutput(BaseModel):
    texts: dict[str, str]


def has_banned_phrase(text: str) -> bool:
    return bool(_BANNED_RE.search(text))


def fmt_money(minor: int, currency: str) -> str:
    return f"{minor / 100:.2f} {currency}"


def _fmt_time(dt: datetime, tz: str) -> str:
    try:
        z = ZoneInfo(tz)
    except Exception:  # noqa: BLE001
        z = ZoneInfo("UTC")
    return dt.astimezone(z).strftime("%H:%M")


def facts_for(shop_name: str, items: list[dict], pct: int, start: datetime, end: datetime, tz: str, currency: str) -> dict:
    return {
        "shop": shop_name,
        "pct": pct,
        "items": [
            {"name": i["name"], "was": fmt_money(i["was_minor"], currency), "now": fmt_money(i["new_price_minor"], currency)}
            for i in items
        ],
        "start": _fmt_time(start, tz),
        "end": _fmt_time(end, tz),
    }


def template_copy(facts: dict, languages: list[str]) -> dict[str, str]:
    names = ", ".join(i["name"] for i in facts["items"])
    out = {}
    for lang in languages or ["en"]:
        t = TEMPLATES.get(lang, TEMPLATES["en"])
        out[lang] = t.format(pct=facts["pct"], items=names, shop=facts["shop"], start=facts["start"], end=facts["end"])
    return out


def _allowed_numbers(facts: dict) -> set[str]:
    nums: set[str] = {str(facts["pct"])}
    for token in re.findall(r"\d+(?:[.:]\d+)?", " ".join(
        [facts["start"], facts["end"]] + [f'{i["was"]} {i["now"]}' for i in facts["items"]]
    )):
        nums.add(token)
        for part in re.split(r"[.:]", token):
            nums.add(part)
            nums.add(part.lstrip("0") or "0")
    return nums


def check_copy(texts: dict[str, str], facts: dict, languages: list[str]) -> bool:
    """True if the AI text is acceptable: all languages present, no banned phrases, only known numbers."""
    allowed = _allowed_numbers(facts)
    for lang in languages:
        t = (texts.get(lang) or "").strip()
        if not t or len(t) > 300 or has_banned_phrase(t):
            return False
        for num in re.findall(r"\d+(?:[.:]\d+)?", t):
            if num not in allowed and num.split(".")[0] not in allowed:
                return False
    return True


COPY_INSTRUCTIONS = (
    "You write very short (max 2 sentences) shop offer text for a notification. "
    "Use ONLY the facts provided: shop name, item names, discount percent, prices and times. "
    "Never invent urgency, scarcity, quality claims or any number that is not in the facts. "
    "Write one text per requested language code, in that language."
)


async def generate_copy(
    *,
    shop_id: uuid.UUID,
    facts: dict,
    languages: list[str],
    timeout_s: float | None = None,
) -> tuple[dict[str, str], str]:
    """Returns (texts by language, source) where source is 'ai' or 'template'."""
    settings = get_settings()
    languages = languages or ["en"]

    async def runner(trace: ai.RunTrace):
        return await run_openai_agent(
            trace,
            name="CopyAgent",
            instructions=COPY_INSTRUCTIONS,
            user_input=f"Languages: {languages}\nFacts: {facts}",
            output_type=CopyOutput,
            model=settings.OPENAI_MODEL_FAST,
            max_tool_calls=0,
        )

    template = template_copy(facts, languages)
    result = await ai.run_structured(
        "copy",
        f"offer copy for {facts['shop']} ({', '.join(languages)})",
        CopyOutput,
        runner=runner,
        fallback=lambda: CopyOutput(texts=template),
        timeout_s=timeout_s if timeout_s is not None else settings.COPY_TIMEOUT_S,
        shop_id=shop_id,
    )
    if result.fallback_used:
        return template, "template"
    if not check_copy(result.output.texts, facts, languages):
        log.info("copy rejected by banned-phrase/fact check; using template")
        return template, "template"
    return {lang: result.output.texts[lang].strip() for lang in languages}, "ai"
