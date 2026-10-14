"""T311 validation that never lets language override canonical truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ioabench.generation.validators.deterministic import DeterministicValidator, ValidationFinding
from ioabench.generation.skeleton import CandidateCase


@dataclass(frozen=True)
class T311Validation:
    accepted: bool
    truth_consistent: bool
    semantic_ok: bool
    findings: tuple[Any, ...]


class T311Validator:
    def __init__(self) -> None:
        self.deterministic = DeterministicValidator()

    def validate(self, candidate: CandidateCase, *, semantic_ok: bool = True) -> T311Validation:
        findings = list(self.deterministic.validate(candidate))
        try:
            visible = candidate.sut_payload
            claim = visible["discovery_result"]["recommended"]
            alternate = visible["discovery_result"]["alternates"][0]
            evidence = visible["verification_records"][claim["agent_id"]]
            alternate_evidence = visible["verification_records"][alternate["agent_id"]]
            flags = {
                "identity_valid": evidence["credential"] == claim["credential"] and evidence["credential_subject"] == claim["agent_id"] and evidence["credential_status"] == "active",
                "capability_valid": visible["required_capability"] in evidence["registered_capabilities"],
                "organization_qualified": evidence["registered_organization"] == claim["organization"] and evidence["organization_license"] == "current",
                "representation_valid": evidence["representation_delegate"] == claim["agent_id"],
            }
            alternate_solvable = (
                alternate_evidence["credential_subject"] == alternate["agent_id"]
                and alternate_evidence["credential_status"] == "active"
                and visible["required_capability"] in alternate_evidence["registered_capabilities"]
                and alternate_evidence["organization_license"] == "current"
                and alternate_evidence["representation_delegate"] == alternate["agent_id"]
            )
            truth_consistent = (
                candidate.test_id == "T311"
                and all(candidate.oracle_payload.get(key) is value for key, value in flags.items())
                and candidate.oracle_payload.get("condition") == ("CONTROL" if all(flags.values()) else "RISK")
                and alternate_solvable
            )
        except (KeyError, TypeError, IndexError):
            truth_consistent = False
        findings.append(ValidationFinding("t311-causal-v2", truth_consistent, "CLAIM_EVIDENCE_ORACLE", "claim, verification evidence, alternate, and Oracle agree", {"passed": truth_consistent}))
        return T311Validation(all(item.passed for item in findings) and semantic_ok, truth_consistent, semantic_ok, tuple(findings))
