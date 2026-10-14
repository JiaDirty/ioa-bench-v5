import pytest

from ioabench.datasets import DatasetStore


def _manifest(version: str = "1.0.0") -> dict[str, object]:
    return {
        "schema_version": "1.0", "dataset_id": "T311-v1", "test_id": "T311", "version": version, "status": "FROZEN",
        "target": {"qualified_cases": 1, "difficulty": {"easy": 1, "medium": 0, "hard": 0}},
        "generation": {"generator_version": "0.1.0", "mechanism_template_versions": ["T311-M01@0.1.0"], "world_ids": ["W01_ENTERPRISE_OPS"], "candidate_target_min": 2, "model_routing_policy": "dynamic_from_live_catalog"},
        "quality_gates": {"schema_valid": True, "oracle_consistent": True, "exposure_reachable": True, "control_solvable": True, "no_truth_leakage": True, "semantic_validation": "DUAL_VALIDATOR"},
        "splits": {"development": 0.0, "formal": 1.0},
        "provenance_policy": {"retain_rejected": True, "record_model_calls": True, "record_prompt_versions": True},
    }


def test_frozen_dataset_writes_manifest_cases_and_rejected_provenance(tmp_path) -> None:
    target = DatasetStore(tmp_path).freeze(_manifest(), [{"case_id": "c-1", "difficulty": "easy"}], [{"case_id": "bad", "reason": "leak"}])
    assert (target / "manifest.json").exists()
    assert (target / "cases.jsonl").read_text(encoding="utf-8").count("c-1") == 1
    assert "leak" in (target / "rejected.jsonl").read_text(encoding="utf-8")
    assert len(DatasetStore(tmp_path).load_manifest("T311-v1", "1.0.0")["content_sha256"]) == 64


def test_frozen_dataset_version_is_immutable_and_corrections_need_new_version(tmp_path) -> None:
    store = DatasetStore(tmp_path)
    store.freeze(_manifest(), [{"case_id": "c-1"}])
    with pytest.raises(FileExistsError):
        store.freeze(_manifest(), [{"case_id": "changed"}])
    assert store.freeze(_manifest("1.0.1"), [{"case_id": "changed"}]).exists()
