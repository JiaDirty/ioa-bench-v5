import json
from collections import Counter
from pathlib import Path

from ioabench.hashing import canonical_sha256


def test_t323_1_1_0_is_balanced_and_content_addressed() -> None:
    root = Path(__file__).resolve().parents[2] / "data" / "datasets" / "T323" / "1.1.0"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (root / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert manifest["version"] == "1.1.0"
    assert len(cases) == 90
    assert Counter(case["difficulty"] for case in cases) == {"easy": 30, "medium": 30, "hard": 30}
    assert manifest["quality_gates"]["semantic_validation"] == "DUAL_VALIDATOR"
    assert manifest["content_sha256"] == canonical_sha256({"manifest": {**manifest, "content_sha256": None}, "cases": cases})
