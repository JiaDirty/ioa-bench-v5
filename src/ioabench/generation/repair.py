"""Bounded candidate repair without quality-threshold downgrades."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .skeleton import CandidateCase
from .validators.deterministic import DeterministicValidator, ValidationFinding


@dataclass(frozen=True)
class RepairResult:
    status: str
    candidate: CandidateCase
    attempts: int
    findings: tuple[ValidationFinding, ...]


class BoundedRepair:
    def __init__(self, validator: DeterministicValidator, *, max_repairs: int = 1) -> None:
        if max_repairs < 0:
            raise ValueError("max_repairs cannot be negative")
        self.validator = validator
        self.max_repairs = max_repairs

    def run(self, candidate: CandidateCase, repair: Callable[[CandidateCase], CandidateCase]) -> RepairResult:
        current = candidate
        findings = self.validator.validate(current)
        if all(finding.passed for finding in findings):
            return RepairResult("ACCEPTED", current, 0, findings)
        if self.max_repairs == 0:
            return RepairResult("REGENERATE", current, 0, findings)
        current = repair(current)
        findings = self.validator.validate(current)
        return RepairResult("REPAIRED" if all(finding.passed for finding in findings) else "REGENERATE", current, 1, findings)


def rejection_codes(findings: Iterable[ValidationFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        if not finding.passed:
            counts[finding.code] = counts.get(finding.code, 0) + 1
    return counts
