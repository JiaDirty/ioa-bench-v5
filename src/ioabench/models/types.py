"""Provider-neutral model request and response values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model_id: str
    capabilities: Mapping[str, Any]
    default_parameters: Mapping[str, Any]
    role: str = "TESTED"


@dataclass(frozen=True)
class ModelRequest:
    messages: Sequence[Mapping[str, Any]]
    parameters: Mapping[str, Any]
    tools: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    role_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    text: str | None
    tool_calls: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    structured: Mapping[str, Any] | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)
    model_id: str = ""
    finish_reason: str | None = None
    # Thinking/reasoning channels returned alongside ``text``. Persisted for
    # observability. Replaying them into follow-up requests is a versioned
    # protocol decision, not a free choice: DeepSeek's direct thinking-mode
    # contract REQUIRES full reasoning_content replay on every tool-carrying
    # request (HTTP 400 otherwise) and silently ignores it without tools; the
    # AIHubMix gateway's handling of a replayed reasoning_content is unverified
    # (the historical pilot completed multi-turn tool episodes without replay
    # through it).
    reasoning_content: str | None = None
    reasoning_details: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None


def normalize_request(request: ModelRequest) -> ModelRequest:
    if not request.messages:
        raise ValueError("model request requires at least one message")
    if any("role" not in message or "content" not in message for message in request.messages):
        raise ValueError("every model message requires role and content")
    return request
