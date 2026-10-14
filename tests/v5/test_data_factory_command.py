from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from ioabench.models import ModelProfile
from ioabench.errors import ProviderTransientError
from ioabench.v5.ai_generation.factory import read_json
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.runtime_adapter import RuntimeGenerationAdapter
from ioabench.v5.evaluation import atomic_json


ROOT = Path(__file__).resolve().parents[2]


def _command(monkeypatch, runs):
    monkeypatch.syspath_prepend(str(ROOT / "scripts" / "v5"))
    spec = importlib.util.spec_from_file_location("data_factory_command_under_test",
                                                ROOT / "scripts" / "v5" / "data_factory.py")
    assert spec and spec.loader
    command = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(command)
    monkeypatch.setattr(command, "RUNS", runs)
    monkeypatch.setattr(command, "code_hash", lambda: "fixed-source-hash")
    return command


def _args(*, run_id="test-run", trials=2):
    return SimpleNamespace(run_id=run_id, suite=["T331"], typed=True, trials=trials,
                           seed=91, generator="generator-1", auditor="auditor-1")


def _terminal(directory, *, status="REJECTED", new_family=False, pair=None):
    directory.mkdir(parents=True, exist_ok=True)
    atomic_json(directory / "MANIFEST.json", {"fixture": True})
    files = ["MANIFEST.json"]
    if status == "MACHINE_ACCEPTED":
        for name in ("BLUEPRINT.json", "PAIR.json", "HARD_GATE.json", "FIDELITY.json",
                     "REFERENCE_RESULTS.json", "DIVERSITY.json", "REVIEW_INPUT.json", "REVIEW.json",
                     "GENERATOR_REQUEST.json", "GENERATOR_RESPONSE.json", "AUDITOR_REQUEST.json", "AUDITOR_RESPONSE.json"):
            atomic_json(directory / name, {"fixture": True})
            files.append(name)
    if pair:
        atomic_json(directory / "PAIR.json", [case.as_dict() for case in pair])
        if "PAIR.json" not in files:
            files.append("PAIR.json")
    result = {"status": status, "suite_id": "T331-DYNA", "new_family": new_family,
              "evidence_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                  for name in files}}
    atomic_json(directory / "RESULT.json", result)
    return result


def _no_provider(*args, **kwargs):
    raise AssertionError("provider preparation or call must not occur")


def test_terminal_candidates_rebuild_missing_aggregate_without_provider(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path)
    directory = tmp_path / "test-run"
    accepted = _terminal(directory / "candidate-01", status="MACHINE_ACCEPTED", new_family=True)
    rejected = _terminal(directory / "candidate-02")
    before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    monkeypatch.setattr(command, "prepare_models", _no_provider)
    monkeypatch.setattr(command, "run_candidate", _no_provider)

    state = asyncio.run(command.live(directory, _args()))

    assert state["status"] == "COMPLETED_SMALL_TRIALS"
    assert state["outcomes"] == [accepted, rejected]
    assert state["accepted"] == state["new_reference_structures"] == 1
    assert state["new_qualified_global_families"] == 0
    assert read_json(directory / "RUN_STATE.json") == state
    assert asyncio.run(command.live(directory, _args())) == state
    assert all((directory / path).read_bytes() == content for path, content in before.items())


def test_terminal_aggregate_reconstruction_checks_bound_evidence(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path)
    directory = tmp_path / "test-run"
    _terminal(directory / "candidate-01")
    (directory / "candidate-01" / "MANIFEST.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    monkeypatch.setattr(command, "prepare_models", _no_provider)
    with pytest.raises(ValueError, match="evidence changed"):
        asyncio.run(command.live(directory, _args(trials=1)))
    assert not (directory / "RUN_STATE.json").exists()


def test_frozen_baseline_survives_interruption_and_new_accepted_runs(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path)
    directory = tmp_path / "test-run"
    profiles = {"generator": ModelProfile("mock", "generator-1", {}, {}, role="GENERATOR"),
                "auditor": ModelProfile("mock", "auditor-1", {}, {}, role="INDEPENDENT_AUDITOR")}
    prepared = []
    monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: object())
    monkeypatch.setattr(command, "_load_api_key", lambda: "test-key-not-used")

    async def prepare(port, run_directory, generator, auditor):
        prepared.append((generator, auditor))
        return [], profiles, {"generator": {}, "auditor": {}}

    monkeypatch.setattr(command, "prepare_models", prepare)
    original_baseline = command.baseline_cases
    baseline_reads = []

    def baseline(spec, run_id, prior_candidates=0):
        baseline_reads.append((spec.suite_id, run_id))
        return original_baseline(spec, run_id, prior_candidates)

    monkeypatch.setattr(command, "baseline_cases", baseline)
    seen_references = []
    interrupted = False

    async def candidate(candidate_directory, spec, **kwargs):
        nonlocal interrupted
        seen_references.append([case.as_dict() for case in kwargs["references"]])
        if candidate_directory.name == "candidate-02" and not interrupted:
            interrupted = True
            raise RuntimeError("simulated process interruption")
        result_path = candidate_directory / "RESULT.json"
        return read_json(result_path) if result_path.exists() else _terminal(candidate_directory)

    monkeypatch.setattr(command, "run_candidate", candidate)
    with pytest.raises(RuntimeError, match="interruption"):
        asyncio.run(command.live(directory, _args()))
    baseline_before = (directory / "BASELINES.json").read_bytes()

    spec = suite_spec("T331", typed=True)
    _terminal(tmp_path / "later-run" / "candidate-01", status="MACHINE_ACCEPTED",
              pair=spec.slice_module.generate(seed=123, families=1)[0])
    assert len(original_baseline(spec, "new-run")) > len(read_json(directory / "BASELINES.json")["T331"])

    state = asyncio.run(command.live(directory, _args()))
    assert state["status"] == "COMPLETED_SMALL_TRIALS"
    assert (directory / "BASELINES.json").read_bytes() == baseline_before
    assert baseline_reads == [("T331-DYNA", "test-run")]
    assert len(prepared) == 1
    assert len(seen_references) == 4
    assert all(references == seen_references[0] for references in seen_references)


def test_new_baseline_rejects_mutated_accepted_pair_evidence(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path)
    spec = suite_spec("T331", typed=True)
    prior = tmp_path / "prior-run" / "candidate-01"
    pair = spec.slice_module.generate(seed=123, families=1)[0]
    _terminal(prior, status="MACHINE_ACCEPTED", pair=pair)
    changed = read_json(prior / "PAIR.json")
    changed[0]["world"]["brief"] += " Historical evidence was edited."
    atomic_json(prior / "PAIR.json", changed)
    with pytest.raises(ValueError, match="evidence changed"):
        command.baseline_cases(spec, "new-run")


@pytest.mark.parametrize("operation", ["source_hashes", "case_pool"])
def test_missing_historical_reference_is_never_silently_skipped(monkeypatch, tmp_path, operation):
    command = _command(monkeypatch, tmp_path / "runs")
    monkeypatch.setattr(command, "ROOT", tmp_path)
    monkeypatch.setattr(command, "historical_paths", lambda suite: [tmp_path / "missing-cases.jsonl"])
    with pytest.raises(FileNotFoundError):
        if operation == "source_hashes":
            command.baseline_sources(["T331"])
        else:
            command.baseline_cases(suite_spec("T331", typed=True), "new-run")


@pytest.mark.parametrize("changed", ["BASELINES.json", "BASELINE_SOURCES.json", "BASELINE_MANIFEST.json"])
def test_cached_baseline_mutation_stops_before_provider(monkeypatch, tmp_path, changed):
    command = _command(monkeypatch, tmp_path / "runs")
    directory = tmp_path / "runs" / "test-run"
    directory.mkdir(parents=True)
    command.offline(directory, ["T331"], typed=True)
    atomic_json(directory / "SOURCE_MANIFEST.json", {"fixture": True})
    if changed == "BASELINE_MANIFEST.json":
        (directory / changed).unlink(missing_ok=True)
    else:
        value = read_json(directory / changed)
        if changed == "BASELINES.json":
            value["T331"].pop()
        else:
            value[next(iter(value))] = "0" * 64
        atomic_json(directory / changed, value)
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    monkeypatch.setattr(command, "prepare_models", _no_provider)
    monkeypatch.setattr(command, "_load_api_key", _no_provider)
    with pytest.raises(ValueError, match="baseline"):
        asyncio.run(command.live(directory, _args(trials=1)))
    assert not list(directory.glob("candidate-*"))


def test_typed_offline_runs_world_compilers_and_reproduces_each_pair(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path)
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    monkeypatch.setattr(command, "prepare_models", _no_provider)
    original_spec, original_compile = command.suite_spec, command.compile_and_gate
    resolved = []
    compiled = []

    def typed_spec(suite, *, typed=False):
        spec = original_spec(suite, typed=typed)
        assert typed and not isinstance(spec.adapter, RuntimeGenerationAdapter)
        resolved.append(suite)
        return spec

    def compile_pair(spec, blueprint, *, seed):
        assert "suite_payload" in blueprint and "world_edits" not in blueprint
        compiled.append((spec.suite_id, seed))
        return original_compile(spec, blueprint, seed=seed)

    monkeypatch.setattr(command, "suite_spec", typed_spec)
    monkeypatch.setattr(command, "compile_and_gate", compile_pair)
    report = command.offline(tmp_path, ["T312", "T331", "T352"], typed=True)
    assert resolved == ["T312", "T331", "T352"]
    assert len(compiled) == 12 and len(report["checks"]) == 6
    assert all(check["passed"] and check["difficulty"] == "M" for check in report["checks"])
    assert report["provider_calls"] == 0
    assert read_json(tmp_path / "PREFLIGHT.json") == report


@pytest.mark.parametrize("suites", [["T311"], ["T321"], ["T361"], ["all"], ["T312", "T363"]])
def test_unsupported_typed_cli_rejected_before_lock_or_model_preparation(monkeypatch, tmp_path, suites):
    command = _command(monkeypatch, tmp_path)
    monkeypatch.setattr(command, "_lock", _no_provider)
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    monkeypatch.setattr(command, "prepare_models", _no_provider)
    monkeypatch.setattr(command, "_load_api_key", _no_provider)
    monkeypatch.setattr(command.sys, "argv", ["data_factory.py", "--run-id", "unsupported",
                                              "--mode", "live", "--typed", "--suite", *suites])
    with pytest.raises(SystemExit) as excinfo:
        command.main()
    assert excinfo.value.code == 2
    assert not list(tmp_path.iterdir())


def _small_source(monkeypatch, command, directory):
    historical_sources = {path.relative_to(command.ROOT): path.read_bytes()
                          for path in command.historical_paths("T331")}
    directory.mkdir()
    files = {"src/module.py": "VALUE = 1\n", "contracts/rule.md": "Frozen rule\n",
             "config/settings.json": "{}\n", "scripts/v5/entry.py": "print('fixture')\n",
             "pyproject.toml": "[project]\nname = 'fixture'\n",
             "requirements.txt": "pytest\n"}
    for name, content in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for name in (".env", "config/.env", "config/.env.private", "src/__pycache__/cache.pyc"):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("excluded fixture", encoding="utf-8")
    for name, content in historical_sources.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    monkeypatch.setattr(command, "ROOT", directory)
    return files


def test_source_archive_hashes_crc_and_missing_manifest_recovery(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path / "runs")
    source = tmp_path / "source"
    expected = _small_source(monkeypatch, command, source)
    directory = tmp_path / "evidence"
    directory.mkdir()
    command.archive_source(directory)
    manifest = read_json(directory / "SOURCE_MANIFEST.json")
    archive_bytes = (directory / "source.zip").read_bytes()
    assert manifest["archive_sha256"] == hashlib.sha256(archive_bytes).hexdigest()
    assert manifest["source_sha256"] == "fixed-source-hash"
    assert manifest["file_count"] == len(expected)
    with zipfile.ZipFile(directory / "source.zip") as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(expected)
        assert manifest["files"] == {name: hashlib.sha256(archive.read(name)).hexdigest()
                                     for name in expected}
    (directory / "SOURCE_MANIFEST.json").unlink()
    command.archive_source(directory)
    assert (directory / "source.zip").read_bytes() == archive_bytes
    assert read_json(directory / "SOURCE_MANIFEST.json") == manifest
    (source / "src/module.py").write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="immutable run contract"):
        command.archive_source(directory)
    assert (directory / "source.zip").read_bytes() == archive_bytes


