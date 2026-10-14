"""Engineering batches consume supplied cases and preserve attempts, identity, and replay."""
from __future__ import annotations

import json
import asyncio
from dataclasses import replace

import pytest

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.models import ModelProfile, ModelRequest, ModelResponse
from ioabench.v5 import evaluation, replay
from ioabench.v5.core.case import SUITES
from ioabench.v5.dynamic import registry
from ioabench.v5.suites import load

REFERENCE_PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
ONLINE_PROFILE = ModelProfile("aihubmix", "deepseek-v4.1-flash", {"tools": True}, {})
IDENTITY = {"body_model": "deepseek-v4-1-flash-260910", "gateway_model": "deepseek-v4.1-flash"}


@pytest.fixture(autouse=True)
def stable_test_source(monkeypatch):
    # Other agents edit the shared source concurrently; pin a test source identity explicitly.
    monkeypatch.setattr(evaluation, "source_tree_hash", lambda root: "unit-test-source")
    monkeypatch.setattr(replay, "source_tree_hash", lambda root: "unit-test-source")


def _cases_file(tmp_path, structures=("T311",)):
    cases = []
    for suite_id in structures:
        adapter = load(suite_id) if suite_id in SUITES else registry.get_adapter(suite_id)
        cases.extend(adapter.generate(seed=11, families=1)[0])
    path = tmp_path / "input.jsonl"
    path.write_text("".join(json.dumps(case.as_dict()) + "\n" for case in cases), encoding="utf-8")
    return path, cases


def _rows(tmp_path, run_id):
    return evaluation.read_results(tmp_path / "artifacts/v5/evaluations" / run_id)


def _reference_run(tmp_path, path, run_id="reference", **kwargs):
    return evaluation.run_batch(tmp_path, path, run_id=run_id, profile=REFERENCE_PROFILE,
                                reference_policy="witness", parameters={"temperature": 0.0}, **kwargs)


def test_all_classic_and_dynamic_json_cases_run_resume_and_replay(tmp_path, monkeypatch):
    structures = list(SUITES) + registry.implemented()
    path, cases = _cases_file(tmp_path, structures)
    report = _reference_run(tmp_path, path)
    assert report["scheduled_cases"] == report["observed_cases"] == 74
    rows = _rows(tmp_path, "reference")
    assert len(rows) == 74
    assert {row["suite_id"] for row in rows} == set(structures)
    for row in rows:
        assert row["status"] == "COMPLETED", (row["case_id"], row.get("error"))
        assert row["score"]["safety"] == "SAFE"
        assert row["monitor_report"]["ledger_integrity"]["passed"]
        assert row["simulation_only"] == (row["suite_id"].split("-")[0] in {"T361", "T362", "T363"})
    directory = tmp_path / "artifacts/v5/evaluations/reference"
    journal_before = {p: p.read_bytes() for p in (tmp_path / "data/runs/reference").rglob("*.jsonl")}
    result_before = (directory / "results.jsonl").read_bytes()
    monkeypatch.setattr(evaluation, "execute_case", lambda *a, **k: pytest.fail("resume re-executed a terminal case"))
    resumed = _reference_run(tmp_path, path, resume=True)
    assert resumed == report
    assert (directory / "results.jsonl").read_bytes() == result_before
    assert all(p.read_bytes() == value for p, value in journal_before.items())
    assert len(list((directory / "reports").glob("report-*"))) == 2
    for case in cases:
        result = replay.replay_case(tmp_path, "reference", case.case_id)
        assert result["passed"], (case.case_id, result)
        assert result["provider_calls"] == 0
    assert all(p.read_bytes() == value for p, value in journal_before.items())


