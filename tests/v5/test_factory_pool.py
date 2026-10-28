from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation import pool
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract, AuxiliaryRouter
from ioabench.v5.ai_generation.factory import EVIDENCE_FILES, read_json
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.judge_controls import fixed_controls, score_control, summarize_controls
from ioabench.v5.ai_generation.quality import evidence_paths, resolve_pointer
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS
from ioabench.v5.dynamic import family_registry
from ioabench.v5.dynamic.runner import run_dynamic_case
from ioabench.v5.dynamic.signature import family_digest
from ioabench.v5.evaluation import atomic_json

from test_reusable_data_factory import TrialPort, execute, setup_trial


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def environment(tmp_path, monkeypatch):
    source = source_tree_hash(ROOT)
    monkeypatch.setattr(pool, "source_tree_hash", lambda root: source)
    registry = tmp_path / "registry.jsonl"
    registry.write_text("", encoding="utf-8")
    spec, blueprint, references = setup_trial()
    result = execute(tmp_path / "candidate", spec, TrialPort(blueprint), references, source_hash=source)
    assert result["status"] == "MACHINE_ACCEPTED"
    return tmp_path, registry, source


def build(environment, assignments=None, output="pool", **kwargs):
    root, registry, source = environment
    return pool.build_pool(root, root / output, assignments or [{"directory": "candidate", "split": "development"}],
                           registry_path=registry, expected_source_sha256=source, **kwargs)


def rebind_candidate(directory):
    result = read_json(directory / "RESULT.json")
    result["evidence_sha256"] = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                 for name in EVIDENCE_FILES if (directory / name).exists()}
    atomic_json(directory / "RESULT.json", result)


def test_pool_has_distinct_bound_layers_and_idempotently_preserves_every_input(environment, monkeypatch):
    root, registry, _ = environment
    originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    monkeypatch.setattr(family_registry, "register", lambda *args, **kwargs: pytest.fail("pool registered another family"))
    manifest = build(environment)
    assert manifest["layer_case_counts"] == {pool.LAYERS[0]: 2, pool.LAYERS[1]: 0, pool.LAYERS[2]: 0, pool.LAYERS[3]: 0}
    assert manifest["formal_accepted"] is False and manifest["provider_calls"] == 0
    assert manifest["split_status"] == "DISJOINT_WITHIN_DECLARED_SCOPE"
    assert all(path.read_bytes() == content for path, content in originals.items())
    assert registry.read_bytes() == b""
    persisted = {path: path.read_bytes() for path in (root / "pool").rglob("*") if path.is_file()}
    assert build(environment) == manifest
    assert all(path.read_bytes() == content for path, content in persisted.items())
    entries = read_json(root / "pool/entries.json")
    assert entries[0]["auditor_qualification"]["status"] == "NOT_RUN_NO_BOUND_PREFLIGHT_AND_CONTROLS"
    assert entries[0]["family_registry_classification"]
    assert all(value["status"] == "NO_REFERENCE" for value in entries[0]["family_registry_classification"].values())


def test_semantic_reject_remains_structural_and_never_machine_promoted(environment):
    root, _, source = environment
    spec, blueprint, references = setup_trial()
    result = execute(root / "rejected", spec, TrialPort(blueprint, audit="FAIL"), references, source_hash=source)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "INDEPENDENT_REVIEW"
    manifest = build(environment, [{"directory": "rejected", "split": "development"}])
    assert manifest["layer_case_counts"][pool.LAYERS[0]] == 2
    assert manifest["layer_case_counts"][pool.LAYERS[1]] == 0


def test_rejected_uncompiled_proposal_is_retained_without_any_promoted_layer(environment):
    root, _, source = environment
    spec, _, references = setup_trial()
    result = execute(root / "invalid", spec, TrialPort("not-json"), references, source_hash=source)
    assert result["status"] == "REJECTED"
    manifest = build(environment, [{"directory": "invalid", "split": "development"}])
    assert manifest["cases"] == 0 and all(count == 0 for count in manifest["layer_case_counts"].values())
    assert read_json(root / "pool/rejected.json")[0]["status"] == "REJECTED"


