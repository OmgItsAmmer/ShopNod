"""Shared AI wrapper (Plan 3 §0.9).

`run_structured` always saves an `agent_runs` row and never lets an AI failure stop the loop:
  1. `ai_outage` flag on, circuit breaker open, or no runner/API key  -> fallback right away
  2. otherwise run the agent with a timeout; if the output does not match the schema, retry once
  3. on any failure -> fallback
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from . import clock, flags
from .breaker import get_breaker
from .db import get_maker
from .ids import uuid7
from .models import AgentRun
from .settings import get_settings

log = logging.getLogger("shopnod.ai")
T = TypeVar("T", bound=BaseModel)


@dataclass
class RunTrace:
    """Handed to the runner so it can record tool calls, tokens and cost."""

    run_id: uuid.UUID
    shop_id: uuid.UUID | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0
    cost_micro_usd: int = 0

    def tool(self, name: str, args: dict[str, Any] | None = None, result: Any = None, ok: bool = True) -> None:
        self.tool_calls.append({"tool": name, "args": args or {}, "ok": ok, "result": _short(result)})


def _short(v: Any, n: int = 400) -> Any:
    s = str(v)
    return s if len(s) <= n else s[:n] + "…"


@dataclass
class AIResult(Generic[T]):
    output: T
    fallback_used: bool
    run_id: uuid.UUID
    reason: str | None = None  # why the fallback was used


Runner = Callable[[RunTrace], Awaitable[Any]]
Fallback = Callable[[], Awaitable[T] | T]


async def _call_fallback(fallback: Fallback):
    r = fallback()
    if asyncio.iscoroutine(r):
        r = await r
    return r


async def run_structured(
    agent: str,
    input_summary: str,
    schema: type[T],
    *,
    runner: Runner | None,
    fallback: Fallback,
    timeout_s: float | None = None,
    shop_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    require_key: bool = True,
) -> AIResult[T]:
    settings = get_settings()
    timeout_s = timeout_s if timeout_s is not None else settings.AGENT_TIMEOUT_S
    run_id = run_id or uuid7()
    trace = RunTrace(run_id=run_id, shop_id=shop_id)
    breaker = get_breaker("openai")
    started = time.perf_counter()

    maker = get_maker()
    async with maker() as s:  # row exists up-front so proposals can reference it while the agent runs
        s.add(AgentRun(id=run_id, agent=agent, shop_id=shop_id, input_summary=input_summary, created_at=clock.now()))
        await s.commit()

    reason: str | None = None
    output: T | None = None
    error: str | None = None

    if await flags.get_flag(flags.AI_OUTAGE):
        reason = "ai_outage_flag"
    elif not breaker.allow():
        reason = "circuit_open"
    elif runner is None or (require_key and not settings.OPENAI_API_KEY):
        reason = "no_ai_configured"
    else:
        for attempt in (1, 2):
            try:
                raw = await asyncio.wait_for(runner(trace), timeout=timeout_s)
                output = raw if isinstance(raw, schema) else schema.model_validate(raw)
                breaker.record_success()
                break
            except ValidationError as exc:
                error = f"schema mismatch: {exc.errors()[:2]}"
                trace.tool("schema_validation", ok=False, result=error)
                if attempt == 2:
                    reason = "invalid_output"
                    breaker.record_failure()
            except asyncio.TimeoutError:
                reason, error = "timeout", f"timeout after {timeout_s}s"
                breaker.record_failure()
                break
            except Exception as exc:  # noqa: BLE001
                reason, error = "error", f"{type(exc).__name__}: {exc}"
                breaker.record_failure()
                break

    fallback_used = output is None
    if fallback_used:
        try:
            output = await _call_fallback(fallback)
        except Exception as exc:  # noqa: BLE001
            error = (error or "") + f" | fallback failed: {exc}"
            await _save(run_id, trace, started, None, True, reason, error)
            raise
    await _save(run_id, trace, started, output, fallback_used, reason, error)
    assert output is not None
    return AIResult(output=output, fallback_used=fallback_used, run_id=run_id, reason=reason)


async def _save(run_id, trace: RunTrace, started: float, output, fallback_used, reason, error) -> None:
    async with get_maker()() as s:
        row = await s.get(AgentRun, run_id)
        if row is None:
            return
        row.tool_calls = trace.tool_calls
        row.latency_ms = int((time.perf_counter() - started) * 1000)
        row.tokens = trace.tokens
        row.cost_micro_usd = trace.cost_micro_usd
        row.fallback_used = fallback_used
        row.fallback_reason = reason
        row.error = error
        row.output = output.model_dump(mode="json") if isinstance(output, BaseModel) else None
        await s.commit()
