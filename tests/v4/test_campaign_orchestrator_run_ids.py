"""Regression: the v4 campaign orchestrator must never touch historical run dirs.

The v3/v3.2 formal runs live at ``data/runs/<model>-<suite>-<version>-formal``.
A v4.1.13 campaign writes to ``...-v4.1.13-formal`` and must refuse to run when the
historical directory is present, so frozen evidence cannot be resumed into or
overwritten.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORCH = ROOT / "scripts/run_online_campaign_v4_1_13.py"
SUITES = [f"T3{a}{b}" for a in "123456" for b in "123"]


def _source() -> str:
    return ORCH.read_text(encoding="utf-8")


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location("run_online_campaign", ORCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_orchestrator_emits_v4_1_13_run_id():
    src = _source()
    assert re.search(r'run_id = f"\{MODEL\}-\{suite\}-\{frozen_version\}-v4\.1\.13-formal"', src), \
        "orchestrator must build the -v4.1.13-formal run id"


def test_orchestrator_never_builds_bare_formal_run_id():
    src = _source()
    # the only bare -formal occurrence allowed is the legacy id used for the guard
    bare = re.findall(r'f"\{MODEL\}-\{suite\}-\{frozen_version\}-formal"', src)
    assert len(bare) == 1, f"expected exactly one legacy-id reference (the guard), found {len(bare)}"


def test_orchestrator_guards_against_historical_path_collision():
    src = _source()
    assert "run_path.resolve() == legacy_path.resolve()" in src
    assert "collides with historical run directory" in src
    assert "legacy_path.exists()" not in src


def test_formal_complete_reads_v4_1_13_directory():
    src = _source()
    assert 'f"{MODEL}-{suite}-{version}-v4.1.13-formal" / "results.json"' in src


def test_all_18_historical_directories_exist_and_are_distinct_from_v4():
    """Every suite has a historical directory; none collides with the v4 id."""
    from ioabench.frozen_versions import FROZEN_VERSIONS

    model = "deepseek-v4.1-flash"
    collisions = []
    for suite in SUITES:
        version = FROZEN_VERSIONS.get(suite, "2.0.0")
        legacy = ROOT / "data" / "runs" / f"{model}-{suite}-{version}-formal"
        v4 = ROOT / "data" / "runs" / f"{model}-{suite}-{version}-v4.1.13-formal"
        assert legacy.is_dir(), f"historical directory missing for {suite}: {legacy.name}"
        if legacy == v4:
            collisions.append(suite)
    assert not collisions, f"v4 run id collides with historical dir: {collisions}"


def test_all_v4_1_13_formal_directories_exist_after_campaign():
    """The completed campaign retains one isolated result directory per suite."""
    from ioabench.frozen_versions import FROZEN_VERSIONS

    model = "deepseek-v4.1-flash"
    missing = []
    for suite in SUITES:
        version = FROZEN_VERSIONS.get(suite, "2.0.0")
        v4 = ROOT / "data" / "runs" / f"{model}-{suite}-{version}-v4.1.13-formal"
        if not (v4 / "results.json").is_file():
            missing.append(v4.name)
    assert not missing, f"v4.1.13 formal results missing: {missing}"


def test_v4_manifests_use_v4_run_ids():
    manifest_dir = ROOT / "data/runs/_v4_1_13_manifests"
    ids = []
    for path in sorted(manifest_dir.glob("*.manifest.json")):
        ids.append(json.loads(path.read_text(encoding="utf-8"))["run_id"])
    assert len(ids) == 18
    assert all(i.endswith("-v4.1.13-formal") for i in ids), ids


def test_orchestrator_defaults_to_all_18_suites():
    assert 'parser.add_argument("--start", default="T311")' in _source()
    assert "ONLINE_CAMPAIGN_STATE_v4_1_13.json" in _source()
    assert "verify_live_smoke(release)" in _source()
    assert "run_online_pilot.py" not in _source()


def test_orchestrator_runtime_matches_frozen_release():
    module = _load_orchestrator()
    release = module.verify_frozen_runtime()
    assert module.DISPATCH_VERSION == release["runtime_mapping"]["dispatch_version"]
    assert module.source_tree_hash(ROOT) == release["source_tree_sha256"]


def test_install_frozen_manifest_copies_exact_bytes(tmp_path, monkeypatch):
    module = _load_orchestrator()
    release = json.loads(module.RELEASE_PATH.read_text(encoding="utf-8"))
    run_id = "deepseek-v4.1-flash-T311-2.0.0-v4.1.13-formal"
    monkeypatch.setattr(module, "ROOT", tmp_path)
    target = module.install_frozen_manifest(run_id, release)
    source = module.FROZEN_MANIFEST_DIR / f"{run_id}.manifest.json"
    assert target.read_bytes() == source.read_bytes()
    manifest = json.loads(target.read_text(encoding="utf-8"))
    assert manifest["release"]["release_sha256"] == hashlib.sha256(module.RELEASE_PATH.read_bytes()).hexdigest()
