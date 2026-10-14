"""Replay recorded model responses by normalized request hash."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ioabench.hashing import canonical_sha256

from .types import ModelProfile, ModelRequest, ModelResponse


class ReplayModel:
    def __init__(self, responses: Mapping[str, ModelResponse]) -> None:
        self._responses = dict(responses)

    @classmethod
    def from_records(cls, records: Mapping[Mapping[str, Any], ModelResponse]) -> "ReplayModel":
        return cls({canonical_sha256(dict(request)): response for request, response in records.items()})

    async def resolve(self, model_id: str) -> ModelProfile:
        return ModelProfile("replay", model_id, {"replay": True}, {})

    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse:
        key = canonical_sha256({"messages": list(request.messages), "parameters": dict(request.parameters), "tools": list(request.tools)})
        try:
            return self._responses[key]
        except KeyError as exc:
            raise KeyError(f"no replay response for request hash {key}") from exc
