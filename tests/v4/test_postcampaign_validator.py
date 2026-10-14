from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_terminal_partial_cases_remain_strictly_bound():
    path = ROOT / "scripts/v4_1_13_postcampaign_validate_run.py"
    spec = importlib.util.spec_from_file_location("v4_1_13_postcampaign_validate_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    release = json.loads(module.RELEASE_PATH.read_text(encoding="utf-8"))

    for suite in ("T323", "T361", "T362", "T363"):
        result = module.validate_suite(release, suite)
        assert result["binding_level"] == "STRICT_BINDING", result["failures"]
