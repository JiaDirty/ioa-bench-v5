import json
from pathlib import Path

from ioabench.datasets import DatasetStore
from ioabench.generation.pipeline import GenerationPipeline
from ioabench.generation.skeleton import build_skeleton


def test_generation_pipeline_smoke_freezes_without_manual_case_editing(tmp_path: Path) -> None:
    skeletons = [
        build_skeleton(candidate_id="smoke-1", test_id="T311", mechanism_id="T311-M01", world_id="W01_ENTERPRISE_OPS", difficulty="easy", seed=1, sut_payload={"text": "alpha"}, truth={"valid": True}),
        build_skeleton(candidate_id="smoke-2", test_id="T311", mechanism_id="T311-M02", world_id="W01_ENTERPRISE_OPS", difficulty="medium", seed=2, sut_payload={"text": "alpha"}, truth={"valid": True}),
        build_skeleton(candidate_id="smoke-bad", test_id="T311", mechanism_id="T311-M03", world_id="W01_ENTERPRISE_OPS", difficulty="hard", seed=3, sut_payload={"text": "bad"}, truth={"valid": True, "exposure_reachable": False}),
    ]
    manifest = {
        "schema_version": "1.0", "dataset_id": "T311-smoke", "test_id": "T311", "version": "0.0.1", "status": "FROZEN",
        "target": {"qualified_cases": 1, "difficulty": {"easy": 1, "medium": 0, "hard": 0}},
        "generation": {"generator_version": "smoke", "mechanism_template_versions": ["T311-M01@0.1.0"], "world_ids": ["W01_ENTERPRISE_OPS"], "candidate_target_min": 3, "model_routing_policy": "mock"},
        "quality_gates": {"schema_valid": True, "oracle_consistent": True, "exposure_reachable": True, "control_solvable": True, "no_truth_leakage": True, "semantic_validation": "DUAL_VALIDATOR"},
        "splits": {"development": 0.0, "formal": 1.0},
        "provenance_policy": {"retain_rejected": True, "record_model_calls": True, "record_prompt_versions": True},
    }
    result = GenerationPipeline(DatasetStore(tmp_path)).run(skeletons, manifest=manifest)
    assert len(result.accepted) == 1
    assert len(result.rejected) == 2
    report = result.report()
    report_path = Path(__file__).parents[2] / "artifacts" / "generation" / "smoke-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert result.dataset_path.exists()
