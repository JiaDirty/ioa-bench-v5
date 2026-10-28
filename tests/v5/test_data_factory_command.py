from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
from dataclasses import asdict
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import zipfile
from tempfile import TemporaryDirectory

import pytest

from ioabench.models import ModelProfile
from ioabench.errors import ProviderTransientError
from ioabench.v5.ai_generation.factory import read_json
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.runtime_adapter import RuntimeGenerationAdapter
from ioabench.v5.evaluation import atomic_json
from ioabench.generation.coverage import CoveragePlanner
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.history import build_index
from ioabench.runtime.full_manifest import source_tree_hash


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
    result = {"status": status, "suite_id": "T331-DYNA", "new_family": new_family, "formal_accepted": False,
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
    report = command.offline(tmp_path, ["T312", "T321", "T331", "T352"], typed=True)
    assert resolved == ["T312", "T321", "T331", "T352"]
    assert len(compiled) == 16 and len(report["checks"]) == 8
    assert all(check["passed"] and check["difficulty"] == "M" for check in report["checks"])
    assert report["provider_calls"] == 0
    assert read_json(tmp_path / "PREFLIGHT.json") == report


@pytest.mark.parametrize("suites", [["T311"], ["T322"], ["T361"], ["all"], ["T312", "T363"]])
def test_live_typed_cli_without_preflight_rejected_before_lock_or_model_preparation(monkeypatch, tmp_path, suites):
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


@pytest.mark.parametrize("typed_flag", ["--typed", "--auto-typed"])
def test_first_batch_typed_cli_reaches_offline_pipeline_without_provider(monkeypatch, tmp_path, typed_flag):
    command = _command(monkeypatch, tmp_path)
    monkeypatch.setattr(command, "_lock", lambda path: nullcontext())
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    monkeypatch.setattr(command, "prepare_models", _no_provider)
    received = []

    def offline(directory, suites, *, typed=False):
        received.append((directory, suites, typed))
        return {"status": "OFFLINE_ENGINEERING_PASS", "provider_calls": 0}

    monkeypatch.setattr(command, "offline", offline)
    monkeypatch.setattr(command.sys, "argv", ["data_factory.py", "--run-id", "first-batch",
                                              "--mode", "offline", typed_flag, "--suite",
                                              "T321", "T331", "T352"])
    assert command.main() == 0
    assert received == [(tmp_path / "first-batch", ["T321", "T331", "T352"], True)]


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
    assert manifest["runtime_source_sha256"] == source_tree_hash(source)
    assert manifest["command_sha256"] == hashlib.sha256(Path(command.__file__).read_bytes()).hexdigest()
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


def test_history_prescreen_skips_seen_combinations_without_qualifying_coverage(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path / "runs")
    spec = suite_spec("T331", typed=True)
    original = program_proposal(spec, seed=91, difficulty="M", target={"propagation_topology": "fanout"})
    control, risk = spec.adapter.compile_pair(original, seed=91)
    source = tmp_path / "PAIR.json"
    atomic_json(source, [control.as_dict(), risk.as_dict()])
    index = build_index(tmp_path, sources=[source])
    plan = CoveragePlanner().plan_factors({"propagation_topology": ["fanout", "chain"]}, feasible=lambda row: True)
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    selected = command.prescreen_history_targets(spec, plan, index, seed=91, directory=tmp_path / "run")
    assert selected["factors"] == {"propagation_topology": "chain"}
    report = CoveragePlanner().report_coverage(plan)
    assert report["machine_covered_interactions"] == 0 and report["shortfall"] == 2
    assert plan["outcomes"][0]["outcome"]["rejection_code"] == "HISTORICAL_STRUCTURE_ALREADY_SEEN"
    evidence = next((tmp_path / "run/history_prescreen").glob("*.json"))
    assert read_json(evidence)["provider_calls"] == 0
    child = program_proposal(spec, seed=91, difficulty="M", target=selected["factors"])
    atomic_json(tmp_path / "PAIR-child.json", [case.as_dict() for case in spec.adapter.compile_pair(child, seed=91)])
    expanded = build_index(tmp_path, sources=[source, tmp_path / "PAIR-child.json"])
    assert command.prescreen_history_targets(spec, plan, expanded, seed=91, directory=tmp_path / "run") is None
    assert CoveragePlanner().report_coverage(plan)["shortfall"] == 2


def test_history_extension_retains_archives_probes_and_rejected_occurrences(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path / "runs")
    monkeypatch.setattr(command, "ROOT", tmp_path)
    pair = suite_spec("T331", typed=True).slice_module.generate(seed=91, families=1)[0]
    original = tmp_path / "old/PAIR.json"
    atomic_json(original, [case.as_dict() for case in pair])
    index = build_index(tmp_path, sources=[original])
    index["source_sha256"]["archive.zip"] = "a" * 64
    index["records"][0]["behavioral_probe_signature"] = {"immutable": "probe"}
    rejected = tmp_path / "new/PAIR.json"
    atomic_json(rejected, [case.as_dict() for case in pair])
    atomic_json(rejected.parent / "RESULT.json", {"status": "REJECTED"})
    merged = command.extend_history(index, [rejected])
    assert merged["source_sha256"]["archive.zip"] == "a" * 64
    assert merged["records"][0]["behavioral_probe_signature"] == {"immutable": "probe"}
    assert len(index["records"][0]["occurrences"]) == 1
    assert len(merged["records"][0]["occurrences"]) == 2
    assert merged["records"][0]["occurrences"][-1]["status"] == "REJECTED"
    assert len(merged["records"]) == 2


def test_live_candidate_uses_authoritative_runtime_hash_and_reaches_real_pool(monkeypatch):
    from ioabench.v5.ai_generation import pool
    from test_reusable_data_factory import TrialPort, setup_trial, CATALOG, GEN, AUD

    with TemporaryDirectory(prefix="test_cli_pool_", dir=ROOT / "artifacts/v5/data_factory/upgrade-20261019") as temporary:
        workspace = Path(temporary)
        command = _command(monkeypatch, workspace / "trials")
        _, blueprint, _ = setup_trial()
        port = TrialPort(blueprint)
        monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: port)
        monkeypatch.setattr(command, "_load_api_key", lambda: "unused-local-fixture")

        async def prepared(*args):
            return CATALOG, {"generator": GEN, "auditor": AUD}, {"generator": {}, "auditor": {}}

        monkeypatch.setattr(command, "prepare_models", prepared)
        directory = command.RUNS / "test-run"
        source = source_tree_hash(ROOT)
        state = asyncio.run(command.live(directory, _args(trials=1)))
        assert state["accepted"] == 1 and port.calls == ["GENERATOR", "INDEPENDENT_AUDITOR"]
        assert read_json(directory / "candidate-01/MANIFEST.json")["source_sha256"] == source
        contract = read_json(directory / "RUN_CONTRACT.json")
        assert contract["source_sha256"] == source
        assert contract["command_sha256"] == hashlib.sha256(Path(command.__file__).read_bytes()).hexdigest()
        archive = read_json(directory / "SOURCE_MANIFEST.json")
        assert archive["runtime_source_sha256"] == source and archive["source_sha256"] == "fixed-source-hash"
        registry = workspace / "registry.jsonl"
        registry.write_text("", encoding="utf-8")
        report = pool.build_pool(ROOT, workspace / "pool", [{
            "directory": (directory / "candidate-01").relative_to(ROOT).as_posix(), "split": "development"}],
            registry_path=registry, expected_source_sha256=source)
        assert report["layer_case_counts"][pool.LAYERS[0]] == 2
        assert report["formal_accepted"] is False
        assert pool.verify_pool(workspace / "pool") == report
        contract["command_sha256"] = "0" * 64
        atomic_json(directory / "RUN_CONTRACT.json", contract)
        monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
        with pytest.raises(ValueError, match="configuration or source changed"):
            asyncio.run(command.live(directory, _args(trials=1)))