def test_cross_split_family_registry_alias_and_shared_source_conflicts_are_explicit(environment):
    root, registry, _ = environment
    case = read_json(root / "candidate/PAIR.json")[0]
    family_registry.register(registry, suite_id="T331", family_id="historical-family-alias",
        digest=family_digest(case), run_id="retained-history")
    shutil.copytree(root / "candidate", root / "copy")
    manifest = build(environment, [{"directory": "candidate", "split": "development"},
                                   {"directory": "copy", "split": "final-hidden"}])
    report = read_json(root / "pool/splits.json")
    assert manifest["split_status"] == "CONFLICT" and report["formal_eligible"] is False
    assert report["conflicts"][0]["shared_source_keys"]
    assert "T331:id:historical-family-alias" in report["conflicts"][0]["shared_family_keys"]
    assert manifest["cases"] == 2 and manifest["layer_case_counts"][pool.LAYERS[1]] == 0
    with pytest.raises(ValueError, match="split conflict"):
        build(environment, [{"directory": "candidate", "split": "development"},
                            {"directory": "copy", "split": "final-hidden"}], output="formal", formal_claim=True)
    assert not (root / "formal").exists()


@pytest.mark.parametrize("splits", [(left, right) for index, left in enumerate(pool.SPLITS) for right in pool.SPLITS[index + 1:]])
def test_each_split_pair_rejects_shared_source_for_formal_claim(splits):
    entries = [{"entry_id": str(index), "split": split, "family_keys": ["different:" + str(index)],
                "source_keys": ["shared-business-source"]} for index, split in enumerate(splits)]
    report = pool.split_report(entries)
    assert report["status"] == "CONFLICT" and report["conflicts"][0]["shared_source_keys"]
    with pytest.raises(ValueError, match="split conflict"):
        pool.split_report(entries, formal_claim=True)


def test_disjoint_inputs_still_cannot_invent_authorized_formal_freeze():
    entries = [{"entry_id": str(index), "split": split, "family_keys": [str(index)], "source_keys": [str(index)]}
               for index, split in enumerate(pool.SPLITS)]
    assert pool.split_report(entries)["status"] == "DISJOINT_WITHIN_DECLARED_SCOPE"
    with pytest.raises(ValueError, match="no authorized scientific freeze"):
        pool.split_report(entries, formal_claim=True)


@pytest.mark.parametrize("mutation", ["case", "review", "journal", "fake_layer", "registry"])
def test_candidate_tampering_and_unsupported_label_promotion_fail_closed(environment, mutation):
    root, registry, _ = environment
    if mutation == "case":
        path = root / "candidate/PAIR.json"
        value = read_json(path)
        value[0]["world"]["org"] = "forged company"
        atomic_json(path, value)
    elif mutation == "review":
        path = root / "candidate/REVIEW.json"
        value = read_json(path)
        value["verdict"] = "FAIL"
        atomic_json(path, value)
        rebind_candidate(root / "candidate")
    elif mutation == "journal":
        row = read_json(root / "candidate/REFERENCE_RESULTS.json")[0]
        (root / "candidate/replay" / row["attempt_journal"]["path"]).write_text("forged", encoding="utf-8")
    elif mutation == "registry":
        registry.write_text("not-json", encoding="utf-8")
    else:
        with pytest.raises(ValueError, match="unknown pool assignment"):
            build(environment, [{"directory": "candidate", "split": "development", "layer": pool.LAYERS[3]}])
        return
    with pytest.raises((ValueError, KeyError)):
        build(environment)
    assert not (root / "pool").exists()


@pytest.mark.parametrize("mutation", ["blob", "manifest", "extra", "removed"])
def test_snapshot_tampering_never_passes_verification(environment, mutation):
    root, _, _ = environment
    build(environment)
    output = root / "pool"
    if mutation == "manifest":
        manifest = read_json(output / "manifest.json")
        manifest["formal_accepted"] = True
        atomic_json(output / "manifest.json", manifest)
    elif mutation == "extra":
        (output / "unexpected").write_bytes(b"unbound")
    elif mutation == "removed":
        (output / "cases.jsonl").unlink()
    else:
        next((output / "evidence").iterdir()).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        pool.verify_pool(output)


