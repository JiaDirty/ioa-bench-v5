"""Scenario identity and capability evidence, kept as separate decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class IdentityClaim:
    subject_id: str
    org_id: str
    claimed_role: str
    credential: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class IdentityEvidence:
    subject_id: str
    credential_valid: bool
    issuer: str | None
    source: str


@dataclass(frozen=True)
class CapabilityEvidence:
    subject_id: str
    capability: str
    evidence_valid: bool
    source: str


class LocalIdentityService:
    def __init__(self, trusted_credentials: Mapping[str, str] | None = None) -> None:
        self._trusted_credentials = dict(trusted_credentials or {})
        self._claims: dict[str, IdentityClaim] = {}
        self._capabilities: dict[tuple[str, str], CapabilityEvidence] = {}

    def publish_claim(self, claim: IdentityClaim) -> None:
        self._claims[claim.subject_id] = claim

    def add_capability_evidence(self, evidence: CapabilityEvidence) -> None:
        self._capabilities[(evidence.subject_id, evidence.capability)] = evidence

    def evidence(self, subject_id: str) -> IdentityEvidence:
        claim = self._claims[subject_id]
        expected = self._trusted_credentials.get(claim.org_id)
        return IdentityEvidence(subject_id, expected is not None and claim.credential == expected, claim.org_id if expected else None, "local-trust-store")

    def verify(self, subject_id: str, capability: str | None = None) -> dict[str, Any]:
        identity = self.evidence(subject_id)
        result: dict[str, Any] = {"subject_id": subject_id, "identity_verified": identity.credential_valid}
        if capability is not None:
            capability_evidence = self._capabilities.get((subject_id, capability))
            result["capability_verified"] = bool(capability_evidence and capability_evidence.evidence_valid)
            result["capability_evidence_source"] = capability_evidence.source if capability_evidence else None
        return result
