"""Provider-neutral model port."""

from __future__ import annotations

from typing import Protocol

from .types import ModelProfile, ModelRequest, ModelResponse


class ModelPort(Protocol):
    async def resolve(self, model_id: str) -> ModelProfile: ...

    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse: ...
