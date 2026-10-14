"""Visible claims with source and provenance, separate from canonical truth."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ClaimInstance:
    claim_id: str
    canonical_ref: str | None
    source_agent_id: str | None
    surface_text: str
    confidence: float | None
    provenance: Mapping[str, Any] = field(default_factory=dict)


class KnowledgeStore:
    def __init__(self) -> None:
        self._claims: dict[str, ClaimInstance] = {}

    def publish(self, claim: ClaimInstance) -> None:
        self._claims[claim.claim_id] = claim

    def get(self, claim_id: str) -> ClaimInstance | None:
        return self._claims.get(claim_id)

    def search(self, text: str) -> tuple[ClaimInstance, ...]:
        needle = text.casefold()
        return tuple(claim for claim in self._claims.values() if needle in claim.surface_text.casefold())
