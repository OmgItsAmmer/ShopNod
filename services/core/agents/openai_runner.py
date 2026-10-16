"""Runs an OpenAI Agents SDK agent, optionally with the ShopNod MCP server as its tool source."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from ..ai import RunTrace
from ..settings import get_settings

log = logging.getLogger("shopnod.agents")
COST_MICRO_USD_PER_TOKEN = 5  # rough blended estimate; real cost tracking is per-model in V1


class ToolBudgetExceeded(Exception):
    pass


async def run_openai_agent(
    trace: RunTrace,
    *,
    name: str,
    instructions: str,
    user_input: str,
    output_type: type[BaseModel],
    model: str,
    mcp_token: str | None = None,
    allowed_tools: list[str] | None = None,
    max_tool_calls: int = 6,
) -> BaseModel:
    from agents import Agent, RunHooks, Runner, set_default_openai_key

    s = get_settings()
    set_default_openai_key(s.OPENAI_API_KEY)

    class _Hooks(RunHooks):
        def __init__(self) -> None:
            self.calls = 0

        async def on_tool_start(self, context, agent, tool) -> None:  # type: ignore[override]
            self.calls += 1
            trace.tool(getattr(tool, "name", "tool"))
            if self.calls > max_tool_calls:
                raise ToolBudgetExceeded(f"more than {max_tool_calls} tool calls")

    hooks = _Hooks()

    async def _go(mcp_servers: list[Any]):
        agent = Agent(name=name, instructions=instructions, model=model, mcp_servers=mcp_servers, output_type=output_type)
        return await Runner.run(agent, user_input, max_turns=max_tool_calls + 2, hooks=hooks)

    if mcp_token:
        from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

        server = MCPServerStreamableHttp(
            name="shopnod",
            params={"url": s.MCP_INTERNAL_URL, "headers": {"Authorization": f"Bearer {mcp_token}"}, "timeout": 8},
            cache_tools_list=True,
            tool_filter=create_static_tool_filter(allowed_tool_names=allowed_tools) if allowed_tools else None,
        )
        async with server:
            result = await _go([server])
    else:
        result = await _go([])

    try:
        usage = result.context_wrapper.usage
        trace.tokens += int(getattr(usage, "total_tokens", 0) or 0)
        trace.cost_micro_usd += trace.tokens * COST_MICRO_USD_PER_TOKEN
    except Exception:  # noqa: BLE001
        pass
    return result.final_output