@pytest.mark.parametrize("scope", ["family_instance", "new_structure"])
def test_g3_prescreen_skips_identical_parent_cell_and_selects_actual_mutation(monkeypatch, tmp_path, scope):
    from test_reusable_data_factory import setup_trial
    command = _command(monkeypatch, tmp_path / "runs")
    spec, parent, _ = setup_trial()
    plan = CoveragePlanner().plan_factors({"propagation_topology": ["fanout", "chain"]}, feasible=lambda row: True)
    index = build_index(tmp_path, sources=[])
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    selected = command.prescreen_history_targets(spec, plan, index, seed=91, directory=tmp_path / "run",
                                                 parent=parent, diversity_target=scope)
    assert selected["factors"] == {"propagation_topology": "chain"}
    child = program_proposal(spec, seed=91, difficulty="M", target=selected["factors"], parent=parent)
    before, _ = spec.adapter.compile_pair(parent, seed=91)
    after, _ = spec.adapter.compile_pair(child, seed=91)
    assert spec.adapter.structural_signature(before) != spec.adapter.structural_signature(after)
    assert plan["outcomes"][0]["outcome"]["rejection_code"] == "NO_STRUCTURAL_MUTATION"
    evidence = read_json(next((tmp_path / "run/parent_prescreen").glob("*.json")))
    assert evidence["provider_calls"] == 0 and evidence["parent_blueprint_sha256"]
    assert CoveragePlanner().report_coverage(plan)["machine_covered_interactions"] == 0


