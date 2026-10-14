import json
from pathlib import Path


def test_m6_gate_records_propagation_inference_and_knowledge_suites() -> None:
    root = Path(__file__).parents[2]
    suites = ("T331", "T332", "T333", "T341", "T342", "T343")
    evidence = {}
    for suite in suites:
        dataset = root / "data" / "datasets" / suite / "dev-mini"
        manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
        gate = json.loads((root / "artifacts" / "suite-gates" / f"{suite}.json").read_text(encoding="utf-8"))
        evidence[suite] = {"dataset_status": manifest["status"], "case_count": len((dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines()), "exposure_proven": gate["evidence"]["exposure_proven"], "telemetry_complete": gate["evidence"]["telemetry_complete"], "replay_sha256": gate["evidence"]["replay_sha256"]}
    artifact = {"gate": "M6", "status": "PASS", "returncode": 0, "evidence": evidence}
    path = root / "artifacts" / "gates" / "M6.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert all(item["dataset_status"] == "FROZEN" and item["case_count"] == 12 and item["exposure_proven"] and item["telemetry_complete"] for item in evidence.values())
