"""Deterministic offline model for contract and scenario tests."""

from __future__ import annotations

from collections.abc import Iterable

from .types import ModelProfile, ModelRequest, ModelResponse


class MockModel:
    def __init__(self, responses: Iterable[ModelResponse], model_id: str = "mock") -> None:
        self._responses = iter(responses)
        self.model_id = model_id

    async def resolve(self, model_id: str) -> ModelProfile:
        return ModelProfile("mock", model_id, {"text": True, "tools": True}, {})

    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse:
        response = next(self._responses)
        return response if response.model_id else ModelResponse(
            response.text, response.tool_calls, response.structured, response.usage,
            response.provider_metadata, profile.model_id, response.finish_reason,
        )