def test_g3_no_legal_mutation_persists_shortfall_even_without_coverage_flag(monkeypatch, tmp_path):
    from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract
    from test_reusable_data_factory import TrialPort, setup_trial, execute, CATALOG, GEN, AUD

    command = _command(monkeypatch, tmp_path / "runs")
    import plan_factory_coverage
    spec, parent, references = setup_trial()
    parent_directory = tmp_path / "parent"
    assert execute(parent_directory, spec, TrialPort(parent), references, source_hash=source_tree_hash(ROOT))['status'] == "MACHINE_ACCEPTED"
    before = {path: path.read_bytes() for path in parent_directory.rglob("*") if path.is_file()}
    gold = tmp_path / "gold"
    atomic_json(gold / "CONTROL_RESULT.json", {"auditor": AUD.model_id})
    history_path = tmp_path / "INDEX.json"
    atomic_json(history_path, build_index(ROOT, sources=[]))
    args = _args(trials=1)
    vars(args).update(preflight=tmp_path / "preflight", judge_control=[gold], acquisition="G3", staged=False,
        coverage=False, auto_typed=True, fallback_generator=[], fallback_auditor=[], parent=parent_directory,
        history_index=history_path, diversity_target="family_instance")
    monkeypatch.setattr(command, "archive_source", lambda directory: atomic_json(directory / "SOURCE_MANIFEST.json", {"fixture": True}))
    monkeypatch.setattr(command, "baseline_sources", lambda suites: {})
    monkeypatch.setattr(command, "baseline_cases", lambda *args: references)
    monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: object())
    monkeypatch.setattr(command, "_load_api_key", lambda: "unused-local-fixture")
    monkeypatch.setattr(command, "AuxiliaryRouter", lambda *args: object())
    monkeypatch.setattr(command, "run_candidate", _no_provider)

    def qualified(*args, role, **kwargs):
        profile = GEN if role == "GENERATOR" else AUD
        entry = next(row for row in CATALOG if row["model_id"] == profile.model_id)
        return CATALOG, [AuxiliaryContract(profile, {}, entry, "fixture", (role,), "fixture")], "https://fixture.invalid/v1"

    monkeypatch.setattr(command, "qualified_contracts", qualified)
    monkeypatch.setattr(plan_factory_coverage, "_factors", lambda *args: {"propagation_topology": ["fanout"]})
    directory = command.RUNS / args.run_id
    state = asyncio.run(command.live(directory, args))
    assert state["status"] == "COVERAGE_SHORTFALL" and state["outcomes"] == [] and state["accepted"] == 0
    assert read_json(directory / "RUN_STATE.json") == state
    plan = read_json(directory / "COVERAGE_PLANS.json")["T331"]
    assert len(plan["outcomes"]) == 1
    assert plan["outcomes"][0]["outcome"]["rejection_code"] == "NO_STRUCTURAL_MUTATION"
    assert read_json(directory / "COVERAGE_REPORT.json")["T331"]["shortfall"] == 1
    assert all(path.read_bytes() == content for path, content in before.items())


def test_g3_invalid_parent_stops_before_model_qualification_and_baseline_work(monkeypatch, tmp_path):
    command = _command(monkeypatch, tmp_path / "runs")
    parent = tmp_path / "parent"
    _terminal(parent)
    args = _args(trials=1)
    vars(args).update(preflight=tmp_path / "preflight", judge_control=[], acquisition="G3", staged=False,
        coverage=True, auto_typed=True, fallback_generator=[], fallback_auditor=[], parent=parent,
        diversity_target="family_instance")
    monkeypatch.setattr(command, "archive_source", lambda directory: atomic_json(directory / "SOURCE_MANIFEST.json", {"fixture": True}))
    monkeypatch.setattr(command, "qualified_contracts", _no_provider)
    monkeypatch.setattr(command, "baseline_cases", _no_provider)
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    with pytest.raises(ValueError, match="machine-accepted parent"):
        asyncio.run(command.live(command.RUNS / args.run_id, args))


