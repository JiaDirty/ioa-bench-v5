import asyncio

import pytest

from ioabench.protocols.mcp import LocalMCPAdapter, ToolCallError, ToolDefinition


def test_mcp_discovers_calls_and_observes_tool_errors() -> None:
    events = []
    adapter = LocalMCPAdapter(events.append)
    adapter.register_tool(ToolDefinition("sandbox.read", "Read local synthetic state", {"type": "object"}), lambda args: {"value": args["key"]})

    tools = asyncio.run(adapter.list_tools())
    result = asyncio.run(adapter.call_tool("local", {"name": "sandbox.read", "arguments": {"key": "x"}}, idempotency_key="a-1"))

    assert tools[0]["name"] == "sandbox.read"
    assert result["value"] == "x"
    assert result["action_id"]
    with pytest.raises(ToolCallError):
        asyncio.run(adapter.call_tool("local", {"name": "missing", "arguments": {}}, idempotency_key="a-2"))
    assert {event["event_type"] for event in events} >= {"tool.call.request", "tool.call.result"}


def test_mcp_adapter_awaits_async_tool_handlers() -> None:
    async def handler(arguments: dict[str, object]) -> dict[str, object]:
        return {"value": arguments["value"]}

    adapter = LocalMCPAdapter()
    adapter.register_tool(ToolDefinition("async.echo", "echo", {"type": "object"}), handler)
    result = asyncio.run(adapter.call_tool("local", {"name": "async.echo", "arguments": {"value": 1}}, idempotency_key="a-3"))
    assert result["value"] == 1
