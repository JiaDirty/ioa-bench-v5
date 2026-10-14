"""MCP-shaped local tool discovery and invocation boundary."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, Callable, Mapping
from uuid import uuid4


class ToolCallError(RuntimeError):
    """A local tool failed or was not available."""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Mapping[str, Any]


class LocalMCPAdapter:
    def __init__(self, telemetry: Callable[[Mapping[str, Any]], None] | None = None) -> None:
        self._tools: dict[str, tuple[ToolDefinition, Callable[[Mapping[str, Any]], Mapping[str, Any]]]] = {}
        self._telemetry = telemetry

    def register_tool(self, definition: ToolDefinition, handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = (definition, handler)

    async def list_tools(self, endpoint: str = "local") -> tuple[Mapping[str, Any], ...]:
        return tuple({"name": definition.name, "description": definition.description, "inputSchema": dict(definition.input_schema)} for definition, _ in self._tools.values())

    async def call_tool(self, endpoint: str, request: Mapping[str, Any], *, idempotency_key: str) -> Mapping[str, Any]:
        action_id = str(request.get("action_id") or uuid4())
        tool_name = str(request.get("name", ""))
        arguments = request.get("arguments", {})
        self._emit({"event_type": "tool.call.request", "action_id": action_id, "tool": tool_name, "endpoint": endpoint})
        if tool_name not in self._tools or not isinstance(arguments, Mapping):
            error = {"action_id": action_id, "status": "ERROR", "error_class": "ToolCallError", "error": "unknown tool or invalid arguments"}
            self._emit({"event_type": "tool.call.result", **error})
            raise ToolCallError(error["error"])
        try:
            result = self._tools[tool_name][1](arguments)
            if inspect.isawaitable(result):
                result = await result
            result = dict(result)
        except Exception as exc:
            error = {"action_id": action_id, "status": "ERROR", "error_class": type(exc).__name__, "error": str(exc)}
            self._emit({"event_type": "tool.call.result", **error})
            raise ToolCallError(str(exc)) from exc
        result.update({"action_id": action_id, "status": "OK", "idempotency_key": idempotency_key})
        self._emit({"event_type": "tool.call.result", **result})
        return result

    def _emit(self, event: Mapping[str, Any]) -> None:
        if self._telemetry is not None:
            self._telemetry(event)
