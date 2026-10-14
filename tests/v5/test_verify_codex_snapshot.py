"""Tests for the Codex snapshot acceptance harness (P3 preparation): hash verification,
mainline classification, and manifest-format tolerance — exercised against synthetic
snapshot fixtures so no Codex directory is ever touched."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _harness():
    spec = importlib.util.spec_from_file_location(
        "verify_codex_snapshot", ROOT / "scripts" / "v5" / "verify_codex_snapshot.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def snapshot(tmp_path: Path) -> Path:
    snap = tmp_path / "codex-snapshot"
    (snap / "src/ioabench/v5/ai_generation").mkdir(parents=True)
    (snap / "tests/v5").mkdir(parents=True)
    (snap / "notes").mkdir(parents=True)
    (snap / "src/ioabench/v5/ai_generation/blueprint_schema.py").write_text("# snapshot version\n")
    (snap / "src/ioabench/v5/ai_generation/t321_adapter.py").write_text("# adapter\n")
    (snap / "tests/v5/test_ai_generation_probe.py").write_text("def test_x(): pass\n")
    (snap / "notes/internal_draft.md").write_text("codex-local note\n")
    files = {str(p.relative_to(snap).as_posix()): _sha(p)
             for p in snap.rglob("*") if p.is_file()}
    (snap / "MANIFEST.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    return snap


def test_accepts_intact_snapshot_and_classifies(tmp_path: Path, snapshot: Path) -> None:
    module = _harness()
    report_path = tmp_path / "report.json"
    assert module.main.__module__  # importable
    rc = _run(module, snapshot, report_path)
    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["hash_verified"] is True
    assert report["acceptance"].startswith("PASS")
    assert report["summary"]["new_vs_mainline"] >= 2  # ai_generation files are new to mainline
    assert any(c["path"].endswith("internal_draft.md") and not c["portable_integration_candidate"]
               for c in report["files"]), "codex-local notes must not be integration candidates"


def test_rejects_tampered_snapshot(tmp_path: Path, snapshot: Path) -> None:
    # tamper with one file after manifest signing
    target = snapshot / "src/ioabench/v5/ai_generation/t321_adapter.py"
    target.write_text("# TAMPERED\n")
    module = _harness()
    report_path = tmp_path / "report.json"
    rc = _run(module, snapshot, report_path)
    assert rc == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["hash_verified"] is False
    assert report["acceptance"].startswith("FAIL")
    assert any("mismatch" in f["problem"] for f in report["hash_failures"])


def test_accepts_list_style_manifest(tmp_path: Path) -> None:
    snap = tmp_path / "snap-list"
    (snap / "src/ioabench/v5/ai_generation").mkdir(parents=True)
    f = snap / "src/ioabench/v5/ai_generation/validator.py"
    f.write_text("# validator\n")
    (snap / "SNAPSHOT_HASHES.json").write_text(json.dumps(
        {"files": [{"path": "src/ioabench/v5/ai_generation/validator.py", "sha256": _sha(f)}]}),
        encoding="utf-8")
    module = _harness()
    report_path = tmp_path / "report.json"
    rc = _run(module, snap, report_path)
    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["hash_verified"] is True


def _run(module, snapshot: Path, report_path: Path) -> int:
    import sys
    argv = sys.argv
    sys.argv = ["verify_codex_snapshot.py", "--snapshot-dir", str(snapshot),
                "--out", str(report_path)]
    try:
        return module.main()
    finally:
        sys.argv = argv
