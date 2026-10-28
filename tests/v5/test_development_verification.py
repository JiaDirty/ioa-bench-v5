from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import shutil
import socket
import subprocess
import sys
import urllib.request

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelResponse
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.development_audit import audit_pair, CURRENT_PROTOCOL, VERSION
from ioabench.v5.ai_generation.direct_deepseek import DirectStudy, SCOPE
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.evaluation import atomic_json


SPEC = importlib.util.spec_from_file_location("development_verifier", Path(__file__).resolve().parents[2] /
    "scripts/v5/verify_development_factory.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


@pytest.mark.parametrize("value", ["D:/Project/ioa_codex_spec-evasion/a", "E:/Project/ioa_codex_spec/a",
                                 "D:/Project/ioa_codex_spec/../secret", "D:relative/file"])
def test_mapping_rejects_other_roots_prefix_collision_and_traversal(tmp_path, value):
    with pytest.raises(ValueError):
        verifier.mapped_path(value, tmp_path)


def test_mapping_is_exact_case_insensitive_and_never_falls_back(tmp_path):
    mapped = verifier.mapped_path("d:/PROJECT/ioa_codex_spec/artifacts/missing.json", tmp_path)
    assert mapped == tmp_path / "artifacts/missing.json"
    assert not mapped.exists()
    with pytest.raises(ValueError, match="missing or changed"):
        verifier.verify_files(tmp_path, {"artifacts/missing.json": "0" * 64})
    with pytest.raises(ValueError, match="traversal"):
        verifier.safe_child(tmp_path, "../outside")


def test_hash_binding_checks_real_bytes_and_missing_result_never_recovers(tmp_path):
    path = tmp_path / "item.json"
    path.write_text("{}", encoding="utf-8")
    digest = verifier.sha(path)
    assert verifier.verify_files(tmp_path, {"item.json": digest}) == 1
    path.write_text("{ }", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        verifier.verify_files(tmp_path, {"item.json": digest})
    atomic_json(tmp_path / "TERMINAL.json", {"result": {}})
    with pytest.raises(ValueError, match="will not reconstruct"):
        verifier.sealed_candidate(tmp_path)
    assert not (tmp_path / "RESULT.json").exists()


def test_network_guard_blocks_real_http_socket_dns_and_restores_functions():
    original = urllib.request.urlopen, socket.socket.connect, socket.getaddrinfo
    with verifier.no_network() as guard:
        with pytest.raises(AssertionError, match="forbidden"):
            urllib.request.urlopen("https://api.deepseek.com")
        with socket.socket() as connection:
            with pytest.raises(AssertionError, match="forbidden"):
                connection.connect(("198.51.100.1", 443))
        with pytest.raises(AssertionError, match="forbidden"):
            socket.getaddrinfo("api.deepseek.com", 443)
        assert asyncio.run(asyncio.sleep(0, result="local event loop works")) == "local event loop works"
    assert guard["provider_http_or_external_network_attempts"] == 3
    assert original == (urllib.request.urlopen, socket.socket.connect, socket.getaddrinfo)


class Port:
    base_url = "https://api.deepseek.com"

    async def generate(self, profile, request):
        documents = json.loads(request.messages[-1]["content"])["documents"]
        review = {"verdict": "ACCEPT", "error_codes": [], "evidence_refs": [
            {"file": item["file"], "json_pointer": "", "sha256": item["sha256"], "claim": "Bound evidence."}
            for item in documents.values()], "causal_mechanism": "A changed inbound value propagates.",
            "control_risk_delta": "One intervention differs.", "novelty_claim": "Existing mechanism instance.",
            "difficulty_rationale": "Uncalibrated design intention.", "reuse_constraints": ["Preserve source ledger."],
            "disconfirming_checks": ["Compare arm actions to their frozen source facts."]}
        return ModelResponse(text=json.dumps(review), model_id="deepseek-flash", finish_reason="stop",
            usage={"prompt_tokens": 8, "completion_tokens": 9}, provider_metadata={"model": "deepseek-flash",
                "_transport": {"http_status": 200, "endpoint": "https://api.deepseek.com/chat/completions"}})


@pytest.fixture
def audited(tmp_path, monkeypatch):
    monkeypatch.setattr(verifier, "ORIGINAL_ROOT", PureWindowsPath(tmp_path))
    source = tmp_path / "source"
    source.mkdir()
    spec = suite_spec("T331", typed=True)
    blueprint = program_proposal(spec, seed=193, difficulty="M")
    compiled = compile_and_gate(spec, blueprint, seed=193)
    pair = [compiled[arm].as_dict() for arm in ("control", "risk")]
    rows = [{"arm": case["arm"], "case_id": case["case_id"], "status": "COMPLETED", "trace": {"actions": [], "records": []}}
            for _ in spec.policies for case in pair]
    values = {"MANIFEST.json": {"source_sha256": "fixture-runtime", "task": {"suite": "T331"}},
              "BLUEPRINT.json": blueprint, "PAIR.json": pair, "STRICT_REFERENCE_RESULTS.json": rows,
              "REPLAY.json": [{"case_id": row["case_id"], "checks": {"actions": True}, "passed": True,
                               "provider_calls": 0} for row in rows],
              "HISTORY_DEDUP.json": [{"status": "VALID_FAMILY_INSTANCE", "nearest_neighbors": []}] * 2,
              "HARD_GATE.json": {"passed": True}, "FIDELITY.json": {"faithful": True}}
    for name, value in values.items():
        atomic_json(source / name, value)
    result = {"status": "PASS", "scope": SCOPE, "formal_accepted": False, "machine_qualified": False,
              "evidence_sha256": {name: verifier.sha(source / name) for name in values}}
    atomic_json(source / "RESULT.json", result)
    atomic_json(source / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})
    study = DirectStudy(tmp_path, Port(), [{"id": "deepseek-flash"}])
    return source, study


@pytest.mark.parametrize("protocol", [VERSION, CURRENT_PROTOCOL])
@pytest.mark.parametrize("max_tokens", [16384, 65536])
def test_frozen_audits_verify_model_io_and_source_without_network(tmp_path, audited, protocol, max_tokens):
    source, study = audited
    directory = tmp_path / "audit"
    asyncio.run(audit_pair(study, source, directory, protocol=protocol, max_tokens=max_tokens))
    before = verifier.inventory(tmp_path)
    with verifier.no_network() as guard:
        result = verifier.verify_audit(directory, tmp_path)
    assert result["status"] == "PASS" and result["audit_status"] == "DEV_AUTO_AUDITED"
    assert verifier.inventory(tmp_path) == before
    assert guard["provider_http_or_external_network_attempts"] == 0


def reseal(directory, result):
    atomic_json(directory / "AUDIT_RESULT.json", result)
    atomic_json(directory / "AUDIT_TERMINAL.json", {"result_sha256": canonical_sha256(result),
        "evidence_sha256": verifier.inventory(directory, except_names={"AUDIT_RESULT.json", "AUDIT_TERMINAL.json"})})


def test_invalid_review_pointer_cannot_be_hidden_by_resealing(tmp_path, audited):
    source, study = audited
    directory = tmp_path / "audit"
    result = asyncio.run(audit_pair(study, source, directory))
    row = result["reviews"][0]
    row["review"]["evidence_refs"][0]["json_pointer"] = "/invented/answer"
    atomic_json(directory / "AUDIT_high.json", row)
    raw = verifier.read(directory / "AUDIT_high_RESPONSE.json")
    raw["text"] = json.dumps(row["review"])
    atomic_json(directory / "AUDIT_high_RESPONSE.json", raw)
    reseal(directory, result)
    with pytest.raises(ValueError, match="invalid evidence references"):
        verifier.verify_audit(directory, tmp_path)


def test_effort_change_cannot_be_hidden_by_resealing(tmp_path, audited):
    source, study = audited
    directory = tmp_path / "audit"
    result = asyncio.run(audit_pair(study, source, directory))
    path = directory / "model_io" / result["reviews"][0]["request_id"] / "REQUEST_BINDING.json"
    binding = verifier.read(path)
    binding["binding"]["contracts"][0]["parameters"]["reasoning_effort"] = "low"
    binding["sha256"] = canonical_sha256(binding["binding"])
    atomic_json(path, binding)
    reseal(directory, result)
    with pytest.raises(ValueError, match="documented effort differs"):
        verifier.verify_audit(directory, tmp_path)


def test_accepted_review_cannot_bind_unrelated_case_facts(tmp_path, audited):
    source, study = audited
    directory = tmp_path / "audit"
    result = asyncio.run(audit_pair(study, source, directory))
    packet = verifier.read(directory / "AUDIT_PACKET.json")
    packet["documents"]["cases"][0]["metadata"]["case_id"] = "DIFFERENT-PAIR"
    atomic_json(directory / "AUDIT_PACKET.json", packet)
    atomic_json(directory / "inputs/cases.json", packet["documents"]["cases"])
    bindings = verifier.read(directory / "DOCUMENT_BINDINGS.json")
    bindings["inputs/cases.json"] = verifier.sha(directory / "inputs/cases.json")
    atomic_json(directory / "DOCUMENT_BINDINGS.json", bindings)
    result["packet_sha256"] = canonical_sha256(packet)
    reseal(directory, result)
    with pytest.raises(ValueError, match="documents differ from their sealed source facts"):
        verifier.verify_audit(directory, tmp_path)


@pytest.mark.parametrize("suite,count", [("T322", 6), ("T331", 4)])
def test_admission_rejects_history_uncertainty_or_invented_replay_count(tmp_path, audited, suite, count):
    source, study = audited
    review_directory = tmp_path / "reviews/item"
    audit_directory = review_directory / "audit"
    review = asyncio.run(audit_pair(study, source, audit_directory))
    record = {"id": "item", "source_directory": str(source), "audit_status": review["status"],
        "source_result_sha256": verifier.sha(source / "RESULT.json"), "pair_sha256": verifier.sha(source / "PAIR.json"),
        "audit_result_sha256": canonical_sha256(review), "recorded_strict_replays": count, "suite": suite,
        "status": "DEV_ACCEPTED", "hard_gate_errors": [], "history_scope": "FULL_HISTORY", "formal_accepted": False,
        "machine_qualified": False, "same_model_audit_independent_science": False, "new_scientific_families": 0}
    path = review_directory / "ADMISSION.json"
    atomic_json(path, record)
    audit = verifier.verify_audit(audit_directory, tmp_path)
    with pytest.raises(ValueError, match="T322 historical uncertainty|invented a strict Replay count"):
        verifier.verify_admission(path, tmp_path, {audit_directory.resolve(): audit})


def test_admission_checks_vector_hash_and_does_not_claim_calibrated_difficulty(tmp_path, audited):
    from ioabench.v5.ai_generation.development import admission, structure_vector
    from ioabench.v5.core.case import case_from_dict
    source, study = audited
    directory = tmp_path / "reviews/item"
    result = asyncio.run(audit_pair(study, source, directory / "audit"))
    vector = structure_vector(case_from_dict(verifier.read(source / "PAIR.json")[0], allow_dynamic=True))
    record = admission(source, result, vector, audit_directory=directory / "audit")
    record.update(id="item", source_directory=str(source), suite="T331", pair_sha256=verifier.sha(source / "PAIR.json"))
    path = directory / "ADMISSION.json"
    atomic_json(path, record)
    audits = {(directory / "audit").resolve(): verifier.verify_audit(directory / "audit", tmp_path)}
    assert verifier.verify_admission(path, tmp_path, audits)["admission_status"] == "DEV_ACCEPTED"
    record["structural_vector"]["difficulty"]["calibrated"] = True
    atomic_json(path, record)
    with pytest.raises(ValueError, match="inconsistent novelty or simulation"):
        verifier.verify_admission(path, tmp_path, audits)


def test_forensic_binding_rechecks_original_bytes_without_claiming_historical_replay(tmp_path, monkeypatch):
    from ioabench.v5.core.trace_integrity import inspect_tool_observations
    monkeypatch.setattr(verifier, "ORIGINAL_ROOT", PureWindowsPath(tmp_path))
    out, source = tmp_path / "out", tmp_path / "source"
    trace = {"actions": [], "records": []}
    raw = {"case_id": "case", "run_id": "run", "trace": trace}
    atomic_json(source / "STRICT_REFERENCE_RESULTS.json", [raw])
    baseline = {"pairs": [{"id": "pair", "source_directory": str(source)}]}
    atomic_json(out / "BASELINE_CENSUS.json", baseline)
    report = {"baseline_file": str(out / "BASELINE_CENSUS.json"),
        "baseline_sha256": verifier.sha(out / "BASELINE_CENSUS.json"), "pair_count": 1, "reference_rows": 1,
        "historical_mismatch_count": 0, "historical_alignment_error_count": 0, "affected_pair_ids": [],
        "current_reanalysis_pass": 1, "current_reanalysis_fail": 0, "provider_calls": 0, "new_generation_requests": 0,
        "original_evidence_modified": False, "strict_historical_replay_claim": False,
        "rows": [{"pair_id": "pair", "row_ordinal": 0, "case_id": "case", "run_id": "run",
                  "source_file": str(source / "STRICT_REFERENCE_RESULTS.json"),
                  "source_sha256": verifier.sha(source / "STRICT_REFERENCE_RESULTS.json"),
                  "historical_observations": inspect_tool_observations(trace),
                  "current_engine_reanalysis": {"checks": {"events": True}, "provider_calls": 0}}]}
    atomic_json(out / "FORENSIC_TRACE_ALIASING.json", report)
    result = verifier.verify_forensic(out, tmp_path, baseline)
    assert result["status"] == "PASS" and result["historical_rows_rechecked"] == 1
    assert result["strict_historical_replay_claim"] is False
    assert result["current_reanalysis_rerun"] == "NOT_RUN_BOUND_REPORT_ONLY"
    report["historical_mismatch_count"] = 1
    atomic_json(out / "FORENSIC_TRACE_ALIASING.json", report)
    with pytest.raises(ValueError, match="aggregates or scientific scope"):
        verifier.verify_forensic(out, tmp_path, baseline)


def test_live_protection_requires_every_hash_but_extracted_scope_labels_omissions(tmp_path):
    out = tmp_path / "out"
    included, omitted = tmp_path / "old/included.json", tmp_path / "old/omitted.json"
    atomic_json(included, {"old": 1})
    atomic_json(omitted, {"old": 2})
    protected = {"old/included.json": verifier.sha(included), "old/omitted.json": verifier.sha(omitted)}
    atomic_json(out / "PROTECTED_BASELINE.json", {"files": protected})
    assert verifier.verify_protected(out, tmp_path, "full")["actual_files_verified"] == 2
    omitted.unlink()
    with pytest.raises(ValueError, match="protected historical evidence missing"):
        verifier.verify_protected(out, tmp_path, "full")
    atomic_json(tmp_path / "_snapshot/FILES.json", [{"path": "old/included.json"}])
    atomic_json(out / "PROTECTED_VERIFICATION.json", {"status": "PASS", "changes": [], "file_count": 2, "provider_calls": 0})
    result = verifier.verify_protected(out, tmp_path, "included")
    assert result["status"] == "PASS_INCLUDED_SUBSET" and result["actual_files_verified"] == 1
    assert result["not_included"] == 1 and result["not_included_status"] == "NOT_INCLUDED"
    assert result["full_history_reverified_here"] == "NOT_RUN_NOT_INCLUDED"
    included.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="protected historical evidence missing or changed"):
        verifier.verify_protected(out, tmp_path, "included")


