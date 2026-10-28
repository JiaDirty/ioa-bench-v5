"""Retained candidates must be in history before a newly reordered plan starts."""
import asyncio
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


def test_new_task_checks_retained_later_task_from_same_plan(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("development_history_batch_test", scripts / "run_development_factory.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    out = tmp_path / "out"
    retained = out / "candidates/retained-B"
    retained.mkdir(parents=True)
    (retained / "RESULT.json").write_text("{}", encoding="utf-8")
    (retained / "TERMINAL.json").write_text("{}", encoding="utf-8")
    plan = tmp_path / "new-plan.json"
    plan.write_text(json.dumps({"tasks": [{"id": "new-C", "suite": "T331"},
                                         {"id": "retained-B", "suite": "T331"}]}), encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "policy_for", lambda path: {})
    monkeypatch.setattr(module, "snapshot", lambda path: "frozen")
    monkeypatch.setattr(module, "source_tree_hash", lambda path: "frozen")
    monkeypatch.setattr(module, "prepare_history", lambda path: {"records": []})
    monkeypatch.setattr(module, "candidate_result", lambda path: {"status": "FAIL"})
    seen = []

    def extend(index, path):
        if path == retained and not index["records"]:
            index["records"].append({"features": {"retained": "B"}})

    async def study_for(path):
        return SimpleNamespace(out=out, stop=out / "STOP.json")

    async def generate(study, task, index, references, **kwargs):
        seen.append(task["id"])
        assert {"retained": "B"} in references
        assert index["records"][0]["features"] == {"retained": "B"}
        return {"status": "FAIL", "failed_stage": "HISTORY_DUPLICATE"}

    monkeypatch.setattr(module, "extend_history", extend)
    monkeypatch.setattr(module, "study_for", study_for)
    monkeypatch.setattr(module, "generate_candidate", generate)
    assert asyncio.run(module.run(out, "generate", plan)) == {"FAIL": 2}
    assert seen == ["new-C"]


def test_two_t322_history_scopes_are_preserved_and_later_task_still_runs(tmp_path, monkeypatch):
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.ai_generation.history import HISTORY_VERSION
    from ioabench.v5.ai_generation.quality import QUALITY_VERSION
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("development_t322_scope_test", scripts / "run_development_factory.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    out = tmp_path / "out"
    plan = tmp_path / "two-scopes.json"
    tasks = [{"id": "T322-first", "suite": "T322"}, {"id": "T322-second", "suite": "T322"},
             {"id": "T331-after", "suite": "T331"}]
    plan.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "policy_for", lambda path: {})
    monkeypatch.setattr(module, "snapshot", lambda path: "frozen")
    monkeypatch.setattr(module, "source_tree_hash", lambda path: "frozen")
    history = {"index_version": HISTORY_VERSION, "feature_version": QUALITY_VERSION,
               "projection_source_sha256": "frozen", "records": [], "findings": [],
               "source_sha256": {}, "scope": {}, "summary": {}}
    monkeypatch.setattr(module, "prepare_history", lambda path: history)
    seen = []
    async def study_for(path):
        return SimpleNamespace(out=out, stop=out / "STOP.json")
    async def generate(study, task, index, references, **kwargs):
        seen.append(task["id"])
        return {"status": "FAIL", "failed_stage": "HISTORY_DUPLICATE"}
    def extend(index, source):
        index["records"].append({"case_sha256": source.name,
            "features": {"suite_id": source.name[:4], "runtime_verified": True},
            "occurrences": [{"status": "FAIL"}]})
    monkeypatch.setattr(module, "study_for", study_for)
    monkeypatch.setattr(module, "generate_candidate", generate)
    monkeypatch.setattr(module, "extend_history", extend)
    assert asyncio.run(module.run(out, "generate", plan)) == {"FAIL": 3}
    assert seen == [task["id"] for task in tasks]
    reports = [json.loads(path.read_text()) for path in out.glob("T322_VERSION_SCOPE-*.json")]
    assert len(reports) == 2
    assert len({row["full_history_index_sha256"] for row in reports}) == 2
    assert {row["retained_t322_cases"] for row in reports} == {0, 1}
    for report in reports:
        digest = report["full_history_index_sha256"]
        full = json.loads((out / "history" / ("overlay-" + digest + ".json")).read_text())
        assert canonical_sha256(full) == digest
        assert "t322_development_scope" not in full["scope"]


@pytest.fixture
def recovery_fixture(tmp_path, monkeypatch):
    from ioabench.hashing import canonical_sha256
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.v5.ai_generation import quality
    from ioabench.v5.ai_generation.acquisition import program_proposal
    from ioabench.v5.ai_generation.direct_deepseek import SCOPE
    from ioabench.v5.ai_generation.history import HISTORY_VERSION
    from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
    from ioabench.v5.ai_generation.t322_history import version_scoped_index
    from ioabench.v5.core.case import case_from_dict
    from ioabench.v5.evaluation import atomic_json
    workspace = Path(__file__).resolve().parents[2]
    scripts = workspace / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    import recover_development_scope as recovery
    root = tmp_path / "workspace"
    out = root / "artifacts/v5/data_factory/dev_auto_audit/fixture"
    for name in ("src", "contracts", "config"):
        shutil.copytree(workspace / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
    runtime = source_tree_hash(root)
    for name in ("src", "contracts", "config"):
        shutil.copytree(root / name, out / "source_revisions" / runtime / name)
    frozen = (scripts / "run_development_factory.py").read_bytes()
    runner_hash = hashlib.sha256(frozen).hexdigest()
    runner = out / "execution_scripts" / (runner_hash + ".py")
    runner.parent.mkdir(parents=True)
    runner.write_bytes(frozen)
    atomic_json(out / ("GENERATE_SOURCE_BINDING-" + runtime[:12] + "-" + runner_hash[:8] + ".json"),
                {"phase": "generate", "runtime_sha256": runtime, "script_sha256": runner_hash})
    base = {"index_version": HISTORY_VERSION, "feature_version": quality.QUALITY_VERSION,
            "projection_source_sha256": runtime, "records": [{"case_sha256": "legacy-t322",
                "features": {"suite_id": "T322", "runtime_verified": False},
                "occurrences": [{"source": "synthetic fixture", "status": "OLD"}]}],
            "findings": [], "source_sha256": {}, "scope": {}, "summary": {"unique_cases": 1}}
    base_path = out / "history" / (runtime + ".json")
    atomic_json(base_path, base)
    atomic_json(out / ("HISTORY_BINDING-" + runtime[:12] + ".json"),
                {"history_path": base_path.relative_to(out).as_posix(), "sha256": recovery.sha(base_path)})
    tasks = [{"id": "first", "suite": "T331", "seed": 193},
             {"id": "scope-first", "suite": "T322", "seed": 211},
             {"id": "scope-second", "suite": "T322", "seed": 223}]
    atomic_json(out / "plans/frozen.json", {"tasks": tasks})
    extend = recovery.frozen_extend(runner, root, case_from_dict, suite_spec, quality.dedup_features)
    index, full_hashes = deepcopy(base), []
    for task in tasks:
        if task["suite"] == "T322":
            selected, report = version_scoped_index(index)
            full_hashes.append(canonical_sha256(index))
            atomic_json(out / ("T322_VERSION_SCOPE-" + report["full_history_index_sha256"] + ".json"), report)
        else:
            selected = index
        selected_hash = canonical_sha256(selected)
        atomic_json(out / "history" / ("overlay-" + selected_hash + ".json"), selected)
        spec = suite_spec(task["suite"], typed=True)
        compiled = compile_and_gate(spec, program_proposal(spec, seed=task["seed"], difficulty="M"), seed=task["seed"])
        directory = out / "candidates" / task["id"]
        atomic_json(directory / "MANIFEST.json", {"source_sha256": runtime, "task": task, "history_sha256": selected_hash})
        atomic_json(directory / "PAIR.json", [compiled[arm].as_dict() for arm in ("control", "risk")])
        result = {"status": "FAIL", "scope": SCOPE, "formal_accepted": False, "machine_qualified": False,
                  "evidence_sha256": {name: recovery.sha(directory / name) for name in ("MANIFEST.json", "PAIR.json")}}
        atomic_json(directory / "RESULT.json", result)
        atomic_json(directory / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})
        extend(index, directory)
    (out / "REQUEST_LEDGER.jsonl").write_text('{"event":"SYNTHETIC_NO_PROVIDER"}\n', encoding="utf-8")
    return root, out, full_hashes, recovery


def test_scope_recovery_reconstructs_each_exact_full_index_without_resending(recovery_fixture):
    from ioabench.hashing import canonical_sha256
    root, out, full_hashes, recovery = recovery_fixture
    assert all(not (out / "history" / ("overlay-" + digest + ".json")).exists() for digest in full_hashes)
    before = {path.relative_to(root).as_posix(): recovery.sha(path) for path in out.rglob("*") if path.is_file()}
    script = Path(__file__).resolve().parents[2] / "scripts/v5/recover_development_scope.py"
    process = subprocess.run([sys.executable, "-B", str(script), "--root", str(root), "--out", str(out)],
                             capture_output=True, text=True, timeout=120)
    assert process.returncode == 0, process.stderr
    result = recovery.read(out / "T322_FULL_INDEX_RECOVERY_V1.json")
    assert result["method"] == "POST_RUN_DETERMINISTIC_RECONSTRUCTION"
    assert result["original_persistence_claim"] is False and result["ledger_unchanged"] is True
    assert result["provider_calls"] == result["new_generation_requests"] == 0
    assert result["network_guard"]["provider_http_or_external_network_attempts"] == 0
    assert [row["candidate_status"] for row in result["steps"]] == ["FAIL"] * 3
    assert len(result["recovered_files"]) == len(full_hashes) == 2
    for digest in full_hashes:
        full = recovery.read(out / "history" / ("overlay-" + digest + ".json"))
        assert canonical_sha256(full) == digest
        assert "t322_development_scope" not in full["scope"]
    assert all(recovery.sha(root / name) == digest for name, digest in before.items())


@pytest.mark.parametrize("corruption", ["scope", "existing_full_index"])
def test_scope_recovery_rejects_mismatched_report_before_writing(recovery_fixture, corruption):
    root, out, full_hashes, recovery = recovery_fixture
    if corruption == "scope":
        scope = sorted(out.glob("T322_VERSION_SCOPE-*.json"))[0]
        value = recovery.read(scope)
        value["dev_accepted_allowed"] = True
        scope.write_text(json.dumps(value), encoding="utf-8")
        message = "does not match the recorded T322 scope"
        unchanged = None
    else:
        path = out / "history" / ("overlay-" + full_hashes[-1] + ".json")
        path.write_text('{"mismatched":"must not overwrite"}', encoding="utf-8")
        unchanged = path.read_bytes()
        message = "existing full-index artifact differs"
    script = Path(__file__).resolve().parents[2] / "scripts/v5/recover_development_scope.py"
    process = subprocess.run([sys.executable, "-B", str(script), "--root", str(root), "--out", str(out)],
                             capture_output=True, text=True, timeout=120)
    assert process.returncode != 0 and message in process.stderr
    assert not (out / "T322_FULL_INDEX_RECOVERY_V1.json").exists()
    assert not (out / "history" / ("overlay-" + full_hashes[0] + ".json")).exists()
    if unchanged is not None:
        assert path.read_bytes() == unchanged
    else:
        assert not (out / "history" / ("overlay-" + full_hashes[-1] + ".json")).exists()
