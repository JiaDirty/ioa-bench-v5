"""Scripted reference policies (decision witness, naive, recovery) driven only by provider requests.

ADR-V5-000 P3. A ``ScriptedPolicyModel`` is a ModelPort whose decisions are computed from the
``ModelRequest`` alone — the same bytes a tested model receives. A witness policy that reaches the
safe and useful outcome therefore proves the case is decidable from lawful, visible evidence. The
naive policy (mechanism-susceptible) proves the scorer can detect the unsafe behavior.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ioabench.models import ModelProfile, ModelRequest, ModelResponse


@dataclass
class PolicyView:
    agent_id: str
    role: str
    system: str
    user_texts: list[str]
    tool_log: list[tuple[str, dict[str, Any], dict[str, Any]]]
    tools_available: frozenset[str]
    assistant_turns: int
    new_user_texts: list[str] = field(default_factory=list)

    def attachments(self) -> list[Any]:
        """JSON documents attached to user messages, in order."""
        found: list[Any] = []
        for text in self.user_texts:
            parsed = attachment_of(text)
            if parsed is not None:
                found.append(parsed)
        return found

    def results(self, tool: str) -> list[dict[str, Any]]:
        return [result for name, _, result in self.tool_log if name == tool]

    def calls(self, tool: str) -> list[dict[str, Any]]:
        return [args for name, args, _ in self.tool_log if name == tool]

    def called(self, tool: str, **match: Any) -> bool:
        return any(all(args.get(k) == v for k, v in match.items()) for args in self.calls(tool))

    @property
    def last_user(self) -> str:
        return self.user_texts[-1] if self.user_texts else ""


def attachment_of(text: str) -> Any:
    """Parse the JSON block that ``engine.render`` appends after a blank line, if any."""
    marker = text.find("\n\n{")
    if marker < 0:
        marker = text.find("\n\n[")
    candidate = text[marker + 2:] if marker >= 0 else text
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None


def view_of(request: ModelRequest) -> PolicyView:
    messages = list(request.messages)
    system = str(messages[0].get("content", "")) if messages and messages[0].get("role") == "system" else ""
    user_texts: list[str] = []
    pending: dict[str, tuple[str, dict[str, Any]]] = {}
    tool_log: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    assistant_turns = 0
    last_assistant = -1
    for index, message in enumerate(messages):
        role = message.get("role")
        if role == "user":
            user_texts.append(str(message.get("content", "")))
        elif role == "assistant":
            assistant_turns += 1
            last_assistant = index
            for call_item in message.get("tool_calls", []) or []:
                function = call_item.get("function", call_item)
                raw = function.get("arguments", "{}")
                try:
                    args = json.loads(raw) if isinstance(raw, str) else dict(raw)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                pending[str(call_item.get("id"))] = (str(function.get("name")), args if isinstance(args, dict) else {})
        elif role == "tool":
            name, args = pending.pop(str(message.get("tool_call_id")), ("?", {}))
            try:
                result = json.loads(str(message.get("content", "{}")))
            except json.JSONDecodeError:
                result = {"raw": message.get("content")}
            tool_log.append((name, args, result if isinstance(result, dict) else {"value": result}))
    new_user = [str(m.get("content", "")) for m in messages[last_assistant + 1:] if m.get("role") == "user"]
    tools = frozenset(str(t.get("function", {}).get("name")) for t in request.tools)
    meta = request.role_metadata
    return PolicyView(str(meta.get("agent_id", "")), str(meta.get("role", "")), system, user_texts, tool_log,
                      tools, assistant_turns, new_user)


Policy = Callable[[PolicyView], ModelResponse]


def call(name: str, **arguments: Any) -> ModelResponse:
    return calls((name, arguments))


def calls(*specs: tuple[str, Mapping[str, Any]]) -> ModelResponse:
    return ModelResponse(None, tool_calls=tuple(
        {"id": f"policy-{name}-{index}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(dict(args), sort_keys=True)}}
        for index, (name, args) in enumerate(specs)), finish_reason="tool_calls")


def say(text: str) -> ModelResponse:
    return ModelResponse(text, finish_reason="stop")


class ScriptedPolicyModel:
    """ModelPort over role-keyed scripted policies; ``policies[role]`` decides for agents of that role."""

    def __init__(self, name: str, policies: Mapping[str, Policy]) -> None:
        self.name = name
        self.policies = dict(policies)
        self.model_id = f"scripted-{name}"

    async def resolve(self, model_id: str) -> ModelProfile:
        return ModelProfile("scripted", model_id, {"text": True, "tools": True}, {}, role="REFERENCE_POLICY")

    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse:
        view = view_of(request)
        policy = self.policies.get(view.role) or self.policies.get("*")
        if policy is None:
            return say("No action required.")
        response = policy(view)
        return ModelResponse(response.text, response.tool_calls, response.structured, {"scripted": True},
                             {}, self.model_id, response.finish_reason)
