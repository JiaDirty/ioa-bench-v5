"""Deterministic expansion of benchmark requests into resumable work units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ioabench.hashing import canonical_sha256


@dataclass(frozen=True)
class WorkUnit:
    work_id: str
    model_id: str
    suite: str
    dataset_version: str
    case_id: str
    condition: str
    repetition: int


class WorkScheduler:
    def expand(self, model_id: str, suite: str, dataset_version: str, cases: Iterable[dict], *, repetitions: int = 1) -> tuple[WorkUnit, ...]:
        if repetitions < 1:
            raise ValueError("repetitions must be positive")
        units = []
        for case in cases:
            for repetition in range(1, repetitions + 1):
                condition = str(case["provenance"]["condition"])
                identity = {"model": model_id, "suite": suite, "dataset": dataset_version, "case": case["candidate_id"], "condition": condition, "repetition": repetition}
                units.append(WorkUnit(canonical_sha256(identity)[:24], model_id, suite, dataset_version, str(case["candidate_id"]), condition, repetition))
        return tuple(units)
