from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

@dataclass(frozen=True)
class CandidateCase:
    candidate_id: str
    test_id: str
    mechanism_id: str
    world_id: str
    difficulty: str
    sut_payload: Mapping[str, Any]
    oracle_payload: Mapping[str, Any]
    provenance: Mapping[str, Any]

@dataclass(frozen=True)
class ValidationFinding:
    validator_id: str
    passed: bool
    code: str
    detail: str
    evidence: Mapping[str, Any]

class DatasetGeneratorPort(Protocol):
    async def generate_candidate(self, request: Mapping[str, Any]) -> CandidateCase: ...

class DatasetValidatorPort(Protocol):
    async def validate(self, candidate: CandidateCase) -> Sequence[ValidationFinding]: ...