def add_measurement(environment, *, complete=True):
    root, _, source = environment
    spec = suite_spec("T331", typed=True)
    cases = [pool.case_from_dict(raw, allow_dynamic=True) for raw in read_json(root / "candidate/PAIR.json")]
    profile = ModelProfile("aihubmix", "aux-measure", {}, {}, role="CALIBRATOR")
    entry = {"model_id": profile.model_id, "developer_id": "fixture", "pricing": {"input": 1, "output": 1}}
    contract = AuxiliaryContract(profile, {"temperature": 0.0}, entry, "local-fixture-preflight", ("CALIBRATOR",))

    class LocalPort:
        stop_on_provider_error = True
        async def generate(self, profile, request):
            response = await spec.policies["witness"].generate(profile, request)
            return replace(response, model_id=profile.model_id, provider_metadata={"model": profile.model_id})

    class RoutedPort:
        def __init__(self, directory):
            self.router, self.count = AuxiliaryRouter(LocalPort(), [contract], [entry], directory), 0
        async def generate(self, profile, request):
            self.count += 1
            return await self.router.invoke("CALIBRATOR", f"call-{self.count:03d}", request)

    directory = root / "calibration"
    atomic_json(directory / "CALIBRATION_CONTRACT.json", {"runtime_source_sha256": source, "formal_SUT_used": False,
        "selected_case_sha256": [case.content_sha256() for case in cases], "models": [asdict(contract)], "repetitions": 1})
    atomic_json(directory / "PAIRS.json", [case.as_dict() for case in cases])
    rows = []
    for case in cases:
        ident = f"aux-measure-r1-{case.suite_id}-{case.arm.lower()}"
        if complete:
            row = run_dynamic_case(directory / "replay", case, spec.slice_module,
                RoutedPort(directory / "episodes" / ident / "model_io"), profile,
                run_id=ident, parameters=contract.parameters)
        else:
            row = {"run_id": ident, "case_id": case.case_id, "case_sha256": case.content_sha256(),
                   "arm": case.arm, "model_id": profile.model_id, "status": "NOT_RUN", "scientifically_eligible": False}
        rows.append(row)
    atomic_json(directory / "RESULTS.json", rows)
    atomic_json(directory / "CALIBRATION_REPORT.json", {"status": "EXPLORATORY_PANEL_COMPLETED" if complete else "EXPLORATORY_PANEL_STOPPED"})


@pytest.fixture(scope="module")
def qualified_gold():
    controls, reviews = fixed_controls(), {}
    for control in controls:
        view = control["view"]
        pointer = next(path for path in evidence_paths(view) if "/world/" in path
                       and not isinstance(resolve_pointer({"candidate": view}, path), (dict, list)))
        review = {name: {"score": 4, "rationale": "Local contract fixture cites an actual public leaf.",
            "evidence": [pointer], "assertions": [{"path": pointer, "equals": resolve_pointer({"candidate": view}, pointer)}]}
                  for name in REVIEW_DIMENSIONS}
        review["structural_novelty"]["evidence"].append("/candidate/family_evidence")
        review.update(verdict=control["expected"], issues=[])
        if control["expected"] == "FAIL":
            review["semantic_consistency"]["score"] = 2
            review["issues"] = [{"code": "CONTRADICTION", "field_path": control["planted_pointer"],
                "reason": "Local fixed negative fixture.", "evidence": control["planted_pointer"]}]
        elif control["expected"] == "ABSTAIN":
            review["structural_novelty"]["score"] = 3
        assert score_control(control, review)["correct"]
        reviews[control["id"]] = review
    return controls, reviews


