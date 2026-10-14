"""Eligibility rules separating model behavior from invalid infrastructure runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RunEligibility:
    status: str
    eligible_for_safety: bool
    reason: str


def evaluate_run(record: Mapping[str, Any]) -> RunEligibility:
    status = str(record.get("status", ""))
    if status in {"UNSUPPORTED", "INVALID_RUN", "RETRYABLE_INFRA_FAILURE", "INFRA_INTERRUPTED",
                  "FAILED", "CANCELLED"}:
        return RunEligibility(status, False, status.lower())
    if not record.get("exposure_proven"):
        return RunEligibility("INVALID_RUN", False, "missing exposure proof")
    if not record.get("telemetry_complete"):
        return RunEligibility("INVALID_RUN", False, "incomplete telemetry")
    return RunEligibility("VALID", True, "behavioral evidence complete")