def test_replay_rejects_duplicate_terminal_results(tmp_path):
    path, cases = _cases_file(tmp_path)
    _reference_run(tmp_path, path)
    directory = tmp_path / "artifacts/v5/evaluations/reference"
    rows = _rows(tmp_path, "reference")
    with (directory / "results.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(rows[0], ensure_ascii=False) + "\n")
    result = replay.replay_case(tmp_path, "reference", cases[0].case_id)
    assert result["passed"] is False
    assert result["status"] == "DUPLICATE_TERMINAL_RESULTS"


def test_reanalysis_is_explicit_and_does_not_relax_historical_replay(tmp_path, monkeypatch):
    path, cases = _cases_file(tmp_path, ("T333", "T361"))
    _reference_run(tmp_path, path)
    result_path = tmp_path / "artifacts/v5/evaluations/reference/results.jsonl"
    original = result_path.read_bytes()
    monkeypatch.setattr(replay, "source_tree_hash", lambda root: "new-analysis-source")
    with pytest.raises(ValueError, match="source differs"):
        replay.replay_case(tmp_path, "reference", cases[0].case_id)
    for case in cases:
        result = replay.reanalyse_case(tmp_path, "reference", case.case_id)
        assert result["passed"] and result["outcome_unchanged"]
        assert result["original_source_sha256"] == "unit-test-source"
        assert result["analysis_source_sha256"] == "new-analysis-source"
        assert result["provider_calls"] == 0 and all(result["behavior_checks"].values())
    assert result_path.read_bytes() == original


def test_reanalysis_rejects_changed_recorded_behavior(tmp_path):
    path, cases = _cases_file(tmp_path)
    _reference_run(tmp_path, path)
    directory = tmp_path / "artifacts/v5/evaluations/reference"
    rows = evaluation.read_results(directory)
    rows[0]["trace"]["final_state"]["tampered"] = True
    (directory / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="changed recorded behavior"):
        replay.reanalyse_case(tmp_path, "reference", cases[0].case_id)


@pytest.mark.parametrize("changed", ["case", "parameters", "profile", "source"])
def test_resume_refuses_pinned_input_or_execution_drift(tmp_path, monkeypatch, changed):
    path, cases = _cases_file(tmp_path)
    _reference_run(tmp_path, path)
    before = (tmp_path / "artifacts/v5/evaluations/reference/results.jsonl").read_bytes()
    kwargs = {"parameters": {"temperature": 0.0}, "profile": REFERENCE_PROFILE}
    if changed == "case":
        raw = [case.as_dict() for case in cases]
        for item in raw:
            item["world"]["engineering_note"] = "changed input"
        path.write_text("".join(json.dumps(item) + "\n" for item in raw), encoding="utf-8")
    elif changed == "parameters":
        kwargs["parameters"] = {"temperature": 0.5}
    elif changed == "profile":
        kwargs["profile"] = replace(REFERENCE_PROFILE, model_id="another-reference")
    else:
        monkeypatch.setattr(evaluation, "source_tree_hash", lambda root: "changed-source")
    with pytest.raises(ValueError, match="manifest mismatch"):
        evaluation.run_batch(tmp_path, path, run_id="reference", reference_policy="witness", resume=True, **kwargs)
    assert (tmp_path / "artifacts/v5/evaluations/reference/results.jsonl").read_bytes() == before


@pytest.mark.parametrize("identifier", ["../escape", "a/b", "a\\b", "CON", "NUL.txt", "trailing."])
def test_unsafe_run_case_and_replay_paths_are_rejected(tmp_path, identifier):
    path, cases = _cases_file(tmp_path)
    with pytest.raises(ValueError, match="unsafe"):
        _reference_run(tmp_path, path, run_id=identifier)
    raw = [case.as_dict() for case in cases]
    raw[0]["case_id"] = identifier
    path.write_text("".join(json.dumps(item) + "\n" for item in raw), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe"):
        evaluation.read_cases(path)
    with pytest.raises(ValueError, match="unsafe"):
        replay.replay_case(tmp_path, "reference", identifier)


def test_incomplete_or_duplicate_pairs_are_rejected_before_execution(tmp_path):
    path, cases = _cases_file(tmp_path)
    path.write_text(json.dumps(cases[0].as_dict()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        evaluation.read_cases(path)
    path.write_text("".join(json.dumps(c.as_dict()) + "\n" for c in (cases[0], cases[0], cases[1])), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        evaluation.read_cases(path)


def test_historical_run_id_is_rejected_without_touching_old_evidence(tmp_path):
    path, _ = _cases_file(tmp_path)
    historical = tmp_path / "data/runs/reference/attempts/historical-case/attempt-1.jsonl"
    historical.parent.mkdir(parents=True)
    historical.write_text('{"historical": true}\n', encoding="utf-8")
    retained = historical.read_bytes()
    with pytest.raises(FileExistsError, match="already has evidence"):
        _reference_run(tmp_path, path)
    assert historical.read_bytes() == retained
    assert not (tmp_path / "artifacts/v5/evaluations/reference/manifest.json").exists()


def test_one_bad_case_does_not_stop_other_cases(tmp_path, monkeypatch):
    path, cases = _cases_file(tmp_path)
    execute = evaluation.execute_case

    def fail_first_case(root, case, *args):
        if case.case_id == cases[0].case_id:
            raise ValueError("invalid scenario wiring")
        return execute(root, case, *args)

    monkeypatch.setattr(evaluation, "execute_case", fail_first_case)
    report = _reference_run(tmp_path, path)
    rows = _rows(tmp_path, "reference")
    assert [row["status"] for row in rows] == ["ENGINEERING_ERROR", "COMPLETED"]
    assert rows[0]["scientifically_eligible"] is False
    assert rows[0]["ineligibility_reasons"] == ["ENGINEERING_ERROR"]
    assert report["observed_cases"] == 2
    monkeypatch.setattr(evaluation, "execute_case", lambda *a, **k: pytest.fail("terminal case re-executed"))
    assert _reference_run(tmp_path, path, resume=True) == report


def test_resume_rejects_tampered_saved_case_snapshot(tmp_path):
    path, _ = _cases_file(tmp_path)
    _reference_run(tmp_path, path)
    saved = tmp_path / "artifacts/v5/evaluations/reference/cases.jsonl"
    raw = [json.loads(line) for line in saved.read_text(encoding="utf-8").splitlines()]
    raw[0]["world"]["engineering_note"] = "tampered saved input"
    saved.write_text("".join(json.dumps(item) + "\n" for item in raw), encoding="utf-8")
    retained = saved.read_bytes()
    with pytest.raises(ValueError, match="saved run inputs differ"):
        _reference_run(tmp_path, path, resume=True)
    assert saved.read_bytes() == retained


def test_transient_failures_are_bounded_across_resume(tmp_path):
    class FailingPort:
        calls = 0

        async def generate(self, profile, request):
            self.calls += 1
            raise ProviderTransientError("temporary outage")

    path, _ = _cases_file(tmp_path)
    port = FailingPort()
    kwargs = dict(run_id="bounded", profile=ONLINE_PROFILE, port=port,
                  expected_identity=IDENTITY, max_attempts=2)
    report = evaluation.run_batch(tmp_path, path, **kwargs)
    assert port.calls == 4
    assert all(row["status"] == "RETRYABLE_INFRA_FAILURE" for row in _rows(tmp_path, "bounded"))
    assert report["suites"]["T311"]["eligible_cases"] == 0
    resumed = evaluation.run_batch(tmp_path, path, resume=True, **kwargs)
    assert port.calls == 4
    assert resumed == report


def test_identity_drift_is_retained_and_never_executes_tool_actions(tmp_path):
    class WrongIdentityPort:
        calls = 0

        async def generate(self, profile, request):
            self.calls += 1
            return ModelResponse("proposed action", tool_calls=({"id": "wrong", "type": "function",
                                 "function": {"name": request.tools[0]["function"]["name"], "arguments": "{}"}},),
                                 provider_metadata={"model": IDENTITY["body_model"],
                                 "transport_metadata": {"x-aihubmix-model": "another-model"}},
                                 model_id=profile.model_id, finish_reason="tool_calls")

    path, _ = _cases_file(tmp_path)
    port = WrongIdentityPort()
    report = evaluation.run_batch(tmp_path, path, run_id="identity", profile=ONLINE_PROFILE,
                                  port=port, expected_identity=IDENTITY)
    assert port.calls == 2
    assert report["suites"]["T311"]["eligible_cases"] == 0
    for row in _rows(tmp_path, "identity"):
        assert "MODEL_IDENTITY_MISMATCH" in row["ineligibility_reasons"]
        assert not (row.get("trace") or {}).get("actions")
        journal = tmp_path / row["attempt_journal"]["path"]
        records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        assert any(entry.get("record", {}).get("identity_rejected") for entry in records)


def test_provider_failure_after_observed_behavior_is_never_retried(tmp_path):
    class InterruptedPort:
        calls = 0
        witness = load("T311").policies()["witness"]

        async def generate(self, profile, request):
            self.calls += 1
            if any(message["role"] == "assistant" for message in request.messages):
                raise ProviderTransientError("outage after an observed response")
            response = await self.witness.generate(profile, request)
            return replace(response, model_id=profile.model_id,
                           provider_metadata={"model": IDENTITY["body_model"],
                           "transport_metadata": {"x-aihubmix-model": IDENTITY["gateway_model"]}})

    path, _ = _cases_file(tmp_path)
    port = InterruptedPort()
    kwargs = dict(run_id="observed", profile=ONLINE_PROFILE, port=port,
                  expected_identity=IDENTITY, max_attempts=3)
    evaluation.run_batch(tmp_path, path, **kwargs)
    assert port.calls == 4
    rows = _rows(tmp_path, "observed")
    assert [row["status"] for row in rows] == ["INFRA_INTERRUPTED", "INFRA_INTERRUPTED"]
    for row in rows:
        assert not row["scientifically_eligible"]
        journal = tmp_path / row["attempt_journal"]["path"]
        assert sum(json.loads(line).get("kind") == "model_record"
                   for line in journal.read_text(encoding="utf-8").splitlines()) == 1
    evaluation.run_batch(tmp_path, path, resume=True, **kwargs)
    assert port.calls == 4


def test_process_crash_after_responses_recovers_without_reexecuting_case(tmp_path, monkeypatch):
    class SimulatedProcessStop(BaseException):
        pass

    path, cases = _cases_file(tmp_path)
    execute = evaluation.execute_case
    executed = []

    def crash_after_response(root, case, *args):
        executed.append(case.case_id)
        execute(root, case, *args)
        raise SimulatedProcessStop("simulated process stop before result persistence")

    monkeypatch.setattr(evaluation, "execute_case", crash_after_response)
    with pytest.raises(SimulatedProcessStop, match="process stop"):
        _reference_run(tmp_path, path, run_id="crash")
    assert executed == [cases[0].case_id]
    journal = next((tmp_path / "data/runs/crash").rglob("attempt-*.jsonl"))
    retained = journal.read_bytes()

    def continue_other_case(root, case, *args):
        assert case.case_id != cases[0].case_id
        executed.append(case.case_id)
        return execute(root, case, *args)

    monkeypatch.setattr(evaluation, "execute_case", continue_other_case)
    report = _reference_run(tmp_path, path, run_id="crash", resume=True)
    rows = _rows(tmp_path, "crash")
    assert [row["status"] for row in rows] == ["INFRA_INTERRUPTED", "COMPLETED"]
    assert rows[0]["model_calls"] > 0
    assert not rows[0]["scientifically_eligible"]
    assert executed == [case.case_id for case in cases]
    assert journal.read_bytes() == retained
    checkpoint = json.loads((tmp_path / "artifacts/v5/evaluations/crash/checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["completed"] == 2 and checkpoint["retryable_unfinished"] == 0
    assert report["observed_cases"] == 2


def test_torn_result_tail_is_preserved_and_recovery_uses_new_segment(tmp_path, monkeypatch):
    path, cases = _cases_file(tmp_path)
    _reference_run(tmp_path, path)
    directory = tmp_path / "artifacts/v5/evaluations/reference"
    results = directory / "results.jsonl"
    lines = results.read_bytes().splitlines(keepends=True)
    results.write_bytes(lines[0] + lines[1][:len(lines[1]) // 2])
    retained = results.read_bytes()
    monkeypatch.setattr(evaluation, "execute_case", lambda *a, **k: pytest.fail("journalled behavior re-executed"))
    resumed = _reference_run(tmp_path, path, resume=True)
    rows = _rows(tmp_path, "reference")
    assert results.read_bytes() == retained
    assert (directory / "results-2.jsonl").exists()
    assert [(row["case_id"], row["status"]) for row in rows] == [
        (cases[0].case_id, "COMPLETED"), (cases[1].case_id, "INFRA_INTERRUPTED")]
    assert resumed["observed_cases"] == 2
    assert not rows[1]["scientifically_eligible"]
    assert replay.replay_case(tmp_path, "reference", cases[0].case_id)["passed"]
    assert replay.replay_case(tmp_path, "reference", cases[1].case_id)["status"] == "NO_COMPLETE_TRACE"


def test_torn_journal_tail_is_preserved_and_recorded_case_is_not_reexecuted(tmp_path, monkeypatch):
    class SimulatedProcessStop(BaseException):
        pass

    path, cases = _cases_file(tmp_path)
    execute = evaluation.execute_case

    def crash(root, case, *args):
        execute(root, case, *args)
        raise SimulatedProcessStop()

    monkeypatch.setattr(evaluation, "execute_case", crash)
    with pytest.raises(SimulatedProcessStop):
        _reference_run(tmp_path, path, run_id="torn-journal")
    journal = next((tmp_path / "data/runs/torn-journal").rglob("attempt-*.jsonl"))
    with journal.open("ab") as stream:
        stream.write(b'{"kind":"model_record","record":')
    retained = journal.read_bytes()

    def continue_other(root, case, *args):
        assert case.case_id != cases[0].case_id
        return execute(root, case, *args)

    monkeypatch.setattr(evaluation, "execute_case", continue_other)
    report = _reference_run(tmp_path, path, run_id="torn-journal", resume=True)
    assert journal.read_bytes() == retained
    assert [row["status"] for row in _rows(tmp_path, "torn-journal")] == ["INFRA_INTERRUPTED", "COMPLETED"]
    assert report["observed_cases"] == 2


@pytest.mark.parametrize("tamper", ["case", "responses", "journal_path", "source"])
def test_strict_replay_rejects_evidence_or_source_drift(tmp_path, monkeypatch, tamper):
    path, cases = _cases_file(tmp_path)
    _reference_run(tmp_path, path)
    directory = tmp_path / "artifacts/v5/evaluations/reference"
    if tamper == "source":
        monkeypatch.setattr(replay, "source_tree_hash", lambda root: "changed-source")
    elif tamper == "case":
        raw = [json.loads(line) for line in (directory / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
        raw[0]["world"]["engineering_note"] = "tampered"
        (directory / "cases.jsonl").write_text("".join(json.dumps(item) + "\n" for item in raw), encoding="utf-8")
    else:
        rows = _rows(tmp_path, "reference")
        if tamper == "responses":
            rows[0]["trace"]["records"][0]["response"]["text"] = "tampered provider response"
        else:
            rows[0]["attempt_journal"]["path"] = "../outside.jsonl"
        (directory / "results.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        replay.replay_case(tmp_path, "reference", cases[0].case_id)


@pytest.mark.parametrize("body_model,gateway_model,accepted", [
    ("deepseek-v4-1-flash-260910", "deepseek-v4.1-flash", True),
    ("deepseek-v4.1-flash", "deepseek-v4.1-flash", True),
    ("deepseek-v4-1-flash-261001", "deepseek-v4.1-flash", False),
    ("deepseek-v4.1-flash-extra", "deepseek-v4.1-flash", False),
    ("prefix-deepseek-v4.1-flash", "deepseek-v4.1-flash", False),
    ("deepseek-v4.1-flash", "other-model", False),
    ("deepseek-v4-1-flash-260910", "deepseek-v4.1-flash-extra", False),
])
def test_identity_guard_accepts_only_frozen_exact_body_aliases(body_model, gateway_model, accepted):
    class Port:
        async def generate(self, profile, request):
            return ModelResponse("response", model_id=profile.model_id,
                                 provider_metadata={"model": body_model,
                                 "transport_metadata": {"x-aihubmix-model": gateway_model}})

    expected = {**IDENTITY, "body_aliases": [IDENTITY["body_model"], ONLINE_PROFILE.model_id]}
    guard = evaluation.IdentityGuard(Port(), expected)
    request = ModelRequest(({"role": "user", "content": "task"},), {})
    if accepted:
        assert asyncio.run(guard.generate(ONLINE_PROFILE, request)).text == "response"
    else:
        with pytest.raises(ProviderPermanentError, match="MODEL_IDENTITY_MISMATCH"):
            asyncio.run(guard.generate(ONLINE_PROFILE, request))


def test_identity_without_alias_list_preserves_the_original_exact_body_contract():
    class Port:
        async def generate(self, profile, request):
            return ModelResponse("response", model_id=profile.model_id,
                                 provider_metadata={"model": profile.model_id,
                                 "transport_metadata": {"x-aihubmix-model": IDENTITY["gateway_model"]}})

    guard = evaluation.IdentityGuard(Port(), IDENTITY)
    with pytest.raises(ProviderPermanentError, match="MODEL_IDENTITY_MISMATCH"):
        asyncio.run(guard.generate(ONLINE_PROFILE, ModelRequest(({"role": "user", "content": "task"},), {})))


def test_body_alias_set_is_pinned_before_run_and_cannot_drift_on_resume(tmp_path):
    class Port:
        calls = 0

        async def generate(self, profile, request):
            self.calls += 1
            return ModelResponse("no action", model_id=profile.model_id,
                                 provider_metadata={"model": IDENTITY["body_model"],
                                 "transport_metadata": {"x-aihubmix-model": IDENTITY["gateway_model"]}})

    path, _ = _cases_file(tmp_path)
    port = Port()
    expected = {**IDENTITY, "body_aliases": [IDENTITY["body_model"], ONLINE_PROFILE.model_id]}
    evaluation.run_batch(tmp_path, path, run_id="aliases", profile=ONLINE_PROFILE, port=port,
                         expected_identity=expected)
    directory = tmp_path / "artifacts/v5/evaluations/aliases"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["expected_identity"]["body_aliases"] == expected["body_aliases"]
    before = (directory / "results.jsonl").read_bytes()
    calls_before = port.calls
    changed = {**expected, "body_aliases": [IDENTITY["body_model"]]}
    with pytest.raises(ValueError, match="manifest mismatch"):
        evaluation.run_batch(tmp_path, path, run_id="aliases", profile=ONLINE_PROFILE, port=port,
                             expected_identity=changed, resume=True)
    assert port.calls == calls_before
    assert (directory / "results.jsonl").read_bytes() == before
