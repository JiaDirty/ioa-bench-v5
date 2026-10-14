import json
from pathlib import Path
from typing import Any

from tests.formal_dataset_support import SUITES, content_hash, expose_case, load_formal


def _contains_hidden(value: Any) -> bool:
    hidden = {"oracle", "oracle_payload", "ground_truth", "truth", "attack_label", "scoring_rules"}
    if isinstance(value, dict):
        return any(str(key).casefold() in hidden or _contains_hidden(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_hidden(item) for item in value)
    return False


def test_formal_dataset_pack_passes_integrity_preflight() -> None:
    root = Path(__file__).parents[2]
    report = {"status": "PASS", "suites": {}}
    for suite in SUITES:
        manifest, cases = load_formal(root, suite)
        assert manifest["content_sha256"] == content_hash(manifest, cases)
        assert all(case["oracle_payload"]["exposure_reachable"] and case["oracle_payload"]["control_solvable"] for case in cases)
        assert all(not _contains_hidden(case["sut_payload"]) for case in cases)
        if suite in {"T361", "T362", "T363"}:
            assert manifest["generation"]["validity"] == "SIMULATION_ONLY"
            assert all(case["sut_payload"]["validity"] == "SIMULATION_ONLY" for case in cases)
        assert all(expose_case(suite, case) for case in cases[::30])
        report["suites"][suite] = {"hash": manifest["content_sha256"], "exposure_preflight": True, "case_count": len(cases)}
    path = root / "artifacts" / "datasets" / "v1-integrity-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
