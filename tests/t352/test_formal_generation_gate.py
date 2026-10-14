import json
from collections import Counter
from pathlib import Path


def test_t352_formal_candidates_close_quota_and_retain_rejections() -> None:
    root = Path(__file__).resolve().parents[2] / "data" / "datasets" / "T352" / "v1-candidates"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (root / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    rejected = [json.loads(line) for line in (root / "rejected.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert manifest["generation"]["candidate_target_min"] >= 220
    assert len(cases) == 90
    assert Counter(case["difficulty"] for case in cases) == {"easy": 30, "medium": 30, "hard": 30}
    assert len({case["mechanism_id"] for case in cases}) >= 4
    assert len({case["provenance"]["pair_id"].split("-")[3] for case in cases}) == 3
    assert rejected and all(item.get("reason") for item in rejected)
