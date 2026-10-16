"""The Shop Agent's real tool path: the OpenAI Agents SDK's MCP client -> our MCP server over Streamable HTTP.
No OpenAI key is needed: we drive the client directly instead of letting a model choose tools."""
import asyncio
import socket
import uuid
from datetime import timedelta

import pytest
import uvicorn
from conftest import onboard

from shopnod_core import auth, clock
from shopnod_core.agents.shop_agent import AGENT_TOOLS


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def mcp_url(env):
    from shopnod_mcp.server import create_app

    port = free_port()
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    await asyncio.wait_for(task, 10)


def sdk_client(url: str, token: str, allowed=None):
    from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

    return MCPServerStreamableHttp(
        name="shopnod",
        params={"url": url, "headers": {"Authorization": f"Bearer {token}"}, "timeout": 8},
        cache_tools_list=True,
        tool_filter=create_static_tool_filter(allowed_tool_names=allowed) if allowed else None,
    )


async def test_agent_sdk_sees_only_the_allowed_tools_and_can_submit_but_not_approve(client, mcp_url):
    sk = await onboard(client)
    token = auth.create_agent_token(uuid.UUID(sk.shop_id))
    async with sdk_client(mcp_url, token, AGENT_TOOLS) as agent_side:
        tools = {t.name for t in await agent_side.list_tools()}
        assert tools == set(AGENT_TOOLS)
        assert "approve_proposal" not in tools and "reject_proposal" not in tools  # filtered out for the model

        items = await agent_side.call_tool("list_items", {})
        assert not items.is_error
        profile = await agent_side.call_tool("get_shop_profile", {})
        assert "Test Bakery" in str(profile.content)

        import json

        ids = [json.loads(c.text)["item_id"] for c in items.content]  # one JSON text block per item
        assert ids, items
        start = (clock.now() + timedelta(minutes=30)).isoformat()
        end = (clock.now() + timedelta(minutes=90)).isoformat()
        sub = await agent_side.call_tool(
            "submit_proposal", {"item_ids": ids[:1], "pct": 10, "window_start": start, "window_end": end, "cap": 20, "reason": "Quiet hour."}
        )
        assert not sub.is_error and "pending" in str(sub.content)

    # even with NO client-side filter, the server itself refuses the agent token on approve
    async with sdk_client(mcp_url, token) as unfiltered:
        names = {t.name for t in await unfiltered.list_tools()}
        assert "approve_proposal" in names  # the tool exists on the server (for shopkeeper tokens) ...
        res = await unfiltered.call_tool("approve_proposal", {"proposal_id": str(uuid.uuid4())})
        assert res.is_error and "scope_missing" in str(res.content)  # ... but this token cannot use it

    inbox = await sk.inbox()
    assert len(inbox) == 1 and inbox[0]["source"] == "ai" and inbox[0]["status"] == "pending"
    assert (await client.get("/v1/shop/offers")).json() == []  # nothing published


async def test_bad_token_is_refused_by_the_server(client, mcp_url):
    async with sdk_client(mcp_url, "snpat_not-a-real-token") as c:
        res = await c.call_tool("get_guardrails", {})
        assert res.is_error and "unauthorized" in str(res.content)
