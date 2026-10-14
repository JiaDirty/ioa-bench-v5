import json
from pathlib import Path


def test_t312_dev_mini_dataset_is_frozen_and_balanced() -> None:
    root = Path(__file__).parents[2]
    dataset = root / "data" / "datasets" / "T312" / "dev-mini"
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert manifest["status"] == "FROZEN"
    assert len(cases) == 12
    assert {case["difficulty"] for case in cases} == {"easy", "medium", "hard"}
    assert {case["provenance"]["condition"] for case in cases} == {"CONTROL", "RISK"}
    assert manifest["content_sha256"]
