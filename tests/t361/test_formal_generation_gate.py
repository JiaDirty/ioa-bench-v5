import json
from collections import Counter
from pathlib import Path


def test_t361_formal_candidates_are_balanced_simulation_only() -> None:
    root = Path(__file__).resolve().parents[2] / "data" / "datasets" / "T361" / "v1-candidates"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (root / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    rejected = [json.loads(line) for line in (root / "rejected.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert manifest["generation"]["candidate_target_min"] >= 220
    assert manifest["generation"]["validity"] == "SIMULATION_ONLY"
    assert len(cases) == 90
    assert Counter(case["difficulty"] for case in cases) == {"easy": 30, "medium": 30, "hard": 30}
    assert len({case["mechanism_id"] for case in cases}) >= 4
    assert all(case["sut_payload"]["validity"] == "SIMULATION_ONLY" for case in cases)
    assert rejected and all(item.get("reason") for item in rejected)
