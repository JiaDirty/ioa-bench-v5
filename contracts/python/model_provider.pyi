from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model_id: str
    capabilities: Mapping[str, Any]
    default_parameters: Mapping[str, Any]

@dataclass(frozen=True)
class ModelRequest:
    messages: Sequence[Mapping[str, Any]]
    parameters: Mapping[str, Any]
    tools: Sequence[Mapping[str, Any]] = ...

@dataclass(frozen=True)
class ModelResponse:
    text: str | None
    tool_calls: Sequence[Mapping[str, Any]]
    structured: Mapping[str, Any] | None
    usage: Mapping[str, Any]
    provider_metadata: Mapping[str, Any]

class ModelPort(Protocol):
    async def resolve(self, model_id: str) -> ModelProfile: ...
    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse: ...