def test_relocated_actual_cli_resumes_sealed_original_paths_without_provider(tmp_path, audited, monkeypatch):
    from ioabench.v5.ai_generation import development_audit
    from ioabench.v5.ai_generation.development import VERSION as FACTORY_VERSION, structure_vector
    from ioabench.v5.core.case import case_from_dict
    source, study = audited
    root = Path(__file__).resolve().parents[2]
    for name in ("src", "contracts", "config", "scripts/v5"):
        shutil.copytree(root / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__"))
    out = tmp_path / "artifacts/v5/data_factory/dev_auto_audit/fixture"
    directory = out / "reviews/source"
    packet = development_audit.prepare_audit_packet(source)
    packet["source_binding"]["directory"] = "D:/Project/ioa_codex_spec/source"
    # Simulate evidence frozen on D: while all test IO stays in this isolated fixture.
    with monkeypatch.context() as scoped:
        scoped.setattr(development_audit, "_source_check", lambda binding: verifier.verify_files(source, binding["files"]))
        result = asyncio.run(development_audit.audit_packet(study, packet, directory / "audit"))
    control = case_from_dict(verifier.read(source / "PAIR.json")[0], allow_dynamic=True)
    record = {"version": FACTORY_VERSION, "status": "DEV_ACCEPTED", "hard_gate_errors": [],
        "audit_status": result["status"], "source_result_sha256": verifier.sha(source / "RESULT.json"),
        "audit_result_sha256": canonical_sha256(result), "structural_vector": structure_vector(control),
        "recorded_strict_replays": 6, "history_scope": "FULL_HISTORY", "same_model_audit_independent_science": False,
        "formal_accepted": False, "new_scientific_families": 0, "machine_qualified": False,
        "source_directory": "source", "pair_sha256": verifier.sha(source / "PAIR.json"), "suite": "T331", "id": "source"}
    atomic_json(directory / "ADMISSION.json", record)
    before = verifier.inventory(source)
    resumed = verifier.verify_cli(out, tmp_path)
    assert resumed["status"] == "PASS", resumed.get("stderr")
    assert resumed["cli_receipt"]["terminal_admissions"] == 1
    assert resumed["network_guard"]["provider_http_or_external_network_attempts"] == 0
    assert verifier.inventory(source) == before


def test_exact_snapshot_subprocess_actually_replays_and_resumes_complete_matrix(tmp_path):
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.v5.ai_generation.direct_deepseek import strict_checks
    root = Path(__file__).resolve().parents[2]
    revision = tmp_path / "source_revisions" / source_tree_hash(root)
    for name in ("src", "contracts", "config"):
        shutil.copytree(root / name, revision / name, ignore=shutil.ignore_patterns("__pycache__"))
    spec = suite_spec("T331", typed=True)
    compiled = compile_and_gate(spec, program_proposal(spec, seed=193, difficulty="M"), seed=193)
    directory = tmp_path / "candidate"
    directory.mkdir()
    with verifier.no_network():
        strict_checks(directory, spec, compiled)
    jobs, result = tmp_path / "jobs.json", tmp_path / "verification.json"
    atomic_json(jobs, [{"directory": str(directory), "runtime_sha256": revision.name, "required_positive": True}])
    before = verifier.inventory(directory)
    process = subprocess.run([sys.executable, "-B", str(root / "scripts/v5/verify_development_factory.py"),
        "--out", str(tmp_path), "--root", str(tmp_path), "--source", str(revision), "--jobs", str(jobs),
        "--result", str(result)], capture_output=True, text=True, timeout=120)
    assert process.returncode == 0, process.stderr
    report = verifier.read(result)
    assert report["status"] == "PASS" and report["runtime_sha256"] == revision.name
    assert len(report["jobs"][0]["strict_replays"]) == 6
    assert report["jobs"][0]["reference_batch_resumes"] == 3
    assert report["network_guard"]["provider_http_or_external_network_attempts"] == 0
    assert before == verifier.inventory(directory)


def baseline_fixture(root, *, runtime="a" * 64):
    directory = root / "old-run/candidates/retained"
    revision = root / "old-run/source_revisions" / runtime
    revision.mkdir(parents=True)
    atomic_json(directory / "MANIFEST.json", {"source_sha256": runtime})
    atomic_json(directory / "REPLAY.json", [{"passed": True}] * 6)
    (directory / "strict/artifacts/v5/evaluations").mkdir(parents=True)
    return {"baseline_replay_rows": 6, "pairs": [{"id": "retained", "source_directory":
        "D:/Project/ioa_codex_spec/old-run/candidates/retained", "source_runtime_sha256": runtime,
        "reference_replay_rows": 6}]}


def test_baseline_job_resolves_only_packaged_original_runtime_and_preserves_quarantine(tmp_path):
    census = baseline_fixture(tmp_path)
    jobs = verifier.baseline_replay_jobs(census, tmp_path, quarantined_pair_ids=["retained"])
    assert jobs[0]["cohort"] == "baseline" and jobs[0]["required_positive"] is True
    assert jobs[0]["historical_observation_quarantined"] is True
    assert Path(jobs[0]["source_revision_directory"]) == tmp_path / "old-run/source_revisions" / ("a" * 64)
    shutil.rmtree(Path(jobs[0]["source_revision_directory"]))
    with pytest.raises(ValueError, match="baseline source snapshot missing from this package"):
        verifier.baseline_replay_jobs(census, tmp_path)


@pytest.mark.parametrize("mutation,match", [
    ("manifest", "bound source runtime"), ("count", "invented a strict Replay count"),
    ("aggregate", "aggregate strict Replay count"), ("duplicate", "repeats a pair identity"),
])
def test_baseline_job_rejects_runtime_count_and_identity_drift(tmp_path, mutation, match):
    census = baseline_fixture(tmp_path)
    if mutation == "manifest":
        atomic_json(tmp_path / "old-run/candidates/retained/MANIFEST.json", {"source_sha256": "b" * 64})
    elif mutation == "count":
        census["pairs"][0]["reference_replay_rows"] = 7
    elif mutation == "aggregate":
        census["baseline_replay_rows"] = 7
    else:
        census["pairs"] *= 2
    with pytest.raises(ValueError, match=match):
        verifier.baseline_replay_jobs(census, tmp_path)


def test_exact_worker_rejects_source_outside_supplied_root(tmp_path):
    with pytest.raises(ValueError, match="outside --root"):
        verifier.verify_revision([], tmp_path / "outside", tmp_path / "package")


def test_relocated_baseline_exact_source_replay_and_resume_never_read_original_root(tmp_path):
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.v5.ai_generation.direct_deepseek import strict_checks
    project = Path(__file__).resolve().parents[2]
    original, relocated = tmp_path / "original", tmp_path / "extracted"
    runtime = source_tree_hash(project)
    census = baseline_fixture(original, runtime=runtime)
    directory = original / "old-run/candidates/retained"
    revision = original / "old-run/source_revisions" / runtime
    for name in ("src", "contracts", "config"):
        shutil.copytree(project / name, revision / name, ignore=shutil.ignore_patterns("__pycache__"))
    spec = suite_spec("T331", typed=True)
    compiled = compile_and_gate(spec, program_proposal(spec, seed=6193, difficulty="M"), seed=6193)
    with verifier.no_network():
        strict_checks(directory, spec, compiled)
    shutil.copytree(original, relocated)
    assert original.parent == tmp_path
    shutil.rmtree(original)
    jobs = verifier.baseline_replay_jobs(census, relocated, quarantined_pair_ids=["retained"])
    jobs_path, result_path = tmp_path / "baseline-jobs.json", tmp_path / "baseline-result.json"
    atomic_json(jobs_path, jobs)
    before = verifier.inventory(relocated)
    command = [sys.executable, "-B", str(project / "scripts/v5/verify_development_factory.py"),
        "--out", str(relocated), "--root", str(relocated), "--source", jobs[0]["source_revision_directory"],
        "--jobs", str(jobs_path), "--result", str(result_path)]
    process = subprocess.run(command, capture_output=True, text=True, cwd=relocated, timeout=120)
    assert process.returncode == 0, process.stderr
    report = verifier.read(result_path)
    job = report["jobs"][0]
    assert job["cohort"] == "baseline" and job["baseline_id"] == "retained"
    assert job["historical_observation_quarantined"] is True
    assert len(job["strict_replays"]) == 6 and job["reference_batch_resumes"] == 3
    assert report["network_guard"]["provider_http_or_external_network_attempts"] == 0
    assert verifier.inventory(relocated) == before
    Path(jobs[0]["source_revision_directory"]).rename(relocated / "retained-snapshot-outside-expected-location")
    with pytest.raises(ValueError, match="baseline source snapshot missing from this package"):
        verifier.baseline_replay_jobs(census, relocated)
