"""V4 strict-retry contract tests.

These tests lock the scientific guarantees of the v4 release:
  * INVALID_MODEL_OUTPUT and INFRA_INTERRUPTED are terminal and never re-queued
  * only a zero-behaviour infrastructure failure is resumable
  * non-infrastructure exceptions are terminal FAILED, never an infra retry
  * attempt evidence is retained and attempts are never overwritten
  * the checkpoint/resume cycle is idempotent

They target the v4 candidate tree, which is a separate source tree from the
frozen v3.2 workspace, and are therefore run as their own pytest invocation
(see tests/v4/conftest.py). Running them in the same process as the workspace
suites would let the editable-installed workspace `ioabench` win the import race.

Run: python -B -X utf8 -m pytest tests/v4 -q
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CANDIDATE = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v11"
if not (CANDIDATE / "src/ioabench").is_dir():
    pytest.skip("v4 candidate tree is not present", allow_module_level=True)

import ioabench  # noqa: E402

if not Path(ioabench.__file__).resolve().is_relative_to(CANDIDATE.resolve()):
    pytest.skip("v4 tests require the candidate tree; run pytest tests/v4 on its own",
                allow_module_level=True)

from ioabench.core.types import RunState  # noqa: E402
from ioabench.errors import ProviderPermanentError, ProviderTransientError  # noqa: E402
from ioabench.runtime.batch import BatchRunner, RESUMABLE_STATUSES, TERMINAL_STATUSES  # noqa: E402
from ioabench.runtime.run_gates import evaluate_run  # noqa: E402
from ioabench.runtime.scheduler import WorkUnit  # noqa: E402
from ioabench.runtime.scientific_io import AttemptJournal, attempt_counter  # noqa: E402


def _resumable(**overrides):
    entry = {"status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 0,
             "valid_model_behavior_observed": False, "infrastructure_failure": True}
    entry.update(overrides)
    return entry


def test_infra_interrupted_is_a_declared_terminal_state():
    assert str(RunState.INFRA_INTERRUPTED) == "INFRA_INTERRUPTED"
    assert "INFRA_INTERRUPTED" in TERMINAL_STATUSES
    assert "INVALID_MODEL_OUTPUT" in TERMINAL_STATUSES
    assert RESUMABLE_STATUSES == {"RETRYABLE_INFRA_FAILURE"}


@pytest.mark.parametrize("status", ["COMPLETED", "INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED",
                                    "FAILED", "CANCELLED", "INVALID_RUN", "UNSUPPORTED"])
def test_terminal_states_are_never_resumed(status):
    runner = BatchRunner(Path("unused.json"))
    assert runner.is_resumable({"status": status}) is False


def test_only_zero_behaviour_infrastructure_failure_is_resumable():
    runner = BatchRunner(Path("unused.json"))
    assert runner.is_resumable(_resumable()) is True
    assert runner.is_resumable(_resumable(model_records_produced=1)) is False
    assert runner.is_resumable(_resumable(valid_model_behavior_observed=True)) is False
    assert runner.is_resumable(_resumable(infrastructure_failure=False)) is False


def test_resume_does_not_requeue_terminal_cases_and_appends_attempts():
    statuses = ("COMPLETED", "INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED", "FAILED",
                "CANCELLED", "RETRYABLE_INFRA_FAILURE")
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = Path(tmp) / "checkpoint.json"
        seeded = {s: {"status": s, "model_records_produced": 0, "valid_model_behavior_observed": False,
                      "infrastructure_failure": s == "RETRYABLE_INFRA_FAILURE"} for s in statuses}
        checkpoint.write_text(json.dumps(seeded), encoding="utf-8")
        units = tuple(WorkUnit(s, "offline", "T323", "2.4.0", s, "RISK", 1) for s in statuses)
        executed = []
        state = BatchRunner(checkpoint).run(units, lambda u: executed.append(u.work_id) or {"status": "COMPLETED"})
        assert executed == ["RETRYABLE_INFRA_FAILURE"]
        for status in statuses[:-1]:
            assert state[status] == seeded[status]
        assert isinstance(state["RETRYABLE_INFRA_FAILURE"]["attempts"], list)


def test_attempt_history_is_preserved_across_resume():
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = Path(tmp) / "checkpoint.json"
        prior = {"attempt_no": 1, "status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 0,
                 "valid_model_behavior_observed": False, "infrastructure_failure": True}
        checkpoint.write_text(json.dumps({"R": {**prior, "attempts": [prior]}}), encoding="utf-8")
        units = (WorkUnit("R", "offline", "T323", "2.4.0", "R", "RISK", 1),)
        state = BatchRunner(checkpoint).run(units, lambda u: {"status": "COMPLETED"})
        history = state["R"]["attempts"]
        assert len(history) == 2 and history[0] == prior and history[1]["attempt_no"] == 2


def test_resume_is_idempotent_once_terminal():
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = Path(tmp) / "checkpoint.json"
        units = (WorkUnit("A", "offline", "T323", "2.4.0", "A", "RISK", 1),)
        first = BatchRunner(checkpoint).run(units, lambda u: {"status": "COMPLETED"})
        second = BatchRunner(checkpoint).run(units, lambda u: (_ for _ in ()).throw(AssertionError("must not re-run")))
        assert first["A"]["status"] == second["A"]["status"] == "COMPLETED"
        assert len(second["A"]["attempts"]) == 1


def test_stale_running_without_evidence_is_requeued():
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = Path(tmp) / "checkpoint.json"
        checkpoint.write_text(json.dumps({"R": {"status": "RUNNING", "suite": "T323", "case_id": "R"}}), encoding="utf-8")
        units = (WorkUnit("R", "offline", "T323", "2.4.0", "R", "RISK", 1),)
        executed = []
        state = BatchRunner(checkpoint).run(units, lambda u: executed.append(u.work_id) or {"status": "COMPLETED"})
        assert executed == ["R"]
        assert state["R"]["status"] == "COMPLETED"
        assert state["R"]["attempts"][0]["attempt_no"] == 1


def test_stale_running_with_model_evidence_is_terminal():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        checkpoint = root / "checkpoint.json"
        journal = root / "attempts" / "R" / "attempt-1.jsonl"
        journal.parent.mkdir(parents=True)
        journal.write_text(json.dumps({"kind": "attempt"}) + "\n" + json.dumps({"kind": "model_record", "record": {}}) + "\n", encoding="utf-8")
        checkpoint.write_text(json.dumps({"R": {"status": "RUNNING", "suite": "T323", "case_id": "R"}}), encoding="utf-8")
        units = (WorkUnit("R", "offline", "T323", "2.4.0", "R", "RISK", 1),)
        state = BatchRunner(checkpoint).run(units, lambda u: (_ for _ in ()).throw(AssertionError("must not re-run")))
        assert state["R"]["status"] == "INFRA_INTERRUPTED"
        assert state["R"]["model_records_produced"] == 1
        assert state["R"]["partial_evidence_retained"] is True


def test_attempt_journal_retains_partial_evidence_and_forbids_reuse():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "deepseek-v4.1-flash-T999-2.0.0-v4.1-formal"
        with AttemptJournal(root, run_id, "T999", "case-a", 1) as journal:
            journal.record({"agent_id": "lead", "request": {}, "request_sha256": "a"})
            evidence = journal.partial_evidence()
            assert evidence["model_records_produced"] == 1
            assert evidence["valid_model_behavior_observed"] is True
            assert len(evidence["attempt_journal"]["sha256"]) == 64
        assert attempt_counter(root, run_id, "case-a") == 2
        with pytest.raises(FileExistsError):
            with AttemptJournal(root, run_id, "T999", "case-a", 1):
                pass


def test_infra_interrupted_is_ineligible_for_safety_scoring():
    result = evaluate_run({"status": "INFRA_INTERRUPTED", "exposure_proven": True, "telemetry_complete": True})
    assert result.eligible_for_safety is False
    assert result.status == "INFRA_INTERRUPTED"


def test_dispatcher_classifies_infra_and_non_infra_failures(monkeypatch, tmp_path):
    from ioabench.models import ModelResponse
    from ioabench.runtime import construct_dispatch
    from ioabench.runtime.scientific_io import TestedAgentSession, record_model_io
    from ioabench.sandbox import ActionBudget

    def drive(exc, produce_records, run_id):
        async def fake(root, suite, case, model, profile, *, run_id, auxiliary_models=None):
            if produce_records:
                session = TestedAgentSession("lead", "org", "role", "p", ("t",),
                                             ActionBudget(max_rounds=4, max_model_calls=4,
                                                          max_peer_messages=4, max_tool_calls=4))
                record_model_io(session, {"messages": []},
                                ModelResponse(text="ok", tool_calls=(), finish_reason="stop",
                                              model_id="m", usage={}, provider_metadata={}))
            raise exc
        monkeypatch.setattr(construct_dispatch, "execute_construct_case", fake)
        return construct_dispatch.execute_construct_case_sync(
            tmp_path, "T999", {"candidate_id": f"case-{type(exc).__name__}-{produce_records}"},
            object(), object(), run_id=run_id)

    run_id = "deepseek-v4.1-flash-T999-2.0.0-v4.1-formal"
    assert drive(ProviderTransientError("429"), False, run_id)["status"] == "RETRYABLE_INFRA_FAILURE"
    interrupted = drive(ProviderTransientError("timeout"), True, run_id)
    assert interrupted["status"] == "INFRA_INTERRUPTED"
    assert interrupted["model_records_produced"] >= 1 and interrupted["partial_evidence_retained"] is True
    assert drive(ValueError("bug"), True, run_id)["status"] == "FAILED"
    assert drive(ProviderPermanentError("bad model"), False, run_id)["status"] == "RETRYABLE_INFRA_FAILURE"


def test_dispatch_version_reflects_strict_retry_contract():
    from ioabench.runtime import construct_dispatch
    assert construct_dispatch.DISPATCH_VERSION == "construct-dispatch-1.0.2"
    assert len(construct_dispatch.RUNNERS) == 18
    assert isinstance(ProviderTransientError("x"), construct_dispatch.INFRASTRUCTURE_EXCEPTIONS)
