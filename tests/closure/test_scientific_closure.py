"""Checks must reject tampering even when all stored PASS labels remain true."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
import recover_history_source as history_source
import replay_recovered_sources as recovered_replay
import build_release_metadata_addendum as metadata_addendum
import phase_c_campaign as phase_c

SCRIPT = Path(__file__).parents[2] / "scripts/scientific_closure.py"
spec = importlib.util.spec_from_file_location("scientific_closure", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_dataset_binding_rejects_changed_content_and_cross_manifest_pin():
    cases = [{"candidate_id": str(i), "difficulty": ("easy", "medium", "hard")[i // 30],
              "provenance": {"condition": "CONTROL" if i % 2 else "RISK"}} for i in range(90)]
    manifest = {"status": "FROZEN", "version": "2.0.0", "content_sha256": None}
    manifest["content_sha256"] = audit.canonical_sha256({"manifest": manifest, "cases": cases})
    run = {"benchmark": {"dataset_hashes": {"T311": manifest["content_sha256"]}, "dataset_versions": {"T311": "2.0.0"}}}
    release = {"datasets": {"T311": {"version": "2.0.0", "content_sha256": manifest["content_sha256"]}}}
    assert audit.verify_dataset(manifest, cases, run, release, "T311", "2.0.0")["pass"]
    changed = deepcopy(cases)
    changed[0]["candidate_id"] = changed[1]["candidate_id"]
    assert not audit.verify_dataset(manifest, changed, run, release, "T311", "2.0.0")["pass"]
    run["benchmark"]["dataset_hashes"]["T311"] = "incorrect"
    assert not audit.verify_dataset(manifest, cases, run, release, "T311", "2.0.0")["pass"]


def test_evidence_writer_refuses_overwrite(tmp_path):
    import pytest
    target = tmp_path / "evidence.json"
    audit.write_new(target, {"pass": False})
    with pytest.raises(FileExistsError):
        audit.write_new(target, {"pass": True})
    assert audit.read_json(target) == {"pass": False}


def test_recorded_responses_reject_future_messages_and_repeated_consumption():
    import asyncio
    from ioabench.models import ModelProfile, ModelRequest
    import pytest
    request = {"messages": [{"role": "user", "content": "visible now"}], "tools": [],
               "parameters": {}, "role_metadata": {"agent_id": "one"}}
    replay = audit.RecordedResponses([{"request": request, "response": {"text": "done", "model_id": "tested"}}])
    profile = ModelProfile("replay", "tested", {}, {})
    future = deepcopy(request)
    future["messages"].append({"role": "tool", "content": "future evidence"})
    with pytest.raises(audit.MissingRecordedRequest):
        asyncio.run(replay.generate(profile, ModelRequest(**future)))
    assert asyncio.run(replay.generate(profile, ModelRequest(**request))).text == "done"
    with pytest.raises(audit.MissingRecordedRequest):
        asyncio.run(replay.generate(profile, ModelRequest(**request)))


def test_offline_trace_guard_allows_windows_loop_and_reproduces_frozen_case():
    report = audit.trace_replay("T312", 1, False)
    assert report["network_forbidden"]
    assert report["pass"]


def test_baseline_resume_policy_audit_detects_terminal_invalid_retry():
    # INVALID_MODEL_OUTPUT is terminal and must not be rewritten as COMPLETED.
    report = audit.reproduce_invalid_resume()
    assert report["completed_result_preserved"]
    assert report["after_statuses"]["INVALID_MODEL_OUTPUT"] == "INVALID_MODEL_OUTPUT"
    assert report["frozen_policy_satisfied"]


def test_history_reader_ignores_assistant_claims_and_wrong_dataset(tmp_path):
    tool = lambda command, output: {"type": "tool", "state": {"input": {"command": command}, "output": output}}
    history = {"messages": [{"id": "m1", "time_created": 0, "parts": [
        {"id": "wrong", "part": tool("read deepseek-v4.1-flash-T323-2.3.0-formal", "T323 formal: 90 {'COMPLETED': 70, 'INVALID_MODEL_OUTPUT': 20}")},
        {"id": "assistant", "part": {"type": "text", "text": "T323 formal: 90 {'COMPLETED': 70, 'INVALID_MODEL_OUTPUT': 20}"}},
    ]}]}
    path = tmp_path / "export.json"
    audit.write_new(path, history)
    report = audit.historical_status_observations(path)
    assert report["observations"] == []


def test_state_check_rejects_cycle_and_incorrect_count(tmp_path):
    import yaml
    directory = tmp_path / "state"
    directory.mkdir()
    queue = {"version": 1, "summary": {"task_count": 1}, "milestones": {"m": {"exit_task": "a"}},
             "queue_policy": {"status_values": ["in_progress"]},
             "items": [{"id": "a", "milestone": "m", "status": "in_progress", "depends_on": []}]}
    state = {"work_queue_version": 1, "work_queue_task_count": 1, "in_progress": ["a"], "next_task": "a", "next": ["a"]}
    (directory / "PROJECT_STATE.yaml").write_text(yaml.safe_dump(state), encoding="utf-8")
    path = directory / "WORK_QUEUE.yaml"
    path.write_text(yaml.safe_dump(queue), encoding="utf-8")
    assert audit.state_check(tmp_path)["pass"]
    queue["items"][0]["depends_on"] = ["a"]
    queue["summary"]["task_count"] = 2
    path.write_text(yaml.safe_dump(queue), encoding="utf-8")
    report = audit.state_check(tmp_path)
    assert not report["pass"]
    assert not report["checks"]["dag_acyclic"]
    assert not report["checks"]["task_counts_match"]


def test_windows_snapshot_hash_matches_disk_and_detects_changes():
    files = {p.relative_to(audit.ROOT).as_posix(): p.read_bytes() for d in ("src", "contracts", "config")
             for p in (audit.ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    expected = audit.source_tree_hash(audit.ROOT)
    assert audit.windows_snapshot_hash(files) == expected
    files["src/ioabench/models/types.py"] += b"\n"
    assert audit.windows_snapshot_hash(files) != expected


def test_source_filtered_replay_does_not_pass_empty_coverage():
    report = audit.trace_replay("T312", 1, False, source_hash_filter="not-a-recorded-source")
    assert not report["pass"]


def test_replay_supports_historical_dispatcher_without_auxiliary_argument(monkeypatch):
    from ioabench.runtime import construct_dispatch
    current = construct_dispatch.execute_construct_case
    async def historical(root, suite, case, model, profile, *, run_id):
        return await current(root, suite, case, model, profile, run_id=run_id)
    monkeypatch.setattr(construct_dispatch, "execute_construct_case", historical)
    assert audit.trace_replay("T312", 1, False)["pass"]


def test_literal_history_reconstruction_does_not_execute_and_drops_unknown_values(tmp_path):
    import pytest
    target = tmp_path / "must-not-exist"
    files = {"src/example.py": b"old\r\n"}
    commits = []
    def commit(name, data):
        files[name] = data
        commits.append((name, data))
    source = f'''from pathlib import Path
__import__('pathlib').Path({str(target)!r}).write_text('executed')
p = Path('src/example.py')
s = p.read_text(encoding='utf-8').replace('old', 'new')
p.write_text(s, encoding='utf-8')
s = unknown_transform(s)
p.write_text(s)
s = 'stale'
s += unknown_value
p.write_text(s)
p.write_text('invalid newline', newline='')
'''
    assert history_source.python_writes(source, files, commit) == 6
    assert not target.exists()
    assert commits == [("src/example.py", b"new\r\n")]
    for path in ("../src/x", "src/../x", "C:/outside/src/x", "D:src/x", "src/x:stream", "src/./x", "config//x", "data/x"):
        with pytest.raises(ValueError): history_source.source_path(path)


def test_source_variant_search_only_accepts_exact_hashes():
    initial = {"src/A.py": b"old", "src/b.py": b"stable", "config/deleted.json": b"{}"}
    expected = {"src/A.py": b"new", "src/b.py": b"stable"}
    target = audit.windows_snapshot_hash(expected)
    trials, matches = history_source.combine_variants(initial, {"src/A.py": [b"old", b"new"], "config/deleted.json": [b"{}", None]}, {target, "not-a-hash"})
    assert trials == 4
    assert matches == {target: expected}
    assert recovered_replay.snapshot_hash(expected) == target


def test_history_replay_loader_rejects_changed_bytes_and_source_hash(tmp_path, monkeypatch):
    import hashlib
    import pytest
    from zipfile import ZipFile
    monkeypatch.setattr(recovered_replay, "ROOT", tmp_path)
    archive_path = tmp_path / "base.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("src/example.py", b"old")
        archive.writestr("config/deleted.json", b"{}")
    blob = tmp_path / "source-bytes"
    blob.write_bytes(b"new")
    expected = {"src/example.py": b"new"}
    digest = audit.windows_snapshot_hash(expected)
    recovery = {"artifact": "LITERAL_HISTORY_SOURCE_RECOVERY", "recovered": {digest: {
        "base_archive": {"path": "base.zip", "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()},
        "overrides": {"src/example.py": {"path": "source-bytes", "sha256": hashlib.sha256(b"new").hexdigest()}},
        "file_hashes": {"src/example.py": hashlib.sha256(b"new").hexdigest()}}}}
    assert recovered_replay.recovered_files(recovery, digest) == expected
    recovery["recovered"]["wrong"] = recovery["recovered"][digest]
    with pytest.raises(AssertionError): recovered_replay.recovered_files(recovery, "wrong")
    blob.write_bytes(b"tampered")
    with pytest.raises(AssertionError): recovered_replay.recovered_files(recovery, digest)


def test_metadata_addendum_rejects_tampering_and_separates_models_and_defaults():
    import pytest
    request = {"messages": [{"role": "system", "content": "role instructions"}, {"role": "user", "content": "task"}],
               "role_metadata": {"role": "selector", "agent_id": "one"}, "tools": [],
               "parameters": {"temperature": 0.0, "max_tokens": 4096}}
    record = {"record_id": "r1", "request": request, "request_sha256": audit.canonical_sha256(request),
              "response": {"model_id": "deepseek-v4.1-flash", "provider_metadata": {"model": "provider-alias"}}}
    results = {"unit": {"case_id": "case", "replay": {"model_records": [record]}}}
    ledger = [{"unit_id": "unit", "case_id": "case", "record_id": "r1", "role": "selector",
        "request_sha256": record["request_sha256"], "system_prompt_sha256": audit.canonical_sha256(request["messages"][:1]),
        "initial_task_sha256": audit.canonical_sha256(request["messages"][1]), "tool_schema_sha256": audit.canonical_sha256([])}]
    roles, profiles = metadata_addendum.summarize_records(results, ledger)
    assert roles["selector"]["role_metadata_hashes"] == [audit.canonical_sha256(request["role_metadata"])]
    assert profiles["selector"]["requested_model_id"] == "deepseek-v4.1-flash"
    assert profiles["selector"]["provider_returned_model_ids"] == {"provider-alias": 1}
    parameters = profiles["selector"]["parameter_profiles"][0]
    assert parameters["max_tokens"] == 4096 and parameters["top_p"] == "PROVIDER_DEFAULT_UNSET"
    assert parameters["tool_choice"] == "PROVIDER_DEFAULT_UNSET"
    changed = deepcopy(results)
    changed["unit"]["replay"]["model_records"][0]["request"]["tools"] = [{"name": "other"}]
    with pytest.raises(ValueError): metadata_addendum.summarize_records(changed, ledger)
    changed = deepcopy(results)
    changed["unit"]["replay"]["model_records"][0]["response"]["model_id"] = "glm-5.3-flash"
    with pytest.raises(ValueError): metadata_addendum.summarize_records(changed, ledger)
    with pytest.raises(ValueError): metadata_addendum.summarize_records(results, [])
    with pytest.raises(ValueError): metadata_addendum.summarize_records({}, [])


def test_phase_c_excludes_unaccepted_runs_without_loading_their_scores(monkeypatch):
    import pytest
    binding = audit.read_json(audit.ROOT / "artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v3.json")
    def forbidden_load(*args):
        raise AssertionError("unaccepted scores must not enter aggregation")
    monkeypatch.setattr(phase_c, "load_run", forbidden_load)
    runs, excluded = phase_c.select_canonical_runs(binding)
    assert runs == {} and len(excluded) == 18
    assert sum(row["simulation_only"] for row in excluded) == 3
    binding["suites"][0]["canonical_accepted"] = True
    with pytest.raises(ValueError, match="conflicts with binding level"):
        phase_c.select_canonical_runs(binding)


def test_phase_c_acceptance_requires_every_component_and_resolved_deviation():
    names = ("BENCHMARK_IMPLEMENTATION_ACCEPTANCE", "DATASET_PACK_ACCEPTANCE",
             "CANONICAL_BINDING_ACCEPTANCE", "DEEPSEEK_CANONICAL_CAMPAIGN_ACCEPTANCE")
    snapshot = {"pass": True, "verdict": "PASS", "phase_c_and_delivery": {"pass": True},
                "components": {k: {"artifact": name, "pass": True, "verdict": "PASS"} for k, name in zip("ABCD", names)}}
    assert all(phase_c.acceptance_checks(snapshot, 18, "NON_MATERIAL", True).values())
    assert not all(phase_c.acceptance_checks(snapshot, 18, "UNKNOWN", True).values())
    assert not all(phase_c.acceptance_checks(snapshot, 17, "NON_MATERIAL", True).values())
    snapshot["components"].pop("D")
    snapshot["metadata_addendum"] = {"integrity_pass": True}
    assert not all(phase_c.acceptance_checks(snapshot, 18, "NON_MATERIAL", True).values())


def test_phase_c_rejects_changed_evidence_and_uses_exact_manifest(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(phase_c, "ROOT", tmp_path)
    target = tmp_path / "evidence.json"
    audit.write_new(target, {"pass": True})
    envelope = tmp_path / "envelope.json"
    audit.write_new(envelope, {"ref": {"path": "evidence.json", "sha256": audit.sha256(target)}})
    assert phase_c.checked_json(envelope)["ref"]["sha256"] == audit.sha256(target)
    target.write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError): phase_c.checked_json(envelope)
    run = tmp_path / "correct-run"
    audit.write_new(run / "results.json", {})
    audit.write_new(run / "manifest/aaa-decoy.json", {"run_id": "wrong"})
    audit.write_new(run / "manifest/correct-run.json", {"run_id": "correct-run"})
    assert phase_c.load_run(run)["manifest"]["run_id"] == "correct-run"
