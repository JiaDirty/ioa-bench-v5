from ioabench.generation.skeleton import build_skeleton
from ioabench.generation.validators.deterministic import DeterministicValidator


def test_deterministic_validator_keeps_machine_readable_rejection_reasons() -> None:
    validator = DeterministicValidator()
    valid = build_skeleton(
        candidate_id="valid", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="easy", seed=1, sut_payload={"message": "review"},
        truth={"exposure_reachable": True, "control_solvable": True},
    ).naturalize({})
    invalid = build_skeleton(
        candidate_id="invalid", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="easy", seed=1, sut_payload={"message": "review"},
        truth={"exposure_reachable": False, "control_solvable": True},
    ).naturalize({})
    assert validator.accepted(valid)
    findings = validator.validate(invalid)
    assert any(finding.code == "EXPOSURE_REACHABLE" and not finding.passed for finding in findings)
    assert all(set(finding.evidence) == {"passed"} for finding in findings)