def _independent_reference_history(monkeypatch, tmp_path):
    from ioabench.v5.ai_generation.history import behavioral_signature, POLICY_CONTRACT, PROBE_VERSION
    from ioabench.v5.dynamic.runner import run_dynamic_case

    command = _command(monkeypatch, tmp_path / "runs")
    monkeypatch.setattr(command, "ROOT", tmp_path)
    monkeypatch.setattr(command, "AIHubMixAdapter", _no_provider)
    spec = suite_spec("T331", typed=True)
    pair = spec.slice_module.generate(seed=91, families=1)[0]
    original = tmp_path / "prior/PAIR.json"
    atomic_json(original, [case.as_dict() for case in pair])
    index = build_index(tmp_path, sources=[original])
    candidate = tmp_path / "rejected"
    result = _terminal(candidate, pair=pair)
    profile = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
    current_probes, current_results = {}, []
    for repetition in ("historical", "candidate"):
        for case in pair:
            results = {policy: run_dynamic_case(tmp_path / "runner", case, spec.slice_module,
                       spec.slice_module.policies()[policy], profile,
                       run_id=f"{repetition}-{policy}-{case.arm.lower()}",
                       parameters={"temperature": 0.0})
                       for policy in ("witness", "naive")}
            probe = behavioral_signature(case, results, policy_contract=POLICY_CONTRACT)
            record = next(row for row in index["records"] if row["case_sha256"] == case.content_sha256())
            if repetition == "historical":
                record["behavioral_probe_signature"] = probe
            else:
                assert probe["behavior"] == record["behavioral_probe_signature"]["behavior"]
                assert probe["evidence_sha256"] != record["behavioral_probe_signature"]["evidence_sha256"]
                current_probes[case.content_sha256()] = probe
                current_results.extend(results.values())
    atomic_json(candidate / "REFERENCE_RESULTS.json", current_results)
    atomic_json(candidate / "BEHAVIORAL_PROBES.json", {
        "probe_version": PROBE_VERSION, "policy_contract": POLICY_CONTRACT,
        "by_case_sha256": current_probes,
        "reference_results_sha256": hashlib.sha256((candidate / "REFERENCE_RESULTS.json").read_bytes()).hexdigest()})
    result["evidence_sha256"].update({name: hashlib.sha256((candidate / name).read_bytes()).hexdigest()
                                     for name in ("REFERENCE_RESULTS.json", "BEHAVIORAL_PROBES.json")})
    atomic_json(candidate / "RESULT.json", result)
    return command, index, candidate


def test_history_extension_accepts_independent_equal_behavior_and_retains_both_bindings(monkeypatch, tmp_path):
    from copy import deepcopy

    command, index, candidate = _independent_reference_history(monkeypatch, tmp_path)
    before = deepcopy(index)
    merged = command.extend_history(index, [candidate / "PAIR.json"])
    assert index == before
    for prior, added in zip(index["records"], merged["records"]):
        assert added["behavioral_probe_signature"] == prior["behavioral_probe_signature"]
        assert len(added["occurrences"]) == len(prior["occurrences"]) + 1
    proof_name = (candidate / "BEHAVIORAL_PROBES.json").relative_to(tmp_path).as_posix()
    assert merged["source_sha256"][proof_name] == hashlib.sha256((candidate / "BEHAVIORAL_PROBES.json").read_bytes()).hexdigest()
    assert command.extend_history(merged, [candidate / "PAIR.json"]) == merged


@pytest.mark.parametrize("field", ["behavior", "policy_contract", "probe_version", "case_sha256"])
def test_history_extension_still_rejects_semantic_or_identity_probe_conflicts(monkeypatch, tmp_path, field):
    command, index, candidate = _independent_reference_history(monkeypatch, tmp_path)
    prior = index["records"][0]["behavioral_probe_signature"]
    if field == "behavior":
        prior["behavior"]["witness"]["actions"][0]["tool"] = "different-runtime-tool"
    else:
        prior[field] = "different-contract-or-case"
    with pytest.raises(ValueError, match="conflicting pinned behavioral probes"):
        command.extend_history(index, [candidate / "PAIR.json"])
