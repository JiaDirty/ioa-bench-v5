from ioabench.generation.difficulty import DifficultyCalibrator, DifficultyFeatures
from ioabench.generation.skeleton import build_skeleton


def test_difficulty_features_are_explicit_and_calibration_preserves_truth() -> None:
    candidate = build_skeleton(
        candidate_id="difficulty", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS",
        difficulty="easy", seed=1, sut_payload={"message": "review"}, truth={"valid": False},
    ).naturalize({})
    calibrated = DifficultyCalibrator().calibrate(candidate, DifficultyFeatures(2, 1, 1, 1, 1, 1))
    assert calibrated.difficulty == "medium"
    assert calibrated.oracle_payload == candidate.oracle_payload
    assert calibrated.sut_payload == candidate.sut_payload


def test_high_feature_complexity_is_hard() -> None:
    assert DifficultyCalibrator().classify(DifficultyFeatures(3, 3, 3, 3, 3, 3)) == "hard"
