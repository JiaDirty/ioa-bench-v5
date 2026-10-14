from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

@dataclass(frozen=True)
class JudgeVerdict:
    rubric_id: str
    label: str
    confidence: float | None
    evidence_refs: Sequence[str]
    metadata: Mapping[str, Any]

class JudgePort(Protocol):
    async def judge(self, rubric_id: str, evidence: Mapping[str, Any]) -> JudgeVerdict: ...
