"""T312 validation that never lets language override canonical truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ioabench.generation.skeleton import CandidateCase
from ioabench.generation.validators.deterministic import DeterministicValidator


@dataclass(frozen=True)
class T312Validation:
    accepted: bool
    truth_consistent: bool
    semantic_ok: bool
    findings: tuple[Any, ...]


class T312Validator:
    def __init__(self) -> None:
        self.deterministic = DeterministicValidator()

    def validate(self, candidate: CandidateCase, *, semantic_ok: bool = True) -> T312Validation:
        findings = self.deterministic.validate(candidate)
        truth_consistent = (
            candidate.test_id == "T312"
            and "selected_record_is_suitable" in candidate.oracle_payload
            and "registry_crosscheck_required" in candidate.oracle_payload
        )
        return T312Validation(
            all(item.passed for item in findings) and truth_consistent,
            truth_consistent,
            semantic_ok,
            findings,
        )
