from dataclasses import replace

from ioabench.suites.t311.generation import T311Generator
from ioabench.suites.t311.validators import T311Validator


def test_t311_semantic_result_cannot_override_canonical_truth() -> None:
    candidate = T311Generator().generate().naturalize({"narrative": "polished"})
    result = T311Validator().validate(candidate, semantic_ok=False)
    assert result.accepted is False
    assert result.truth_consistent is True
    assert result.semantic_ok is False


def test_t311_validator_rejects_mismatched_oracle_even_with_semantic_acceptance() -> None:
    candidate = T311Generator().generate().naturalize({})
    changed = replace(candidate, oracle_payload={**candidate.oracle_payload, "identity_valid": True})
    result = T311Validator().validate(changed, semantic_ok=True)
    assert result.accepted is False
    assert result.truth_consistent is False
