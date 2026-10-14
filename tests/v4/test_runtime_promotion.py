from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v4_runtime_promotion_is_exact_and_history_delta_is_bounded():
    path = ROOT / "scripts/v4_1_13_verify_runtime_promotion.py"
    spec = importlib.util.spec_from_file_location("v4_verify_runtime_promotion", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.audit()
    post_campaign_checks = {
        key: value for key, value in report["checks"].items()
        if key not in {"no_successor_formal_runs_yet", "no_successor_smoke_gate_yet"}
    }
    assert all(post_campaign_checks.values()), report
    assert len(report["existing_successor_formal_runs"]) == 18
    assert report["successor_smoke_gate_exists"] is True
    assert report["unexpected_baseline_changes"] == []
    assert report["actual_baseline_changes"] == report["expected_promoted_files"]
