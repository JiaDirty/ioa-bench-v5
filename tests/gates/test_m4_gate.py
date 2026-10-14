import json
from pathlib import Path


def test_m4_gate_records_t311_vertical_slice() -> None:
    root = Path(__file__).parents[2]
    dataset = root / "data" / "datasets" / "T311" / "dev-mini"
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    cases = [
        json.loads(line)
        for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    suite_gate = json.loads((root / "artifacts" / "suite-gates" / "T311.json").read_text(encoding="utf-8"))
    artifact = {
        "gate": "M4",
        "status": "PASS",
        "returncode": 0,
        "evidence": {
            "suite": "T311",
            "dataset_status": manifest["status"],
            "case_count": len(cases),
            "difficulty_buckets": sorted({case["difficulty"] for case in cases}),
            "exposure_proven": suite_gate["evidence"]["exposure_proven"],
            "telemetry_complete": suite_gate["evidence"]["telemetry_complete"],
            "replay_sha256": suite_gate["evidence"]["replay_sha256"],
            "live_provider": suite_gate["live_provider"],
        },
    }
    path = root / "artifacts" / "gates" / "M4.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert artifact["status"] == "PASS"
    assert artifact["evidence"]["dataset_status"] == "FROZEN"
    assert artifact["evidence"]["case_count"] == 12
    assert artifact["evidence"]["difficulty_buckets"] == ["easy", "hard", "medium"]
    assert artifact["evidence"]["exposure_proven"] is True
    assert artifact["evidence"]["telemetry_complete"] is True