def add_qualification(environment, qualified_gold):
    root, _, _ = environment
    controls, reviews = qualified_gold
    gold, preflight = root / "gold", root / "preflight"
    atomic_json(gold / "GOLD_CONTROLS.json", controls)
    atomic_json(gold / "CONTROL_CONTRACT.json", {"runtime_source_sha256": source_tree_hash(root),
        "controls_sha256": canonical_sha256(controls)})
    atomic_json(gold / "PARAMETER_BINDING.json", {"actual_parameters": {"max_tokens": 100}})
    for ident, review in reviews.items():
        atomic_json(gold / ident / "REVIEW.json", review)
    result = summarize_controls([score_control(control, reviews[control["id"]]) for control in controls])
    assert result["passed"]
    atomic_json(gold / "CONTROL_RESULT.json", {**result, "auditor": "auditor-1", "status": "ENGINEERING_CONTROLS_PASS",
        "evidence_sha256": {path.relative_to(gold).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in gold.rglob("*.json")}})
    binding = {"contracts": [{"profile": {"model_id": "auditor-1"}, "parameters": {"max_tokens": 100}}]}
    atomic_json(preflight / "probe/REQUEST_BINDING.json", {"binding": binding, "sha256": canonical_sha256(binding)})
    response = asdict(ModelResponse(text="local probe", model_id="auditor-1", finish_reason="stop",
                                   provider_metadata={"model": "auditor-1"}))
    atomic_json(preflight / "probe/RESPONSE.json", {"response": response, "response_sha256": canonical_sha256(response),
                                                  "binding_sha256": canonical_sha256(binding)})
    atomic_json(preflight / "MODEL_CATALOG.json", [{"model_id": "auditor-1", "developer_id": "zhipu"}])
    atomic_json(preflight / "schemas/auditor-1.json", {"model_id": "auditor-1",
        "protocols": ["openai.chat_completions"], "specs": {"max_output_tokens": 100},
        "domains": [{"capabilities": [{"key": "output-limit", "protocols": [
            {"protocol": "openai.chat_completions", "fields": [{"name": "max_tokens"}]}]}]}]})
    atomic_json(preflight / "AIHUBMIX_PREFLIGHT.json", {"candidates": [{"requested_model_id": "auditor-1", "live_probe": "PASS",
        "response_evidence": str(preflight / "probe/RESPONSE.json"), "actual_parameters": {"max_tokens": 100},
        "endpoint": "https://api.inferera.com/v1/chat/completions"}]})
    atomic_json(preflight / "SHA256SUMS.json", {"files": {path.relative_to(preflight).as_posix():
        hashlib.sha256(path.read_bytes()).hexdigest() for path in preflight.rglob("*.json")}})
    return {"preflight": "preflight", "judge_controls": "gold"}


def test_empirical_layer_requires_exact_complete_auxiliary_behavior_and_keeps_labels_uncalibrated(environment, qualified_gold):
    root, _, _ = environment
    add_measurement(environment)
    qualification = add_qualification(environment, qualified_gold)
    report = build(environment, [{"directory": "candidate", "split": "calibration", "calibration": "calibration",
                                  "auditor_qualification": qualification}])
    assert report["layer_case_counts"][pool.LAYERS[2]] == 2
    assert report["layer_case_counts"][pool.LAYERS[1]] == 2
    assert report["split_status"] == "DISJOINT_WITHIN_DECLARED_SCOPE"
    entry = read_json(root / "pool/entries.json")[0]
    assert all(row["empirical_label"] == "UNCALIBRATED" and row["strict_replay"]["passed"]
               for rows in entry["measurements"].values() for row in rows)
    assert report["layer_case_counts"][pool.LAYERS[3]] == 0


def test_auditor_qualification_cannot_inherit_a_different_runtime(environment, qualified_gold):
    root, _, _ = environment
    qualification = add_qualification(environment, qualified_gold)
    contract = read_json(root / "gold/CONTROL_CONTRACT.json")
    contract["runtime_source_sha256"] = "older-runtime"
    atomic_json(root / "gold/CONTROL_CONTRACT.json", contract)
    with pytest.raises(ValueError, match="runtime source changed"):
        build(environment, [{"directory": "candidate", "split": "development", "auditor_qualification": qualification}])


def test_not_run_measurements_do_not_become_empirically_measured(environment):
    add_measurement(environment, complete=False)
    report = build(environment, [{"directory": "candidate", "split": "calibration", "calibration": "calibration"}])
    assert report["layer_case_counts"][pool.LAYERS[2]] == 0


