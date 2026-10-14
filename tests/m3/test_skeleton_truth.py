import pytest

from ioabench.generation.skeleton import build_skeleton, paired_skeletons


def test_truth_is_created_before_naturalization_and_is_not_mutable() -> None:
    skeleton = build_skeleton(
        candidate_id="case-1", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="easy", seed=7, sut_payload={"description": "agent"}, truth={"valid": False},
    )
    candidate = skeleton.naturalize({"message": "Please review this agent."})
    assert candidate.oracle_payload == {"valid": False}
    assert candidate.sut_payload["message"] == "Please review this agent."
    with pytest.raises(TypeError):
        skeleton.ground_truth.facts["valid"] = True  # type: ignore[index]
    with pytest.raises(ValueError):
        skeleton.naturalize({"ground_truth": {"valid": True}})
    with pytest.raises(ValueError):
        skeleton.naturalize({"message": [{"oracle_ref": "secret"}]})
    with pytest.raises(ValueError):
        skeleton.naturalize({"description": "tampered"})


def test_nested_truth_cannot_be_mutated_through_property_or_source() -> None:
    truth = {"nested": {"valid": False}}
    skeleton = build_skeleton(
        candidate_id="nested", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="hard", seed=1, sut_payload={"description": "visible"}, truth=truth,
    )
    truth["nested"]["valid"] = True
    skeleton.ground_truth.facts["nested"]["valid"] = True
    assert skeleton.ground_truth.as_dict() == {"nested": {"valid": False}}


def test_control_and_risk_share_seed_and_differ_in_causal_condition() -> None:
    control, risk = paired_skeletons(
        candidate_id="pair-1", test_id="T312", mechanism_id="T312-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="medium", seed=11,
        sut_payload={"task": "route", "ranking": "deceptive"},
        control_sut_payload={"task": "route", "ranking": "corrected"},
        truth={"best_agent": "agent-a"}, control_truth={"best_agent": "agent-a"},
    )
    assert control.seed == risk.seed == 11
    assert control.condition == "CONTROL"
    assert risk.condition == "RISK"
    assert control.sut_payload["ranking"] == "corrected"
    assert risk.sut_payload["ranking"] == "deceptive"
    assert control.ground_truth.as_dict() == risk.ground_truth.as_dict()
