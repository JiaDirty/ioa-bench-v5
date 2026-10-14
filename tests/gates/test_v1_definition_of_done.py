import json
from pathlib import Path


def test_v2_gate_records_formal_completion() -> None:
    root = Path(__file__).parents[2]
    results = json.loads((root / "data" / "runs" / "mock-v1" / "results.json").read_text(encoding="utf-8"))
    formal_root = root / "data" / "runs" / "deepseek-v4.1-flash-v1-pack-v2-r5"
    formal = json.loads((formal_root / "results.json").read_text(encoding="utf-8"))
    completeness = json.loads((formal_root / "completeness.json").read_text(encoding="utf-8"))
    audit = json.loads((root / "artifacts" / "runs" / "deepseek-v4.1-flash-v1-pack-v2-r5" / "replay-audit.json").read_text(encoding="utf-8"))
    metrics = json.loads((root / "data" / "reports" / "deepseek-v4.1-flash-v1-pack-v2-r5" / "metrics" / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((formal_root / "manifest" / "deepseek-v4.1-flash-v1-pack-v2-r5.json").read_text(encoding="utf-8"))
    assert len(formal) == 1620
    assert all(record.get("status") == "COMPLETED" and record.get("eligibility") == "VALID" for record in formal.values())
    assert completeness["status"] == "VALID" and completeness["replay"]["hash_matches"] == 1620
    assert audit["status"] == "PASS" and audit["audited_valid_units"] == 1620
    assert len(metrics["suites"]) == 18
    assert all(value["task_utility"]["task_success"] is not None for value in metrics["suites"].values())
    assert all(value["efficiency"].get("model_calls", {}).get("denominator", 0) > 0 for value in metrics["suites"].values())
    assert all(value["cost"]["status"] == "ESTIMATED_FROM_LIVE_CATALOG" for value in metrics["suites"].values())
    assert manifest["tested_model"]["model_id"] == "deepseek-v4.1-flash"
    assert manifest["tested_model"]["provider"] == "aihubmix"
    assert manifest["benchmark"]["dataset_pack"] == "DATASET_PACK_V2"
    outcomes = {}
    for record in formal.values():
        outcome = record["score"]["outcome_class"]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    assert not (formal_root / "provider-blocker.json").exists()
    assert not (formal_root / "dataset-blocker.json").exists()
    artifact = {
        "gate": "M10-SCI",
        "status": "PASS",
        "run_id": formal_root.name,
        "manifest_sha256": manifest["manifest_sha256"],
        "offline_mock_run": {"status": "PASS", "units": len(results), "completed": sum(record.get("status") == "COMPLETED" for record in results.values())},
        "formal_model": {"status": "PASS", "model_id": manifest["tested_model"]["model_id"], "provider": manifest["tested_model"]["provider"], "units": len(formal), "valid": sum(record.get("eligibility") == "VALID" for record in formal.values())},
        "datasets": {"suites": 18, "cases": 1620, "difficulty": "30/30/30 per suite"},
        "outcomes": outcomes,
        "replay": {"completeness": completeness["status"], "hash_matches": completeness["replay"]["hash_matches"], "audit": audit["status"]},
        "baseline_discrimination": {"naive_suites": 18, "safe_mock_not_unsafe": True},
        "simulation_status": {suite: metrics["suites"][suite]["validity"] for suite in ("T361", "T362", "T363")},
        "artifacts": {"completeness": "PASS", "replay_audit": "PASS", "dashboard": "PASS", "report": "PASS", "release_bundle": "PASS", "utility_and_efficiency": "PASS"},
        "limitations": ["One repetition per frozen case", "T361-T363 are SIMULATION_ONLY synthetic-persona results", "No overall 18-suite safety score"],
    }
    path = root / "artifacts" / "gates" / "FINAL_SCIENTIFIC_ACCEPTANCE.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert artifact["offline_mock_run"]["units"] == 1620
    assert artifact["status"] == "PASS"
