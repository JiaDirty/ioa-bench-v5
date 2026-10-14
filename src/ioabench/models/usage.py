"""Provider usage, latency and cost accounting."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping


@dataclass(frozen=True)
class UsageRecord:
    model_id: str
    latency_seconds: float
    retries: int
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float | None = None
    status: str = "SUCCESS"
    error_class: str | None = None

    @classmethod
    def from_response(cls, model_id: str, started: float, usage: Mapping[str, Any], retries: int = 0) -> "UsageRecord":
        input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)
        return cls(model_id, perf_counter() - started, retries, input_tokens, output_tokens, total_tokens)

    @classmethod
    def failure(cls, model_id: str, started: float, error_class: str, retries: int) -> "UsageRecord":
        return cls(model_id, perf_counter() - started, retries, status="PROVIDER_FAILURE", error_class=error_class)
