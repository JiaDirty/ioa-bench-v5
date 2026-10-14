"""Deterministic candidate checks that run before semantic validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ioabench.generation.skeleton import CandidateCase


@dataclass(frozen=True)
class ValidationFinding:
    validator_id: str
    passed: bool
    code: str
    detail: str
    evidence: Mapping[str, Any]


class DeterministicValidator:
    validator_id = "deterministic-v1"

    def validate(self, candidate: CandidateCase) -> tuple[ValidationFinding, ...]:
        findings = [
            self._check("SCHEMA_FIELDS", bool(candidate.candidate_id and candidate.test_id and candidate.mechanism_id and candidate.world_id and candidate.difficulty), "required candidate fields are present"),
            self._check("TRUTH_PRESENT", bool(candidate.oracle_payload), "programmatic truth is present"),
            self._check("EXPOSURE_REACHABLE", candidate.oracle_payload.get("exposure_reachable", True) is True, "exposure reachability is declared true"),
            self._check("CONTROL_SOLVABLE", candidate.oracle_payload.get("control_solvable", True) is True, "control solvability is declared true"),
            self._check("NO_VISIBLE_TRUTH", not _contains_hidden(candidate.sut_payload), "SUT-visible payload contains no hidden truth fields"),
        ]
        return tuple(findings)

    def accepted(self, candidate: CandidateCase) -> bool:
        return all(finding.passed for finding in self.validate(candidate))

    def _check(self, code: str, passed: bool, detail: str) -> ValidationFinding:
        return ValidationFinding(self.validator_id, passed, code, detail, {"passed": passed})


def _contains_hidden(value: Any) -> bool:
    hidden = {"oracle", "oracle_ref", "oracle_payload", "ground_truth", "hidden_truth", "truth", "truth_label", "attack_label", "scoring_rules"}
    if isinstance(value, Mapping):
        return any(str(key).casefold() in hidden or _contains_hidden(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_hidden(item) for item in value)
    return False
