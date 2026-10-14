"""Phase F validator tests: fail-closed on missing runs, STRICT on v4-native runs.

The pass path is exercised against a synthetic v4-conformant fixture so the
validator is proven correct offline, before any provider call.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _load_validator():
    spec = importlib.util.spec_from_file_location("v4_1_7_validate_run", SCRIPTS / "v4_1_7_validate_run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v4_1_7_validate_run"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def validator():
    return _load_validator()


@pytest.fixture(scope="module")
def release(validator):
    return json.loads(validator.RELEASE_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def fixture(tmp_path):
    """A scratch v4-native run for T311 plus its manifest."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests" / "v4"))
    import _fixture_build as fb  # noqa: E402

    validator = _load_validator()
    release = json.loads(validator.RELEASE_PATH.read_text(encoding="utf-8"))
    release_sha = hashlib.sha256(validator.RELEASE_PATH.read_bytes()).hexdigest()

    runs = tmp_path / "runs"
    runs.mkdir()
    fb.build("T311", runs, release)
    fb.build_manifest("T311", tmp_path, release, release_sha)
    yield tmp_path, runs, tmp_path / "manifests", release, release_sha
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_missing_run_is_not_bound(validator, release):
    """A suite with no v4 run must fail closed and never be canonical."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        empty = pathlib.Path(td)
        (empty / "manifests").mkdir()
        rep = validator.validate_suite(release, "T311", runs_dir=empty,
                                       manifest_dir=empty / "manifests")
    assert rep["binding_level"] == "NOT_BOUND"
    assert rep["canonical_accepted"] is False
    assert any(f["name"] == "run_dir_exists" for f in rep["failures"])


def test_v4_native_run_reaches_strict_binding(validator, fixture):
    _, runs, manifests, release, release_sha = fixture
    rep = validator.validate_suite(release, "T311", runs_dir=runs,
                                   manifest_dir=manifests, release_sha=release_sha)
    assert rep["failures"] == [], rep["failures"]
    assert rep["binding_level"] == "STRICT_BINDING"
    assert rep["canonical_accepted"] is True


def test_wrong_dispatch_version_breaks_binding(validator, fixture):
    _, runs, manifests, release, release_sha = fixture
    results_path = runs / "deepseek-v4.1-flash-T311-2.0.0-v4.1-formal" / "results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    first = next(iter(data))
    data[first]["dispatch"]["dispatch_version"] = "construct-dispatch-1.0.0"
    results_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    rep = validator.validate_suite(release, "T311", runs_dir=runs,
                                   manifest_dir=manifests, release_sha=release_sha)
    assert rep["binding_level"] == "NOT_BOUND"
    assert any(f["name"] == "frozen_dispatch_version" for f in rep["failures"])


def test_non_terminal_case_breaks_binding(validator, fixture):
    _, runs, manifests, release, release_sha = fixture
    results_path = runs / "deepseek-v4.1-flash-T311-2.0.0-v4.1-formal" / "results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    first = next(iter(data))
    data[first]["status"] = "RETRYABLE_INFRA_FAILURE"
    results_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    rep = validator.validate_suite(release, "T311", runs_dir=runs,
                                   manifest_dir=manifests, release_sha=release_sha)
    assert rep["binding_level"] == "NOT_BOUND"
    assert any(f["name"] == "all_cases_terminal" for f in rep["failures"])


def test_manifest_release_mismatch_breaks_binding(validator, fixture):
    """A manifest bound to a different release must not bind."""
    _, runs, manifests, release, _ = fixture
    rep = validator.validate_suite(release, "T311", runs_dir=runs,
                                   manifest_dir=manifests, release_sha="0" * 64)
    assert rep["binding_level"] == "NOT_BOUND"
    assert any(f["name"] == "manifest_release_sha256" for f in rep["failures"])


def test_runtime_manifest_must_match_prefrozen_manifest(validator, fixture):
    _, runs, manifests, release, release_sha = fixture
    run_id = "deepseek-v4.1-flash-T311-2.0.0-v4.1-formal"
    runtime_manifest = runs / run_id / "manifest" / f"{run_id}.json"
    payload = json.loads(runtime_manifest.read_text(encoding="utf-8"))
    payload["release"]["release_id"] = "different-release"
    runtime_manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rep = validator.validate_suite(release, "T311", runs_dir=runs,
                                   manifest_dir=manifests, release_sha=release_sha)
    assert rep["binding_level"] == "NOT_BOUND"
    assert any(f["name"] == "runtime_manifest_matches_frozen" for f in rep["failures"])


def test_recorded_failure_names_the_suite(validator, fixture):
    _, runs, manifests, release, release_sha = fixture
    rep = validator.validate_suite(release, "T311", runs_dir=runs,
                                   manifest_dir=manifests, release_sha=release_sha)
    assert rep["suite"] == "T311"
    assert rep["run_id"].endswith("-v4.1-formal")


def test_t353_branch_contract_matches_frozen_runtime(validator):
    """T353 branches live under replay.scenario.paired_runs (frozen runtime).

    Guards against the validator drifting from
    ioabench/runtime/discovery_selection.py, which writes the honest/manipulated
    counterfactual bundles at that exact path.
    """
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests" / "v4"))
    import _fixture_build as fb  # noqa: E402
    import tempfile

    release = json.loads(validator.RELEASE_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        runs = tmp / "runs"
        runs.mkdir()
        fb.build("T353", runs, release)
        version = release["datasets"]["T353"]["version"]
        results = json.loads(
            (runs / f"deepseek-v4.1-flash-T353-{version}-v4.1-formal" / "results.json")
            .read_text(encoding="utf-8"))
        rep = next(iter(results.values()))["replay"]
        paired = rep["scenario"]["paired_runs"]
        assert set(paired) == {"honest", "manipulated"}
        assert all(isinstance(paired[m]["replay"], dict) for m in paired)


def test_t353_missing_branches_fail_closed(validator, tmp_path):
    """A T353 run without paired branches must NOT reach STRICT_BINDING."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests" / "v4"))
    import _fixture_build as fb  # noqa: E402

    release = json.loads(validator.RELEASE_PATH.read_text(encoding="utf-8"))
    release_sha = hashlib.sha256(validator.RELEASE_PATH.read_bytes()).hexdigest()
    runs = tmp_path / "runs"
    runs.mkdir()
    fb.build("T353", runs, release)
    fb.build_manifest("T353", tmp_path, release, release_sha)

    version = release["datasets"]["T353"]["version"]
    results_path = runs / f"deepseek-v4.1-flash-T353-{version}-v4.1-formal" / "results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    for rec in data.values():
        rec["replay"]["scenario"].pop("paired_runs", None)
    results_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    rep = validator.validate_suite(release, "T353", runs_dir=runs,
                                   manifest_dir=tmp_path / "manifests",
                                   release_sha=release_sha)
    assert rep["binding_level"] == "NOT_BOUND"
    assert any(f["name"] == "t353_three_branches" for f in rep["failures"])
