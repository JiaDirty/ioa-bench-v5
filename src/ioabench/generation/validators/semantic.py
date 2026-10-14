"""Independent semantic validation without Oracle context."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from ioabench.hashing import canonical_sha256


@dataclass(frozen=True)
class SemanticVerdict:
    validator_id: str
    label: str
    confidence: float | None
    evidence_refs: tuple[str, ...]
    metadata: Mapping[str, Any]


JudgeFn = Callable[[Mapping[str, Any]], SemanticVerdict | Awaitable[SemanticVerdict]]


class SemanticValidator:
    def __init__(self, validator_id: str, judge: JudgeFn) -> None:
        self.validator_id = validator_id
        self.judge = judge

    async def validate(self, visible_context: Mapping[str, Any]) -> SemanticVerdict:
        if _contains_hidden(visible_context):
            raise ValueError("semantic validator context contains hidden truth")
        context_hash = canonical_sha256(visible_context)
        result = self.judge(dict(visible_context))
        verdict = await result if inspect.isawaitable(result) else result
        return SemanticVerdict(
            self.validator_id, verdict.label, verdict.confidence, tuple(verdict.evidence_refs),
            {**dict(verdict.metadata), "validator_id": self.validator_id, "input_sha256": context_hash},
        )


class ValidatorArbitrator:
    def __init__(self, primary: SemanticValidator, secondary: SemanticValidator, arbiter: SemanticValidator | None = None) -> None:
        self.primary = primary
        self.secondary = secondary
        self.arbiter = arbiter

    async def validate(self, visible_context: Mapping[str, Any]) -> tuple[SemanticVerdict, ...]:
        first = await self.primary.validate(visible_context)
        second = await self.secondary.validate(visible_context)
        if first.label == second.label or self.arbiter is None:
            return (first, second)
        return (first, second, await self.arbiter.validate(visible_context))


def _contains_hidden(value: Any) -> bool:
    hidden = {"oracle", "oracle_ref", "oracle_payload", "ground_truth", "hidden_truth", "truth", "attack_label", "scoring_rules"}
    if isinstance(value, Mapping):
        return any(str(key).casefold() in hidden or _contains_hidden(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_hidden(item) for item in value)
    return False
