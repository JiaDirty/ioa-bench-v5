import json
from pathlib import Path


def test_m0_gate_artifact_records_required_evidence() -> None:
    artifact_path = Path(__file__).parents[2] / "artifacts" / "gates" / "M0.json"
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert artifact["gate"] == "M0"
    assert artifact["status"] == "PASS"
    assert artifact["returncode"] == 0
    assert artifact["evidence"]["oracle_hidden"] is True
    assert artifact["evidence"]["public_internet_disabled"] is True