def test_model_preparation_provider_failure_retains_zero_generation_diagnostic(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path / "runs")
    _small_source(monkeypatch, command, tmp_path / "source")
    directory = tmp_path / "runs" / "test-run"
    directory.mkdir(parents=True)
    calls = []
    monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: object())
    monkeypatch.setattr(command, "_load_api_key", lambda: "unused-test-key")
    monkeypatch.setattr(command, "run_candidate", _no_provider)

    async def failed_preparation(port, run_directory, generator, auditor):
        calls.append((generator, auditor))
        assert (run_directory / "source.zip").exists()
        assert (run_directory / "SOURCE_MANIFEST.json").exists()
        raise ProviderTransientError("HTTP 503 model catalog fixture")

    monkeypatch.setattr(command, "prepare_models", failed_preparation)
    state = asyncio.run(command.live(directory, _args(trials=1)))
    assert len(calls) == 1
    assert state["status"] == "DIAGNOSIS_REQUIRED"
    assert state["failed_stage"] == "MODEL_PREPARATION"
    assert state["error_type"] == "ProviderTransientError"
    assert state["outcomes"] == [] and state["accepted"] == 0
    assert state["new_qualified_global_families"] == 0
    assert read_json(directory / "RUN_STATE.json") == state
    assert not list(directory.glob("candidate-*"))
    events = [json.loads(line) for line in (directory / "EXECUTION_LOG.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event"] == "MODEL_PREPARATION_FAILED"
    assert events[-1]["error_type"] == "ProviderTransientError"


@pytest.mark.parametrize("key,field,value", [
    ("generator", "role", "TESTED_MODEL"),
    ("auditor", "role", "GENERATOR"),
    ("generator", "model_id", "different-generator"),
    ("auditor", "model_id", "different-auditor"),
])
def test_cached_wrong_role_or_id_never_runs_candidate(monkeypatch, tmp_path, key, field, value):
    command = _command(monkeypatch, tmp_path / "runs")
    _small_source(monkeypatch, command, tmp_path / "source")
    directory = tmp_path / "runs" / "test-run"
    directory.mkdir(parents=True)
    profiles = {"generator": asdict(ModelProfile("mock", "generator-1", {}, {}, role="GENERATOR")),
                "auditor": asdict(ModelProfile("mock", "auditor-1", {}, {}, role="INDEPENDENT_AUDITOR"))}
    profiles[key][field] = value
    atomic_json(directory / "MODEL_PREPARATION.json", {"catalog": [], "profiles": profiles,
                                                        "parameters": {"generator": {}, "auditor": {}}})
    monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: object())
    monkeypatch.setattr(command, "_load_api_key", lambda: "unused-test-key")
    monkeypatch.setattr(command, "prepare_models", _no_provider)
    monkeypatch.setattr(command, "run_candidate", _no_provider)
    with pytest.raises(ValueError, match="cached model roles/identities"):
        asyncio.run(command.live(directory, _args(trials=1)))
    assert not list(directory.glob("candidate-*"))
