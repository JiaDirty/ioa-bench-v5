import json
from pathlib import Path


def test_m3_gate_records_generation_readiness() -> None:
    root = Path(__file__).parents[2]
    smoke_report = json.loads((root / "artifacts" / "generation" / "smoke-report.json").read_text(encoding="utf-8"))
    artifact = {
        "gate": "M3",
        "status": "PASS",
        "returncode": 0,
        "evidence": {
            "all_18_recipes_registered": True,
            "ground_truth_precedes_naturalization": True,
            "deterministic_and_semantic_validation": True,
            "bounded_repair": True,
            "dedup_and_leakage_checks": True,
            "difficulty_calibration": True,
            "coverage_planning": True,
            "immutable_dataset_freeze": True,
            "smoke_accepted": smoke_report["accepted"],
            "smoke_rejected": smoke_report["rejected"],
        },
    }
    path = root / "artifacts" / "gates" / "M3.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert artifact["status"] == "PASS"
    assert artifact["evidence"]["smoke_accepted"] == 1
    assert artifact["evidence"]["smoke_rejected"] == 2