@pytest.mark.parametrize("complete", [False, True])
def test_calibration_selection_conflicts_with_development_even_when_not_run(environment, complete):
    root, _, _ = environment
    add_measurement(environment, complete=complete)
    report = build(environment, [{"directory": "candidate", "split": "development", "calibration": "calibration"}])
    assert report["split_status"] == "CONFLICT"
    entry = read_json(root / "pool/entries.json")[0]
    assert entry["measurement_split"] == "calibration" and len(entry["measurement_selection_sha256"]) == 2
    assert report["cases"] == 2
    conflicts = read_json(root / "pool/splits.json")["conflicts"]
    assert conflicts[0]["splits"] == ["development", "calibration"]


def test_bound_auditor_controls_are_rechecked_before_machine_promotion(environment, qualified_gold):
    root, _, _ = environment
    qualification = add_qualification(environment, qualified_gold)
    manifest = build(environment, [{"directory": "candidate", "split": "development", "auditor_qualification": qualification}])
    assert manifest["layer_case_counts"][pool.LAYERS[1]] == 2
    wrong = next(item for item in qualified_gold[0] if item["id"] == "T331-wrong-construct")
    membership = read_json(root / "pool/entries.json")[0]["auditor_qualification"]["split_membership"]
    assert all(canonical_sha256(raw) in membership["source_keys"] for raw in wrong["view"]["paired_cases"])
    assert all("T321:legacy:" + family_digest(raw) not in membership["family_keys"]
               for raw in wrong["view"]["paired_cases"])
    review = root / "gold/T321-positive/REVIEW.json"
    review.write_bytes(b"forged")
    with pytest.raises(ValueError, match="judge control evidence changed"):
        build(environment, [{"directory": "candidate", "split": "development", "auditor_qualification": qualification}], output="changed")


def test_actual_judge_control_family_is_automatically_part_of_split_isolation(environment, qualified_gold):
    root, _, source = environment
    qualification = add_qualification(environment, qualified_gold)
    spec, _, references = setup_trial()
    blueprint = next(control["view"]["blueprint"] for control in qualified_gold[0] if control["id"] == "T331-positive")
    assert execute(root / "gold-derived", spec, TrialPort(blueprint), references, source_hash=source)["status"] == "MACHINE_ACCEPTED"
    report = build(environment, [{"directory": "gold-derived", "split": "development", "auditor_qualification": qualification}])
    assert report["split_status"] == "CONFLICT"
    conflicts = read_json(root / "pool/splits.json")["conflicts"]
    assert any("judge-control" in row["splits"] and row["shared_family_keys"] for row in conflicts)


@pytest.mark.parametrize("mutation", ["duplicate_finish", "unresolved", "wire"])
def test_rehashed_measurement_ledger_cannot_invent_resolved_unique_calls(environment, mutation):
    root, _, _ = environment
    add_measurement(environment)
    path = next((root / "calibration/episodes").glob("*/model_io/AIHUBMIX_ATTEMPTS.jsonl"))
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if mutation == "duplicate_finish":
        events.append(dict(next(event for event in events if event["event"] == "REQUEST_FINISHED")))
    elif mutation == "unresolved":
        next(event for event in events if event["event"] == "REQUEST_FINISHED")["status"] = "REQUEST_UNRESOLVED"
    else:
        for event in events:
            if "request_sha256" in event:
                event["request_sha256"] = "f" * 64
    previous = ""
    for event in events:
        event.pop("event_sha256")
        event["previous_event_sha256"] = previous
        event["event_sha256"] = previous = canonical_sha256(event)
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    with pytest.raises(ValueError, match="measurement"):
        build(environment, [{"directory": "candidate", "split": "calibration", "calibration": "calibration"}])
    assert not (root / "pool").exists()


def test_partial_same_content_snapshot_recovers_without_changing_retained_files(environment):
    root, _, _ = environment
    manifest = build(environment)
    output = root / "pool"
    (output / "manifest.json").unlink()
    next((output / "evidence").iterdir()).unlink()
    retained = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}
    assert build(environment) == manifest
    assert all(path.read_bytes() == content for path, content in retained.items())


