"""The publication-readiness inventory must fail closed until required gates exist."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _audit():
    path = ROOT / "scripts" / "v5" / "publication_readiness_audit.py"
    spec = importlib.util.spec_from_file_location("publication_readiness_audit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readiness_audit_is_fail_closed() -> None:
    report = _audit().build_audit(ROOT)
    assert report["formal_model"] == "deepseek-v4.1-flash"
    assert report["publication_ready"] is False
    assert report["gates"]["C"]["automated_evidence"] is True
    assert report["gates"]["D"]["status"] == "BLOCKED_EXTERNAL_REVIEW"
    assert report["gates"]["E"]["status"] == "PENDING_APPROVED_CONFIRMATION"
