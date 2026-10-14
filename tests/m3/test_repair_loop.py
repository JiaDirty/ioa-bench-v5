from ioabench.generation.repair import BoundedRepair
from ioabench.generation.skeleton import build_skeleton
from ioabench.generation.validators.deterministic import DeterministicValidator


def test_repair_is_bounded_and_can_accept_one_local_fix() -> None:
    candidate = build_skeleton(
        candidate_id="repair", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="easy", seed=1, sut_payload={"message": "review"},
        truth={"exposure_reachable": False, "control_solvable": True},
    ).naturalize({})
    repaired = BoundedRepair(DeterministicValidator()).run(
        candidate, lambda value: type(value)(value.candidate_id, value.test_id, value.mechanism_id, value.world_id, value.difficulty, value.sut_payload, {**value.oracle_payload, "exposure_reachable": True}, value.provenance),
    )
    assert repaired.status == "REPAIRED"
    assert repaired.attempts == 1


def test_repair_failure_requests_regeneration() -> None:
    candidate = build_skeleton(
        candidate_id="reject", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="easy", seed=1, sut_payload={"message": "review"},
        truth={"exposure_reachable": False, "control_solvable": True},
    ).naturalize({})
    result = BoundedRepair(DeterministicValidator()).run(candidate, lambda value: value)
    assert result.status == "REGENERATE"
    assert result.attempts == 1
