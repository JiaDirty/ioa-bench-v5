import json
from pathlib import Path


def test_m8_gate_records_simulation_suites() -> None:
    root = Path(__file__).parents[2]
    evidence = {}
    for suite in ("T361", "T362", "T363"):
        dataset = root / "data" / "datasets" / suite / "dev-mini"
        manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
        cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
        gate = json.loads((root / "artifacts" / "suite-gates" / f"{suite}.json").read_text(encoding="utf-8"))
        validity = json.loads((root / "artifacts" / "suite-gates" / f"{suite}-simulation-validity.json").read_text(encoding="utf-8"))
        evidence[suite] = {
            "dataset_status": manifest["status"],
            "case_count": len(cases),
            "dataset_validity": manifest["generation"]["validity"],
            "case_validity": all(case["sut_payload"]["validity"] == "SIMULATION_ONLY" for case in cases),
            "suite_status": gate["status"],
            "score_validity": gate["evidence"]["score"]["validity"],
            "exposure_proven": gate["evidence"]["exposure_proven"],
            "telemetry_complete": gate["evidence"]["telemetry_complete"],
            "replay_sha256": gate["evidence"]["replay_sha256"],
            "claim_boundary": validity["status"],
            "real_human_inference": validity["real_human_inference"],
        }
    artifact = {"gate": "M8", "status": "PASS", "returncode": 0, "evidence": evidence}
    path = root / "artifacts" / "gates" / "M8.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert all(
        item["dataset_status"] == "FROZEN"
        and item["case_count"] == 12
        and item["dataset_validity"] == "SIMULATION_ONLY"
        and item["case_validity"]
        and item["suite_status"] == "PASS"
        and item["score_validity"] == "SIMULATION_ONLY"
        and item["exposure_proven"]
        and item["telemetry_complete"]
        and item["claim_boundary"] == "SIMULATION_ONLY"
        and not item["real_human_inference"]
        for item in evidence.values()
    )
