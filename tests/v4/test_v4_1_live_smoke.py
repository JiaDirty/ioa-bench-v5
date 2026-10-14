from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _module():
    path = ROOT / "scripts/v4_1_7_live_smoke.py"
    spec = importlib.util.spec_from_file_location("v4_1_live_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_sample_is_deterministic_and_noncanonical():
    module = _module()
    cases = module.select_cases()
    assert [(c["difficulty"], c["provenance"]["condition"]) for c in cases] == [
        ("easy", "CONTROL"), ("medium", "RISK"), ("hard", "CONTROL")]


def test_smoke_validation_rejects_retryable_or_wrong_call_count():
    module = _module()
    release = {"release_id": "v4.1.7-corrective-integration-20261002"}
    base = [{"case_id": f"c{i}", "status": "COMPLETED", "attempt_no": 1,
             "replay": {"model_records": [{"x": 1}, {"x": 2}]}} for i in range(3)]
    assert module.validate_results(base, release, "a" * 64)["pass"] is True
    bad = [dict(base[0], status="RETRYABLE_INFRA_FAILURE"), *base[1:]]
    assert module.validate_results(bad, release, "a" * 64)["pass"] is False


def test_smoke_never_marks_formal_canonical():
    text = (ROOT / "scripts/v4_1_7_live_smoke.py").read_text(encoding="utf-8")
    assert '"formal_canonical": False' in text
