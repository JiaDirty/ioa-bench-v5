import json
from pathlib import Path


def test_m1_gate_records_runtime_and_provider_status() -> None:
    root = Path(__file__).parents[2]
    artifact = json.loads((root / "artifacts" / "gates" / "M1.json").read_text(encoding="utf-8"))

    assert artifact["gate"] == "M1"
    assert artifact["status"] == "PASS"
    assert artifact["returncode"] == 0
    assert artifact["evidence"]["no_silent_substitution"] is True
    assert artifact["evidence"]["live_provider_blocker_recorded"] is True
