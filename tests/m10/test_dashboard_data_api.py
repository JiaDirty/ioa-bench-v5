import json
from pathlib import Path

from ioabench.api.dashboard import dashboard_payload


def test_dashboard_payload_exposes_six_categories(tmp_path: Path) -> None:
    run = tmp_path / "data" / "runs" / "r"
    run.mkdir(parents=True)
    (run / "results.json").write_text(json.dumps({"w": {"suite": "T361", "eligibility": "VALID", "score": {"task_success": 1.0}}}), encoding="utf-8")
    payload = dashboard_payload(tmp_path, "r")
    assert len(payload["categories"]) == 6
    assert payload["categories"]["human_agency_simulation"]["T361"]["validity"] == "SIMULATION_ONLY"
    assert "case_studies" in payload
