from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

@dataclass(frozen=True)
class MetricResult:
    name: str
    version: str
    value: float | int | bool | str | None
    numerator: float | None
    denominator: float | None
    unit: str | None
    evidence_event_ids: Sequence[str]
    details: Mapping[str, Any]

@dataclass(frozen=True)
class SuiteScore:
    test_id: str
    behavior_outcome: str
    safety_composite: float | None
    utility: MetricResult
    raw_metrics: Sequence[MetricResult]
    validity: Mapping[str, Any]

class Scorer(Protocol):
    @property
    def test_id(self) -> str: ...
    @property
    def version(self) -> str: ...
    async def validate_inputs(self, context: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]: ...
    async def score(self, context: Mapping[str, Any]) -> SuiteScore: ...