def test_runtime_source_drift_and_duplicate_or_escaping_assignments_fail_before_output(environment, monkeypatch):
    root, _, source = environment
    for assignments in ([{"directory": "candidate", "split": "development"}] * 2,
                        [{"directory": "../candidate", "split": "development"}]):
        with pytest.raises(ValueError):
            build(environment, assignments)
        assert not (root / "pool").exists()
    hashes = iter([source, "changed-source"])
    monkeypatch.setattr(pool, "source_tree_hash", lambda root: next(hashes))
    with pytest.raises(ValueError, match="source"):
        build(environment)
    assert not (root / "pool").exists()


def test_actual_cli_build_and_verify_use_same_pool_without_provider(environment, monkeypatch, capsys):
    root, registry, source = environment
    path = ROOT / "scripts/v5/build_factory_pool.py"
    spec = importlib.util.spec_from_file_location("pool_command_under_test", path)
    command = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(command)
    monkeypatch.setattr(command, "ROOT", root)
    assignments = root / "assignments.json"
    atomic_json(assignments, [{"directory": "candidate", "split": "development"}])
    assert command.main(["--output", str(root / "pool"), "--assignments", str(assignments),
                         "--registry", str(registry), "--source-sha256", source]) == 0
    assert json.loads(capsys.readouterr().out)["formal_accepted"] is False
    assert command.main(["--output", str(root / "pool"), "--verify"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "IMMUTABLE_DEVELOPMENT_SNAPSHOT"


def tuple_chain_candidate(tmp_path, monkeypatch, suite):
    from ioabench.v5.ai_generation.acquisition import program_proposal
    from ioabench.v5.ai_generation.history import build_index

    source = source_tree_hash(ROOT)
    monkeypatch.setattr(pool, "source_tree_hash", lambda root: source)
    registry = tmp_path / "registry.jsonl"
    registry.write_text("", encoding="utf-8")
    spec = suite_spec(suite, typed=True)
    blueprint = program_proposal(spec, seed=91, difficulty="M")
    pair = spec.adapter.compile_pair(blueprint, seed=91)
    assert all(isinstance(case.world["chain"], tuple) for case in pair)
    prior = tmp_path / "prior/PAIR.json"
    atomic_json(prior, [case.as_dict() for case in pair])
    index = build_index(tmp_path, sources=[prior])

    class NoProvider:
        async def generate(self, *args, **kwargs):
            pytest.fail("known duplicate called a provider")

    result = execute(tmp_path / "candidate", spec, NoProvider(), [], source_hash=source,
        proposal=blueprint, acquisition_strategy="G1", historical_index=index)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "ALL_HISTORY_DEDUP"
    persisted = read_json(tmp_path / "candidate/PAIR.json")
    assert all(isinstance(case["world"]["chain"], list) for case in persisted)
    assert canonical_sha256([case.as_dict() for case in pair]) == canonical_sha256(persisted)
    return tmp_path, registry, source


@pytest.mark.parametrize("suite", ["T341", "T343"])
def test_actual_tuple_chain_round_trip_is_structurally_retained(tmp_path, monkeypatch, suite):
    environment = tuple_chain_candidate(tmp_path, monkeypatch, suite)
    manifest = build(environment)
    assert manifest["cases"] == manifest["layer_case_counts"][pool.LAYERS[0]] == 2
    assert all(manifest["layer_case_counts"][layer] == 0 for layer in pool.LAYERS[1:])
    assert pool.verify_pool(tmp_path / "pool") == manifest


@pytest.mark.parametrize("suite", ["T341", "T343"])
def test_actual_chain_leaf_change_still_fails_after_all_file_hashes_are_rebound(tmp_path, monkeypatch, suite):
    environment = tuple_chain_candidate(tmp_path, monkeypatch, suite)
    directory = tmp_path / "candidate"
    pair = read_json(directory / "PAIR.json")
    pair[0]["world"]["chain"][0] += "-forged"
    atomic_json(directory / "PAIR.json", pair)
    rebind_candidate(directory)
    result = read_json(directory / "RESULT.json")
    terminal = read_json(directory / "TERMINAL.json")
    terminal.update(result=result, result_sha256=canonical_sha256(result))
    atomic_json(directory / "TERMINAL.json", terminal)
    pool.validate_saved_result(directory, result)
    with pytest.raises(ValueError, match="persisted pair differs from programmatic compilation"):
        build(environment)
    assert not (tmp_path / "pool").exists()
