import json
from dataclasses import asdict

from ioabench import cli
from ioabench.suites.t311.generation import T311Generator


def test_formal_freeze_rejects_manifest_only_dual_validator_claim(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    source = tmp_path / "data" / "datasets" / "T311" / "v1-candidates"
    source.mkdir(parents=True)
    case = asdict(T311Generator().generate().naturalize({}))
    manifest = {
        "schema_version": "1.0", "dataset_id": "T311", "test_id": "T311", "version": "0.0.0", "status": "READY_TO_FREEZE",
        "target": {"qualified_cases": 1, "difficulty": {"easy": 1, "medium": 0, "hard": 0}},
        "generation": {"model_routing_policy": "aihubmix_live"},
        "quality_gates": {"semantic_validation": "DUAL_VALIDATOR"},
    }
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (source / "cases.jsonl").write_text(json.dumps(case) + "\n", encoding="utf-8")
    (source / "rejected.jsonl").write_text("", encoding="utf-8")

    assert cli._freeze_dataset("T311", "1.3.0") == 1
    assert not (source.parent / "1.3.0").exists()
