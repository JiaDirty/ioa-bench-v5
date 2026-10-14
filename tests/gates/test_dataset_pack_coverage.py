import json
from collections import Counter
from pathlib import Path

from tests.formal_dataset_support import SUITES, load_formal


def test_formal_dataset_pack_has_declared_coverage() -> None:
    root = Path(__file__).parents[2]
    report = {"status": "PASS", "suites": {}, "total_cases": 0}
    for suite in SUITES:
        manifest, cases = load_formal(root, suite)
        difficulties = Counter(case["difficulty"] for case in cases)
        report["suites"][suite] = {
            "version": manifest["version"],
            "content_sha256": manifest["content_sha256"],
            "case_count": len(cases),
            "difficulty": dict(difficulties),
            "mechanisms": sorted({case["mechanism_id"] for case in cases}),
            "worlds": sorted({case["world_id"] for case in cases}),
        }
        report["total_cases"] += len(cases)
        assert manifest["status"] == "FROZEN"
        assert len(cases) == 90
        assert difficulties == Counter({"easy": 30, "medium": 30, "hard": 30})
        assert len(report["suites"][suite]["mechanisms"]) == 5
        assert len(report["suites"][suite]["worlds"]) == 3
    path = root / "artifacts" / "datasets" / "v1-coverage-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert report["total_cases"] == 1620
