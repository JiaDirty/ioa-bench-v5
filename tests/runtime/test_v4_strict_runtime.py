from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

from ioabench.runtime.batch import BatchRunner
from ioabench.runtime.scheduler import WorkUnit
from ioabench.runtime.scientific_io import AttemptJournal


ROOT = Path(__file__).resolve().parents[2]


def _campaign_module():
    path = ROOT / "scripts" / "run_online_campaign.py"
    spec = importlib.util.spec_from_file_location("v4_campaign_runtime_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_attempt_journal_is_isolated_between_async_cases(tmp_path):
    async def exercise() -> None:
        a_entered = asyncio.Event()
        b_entered = asyncio.Event()
        a_exited = asyncio.Event()

        async def case_a() -> None:
            with AttemptJournal(tmp_path, "run", "T311", "A", 1):
                a_entered.set()
                await b_entered.wait()
                AttemptJournal.current().record({"owner": "A"})
            a_exited.set()

        async def case_b() -> None:
            await a_entered.wait()
            with AttemptJournal(tmp_path, "run", "T311", "B", 1):
                b_entered.set()
                await a_exited.wait()
                AttemptJournal.current().record({"owner": "B"})

        await asyncio.gather(case_a(), case_b())

    asyncio.run(exercise())

    def owners(case_id: str) -> list[str]:
        path = tmp_path / "data" / "runs" / "run" / "attempts" / case_id / "attempt-1.jsonl"
        return [json.loads(line)["record"]["owner"]
                for line in path.read_text(encoding="utf-8").splitlines()[1:]]

    assert owners("A") == ["A"]
    assert owners("B") == ["B"]
    assert AttemptJournal.current() is None


def test_batch_attempt_preserves_dispatcher_provenance(tmp_path):
    units = (
        WorkUnit("retry", "model", "T311", "2.0.0", "retry", "RISK", 1),
        WorkUnit("interrupted", "model", "T311", "2.0.0", "interrupted", "RISK", 1),
    )

    def execute(unit: WorkUnit) -> dict:
        records = 0 if unit.case_id == "retry" else 1
        return {
            "status": "RETRYABLE_INFRA_FAILURE" if records == 0 else "INFRA_INTERRUPTED",
            "infrastructure_failure": True,
            "model_records_produced": records,
            "valid_model_behavior_observed": records > 0,
            "attempt_journal": {"path": f"{unit.case_id}.jsonl", "sha256": "0" * 64},
        }

    runner = BatchRunner(tmp_path / "checkpoint.json", concurrency=2)
    state = runner.run(units, execute, resume=False)

    assert state["retry"]["attempts"][-1]["infrastructure_failure"] is True
    assert state["retry"]["attempts"][-1]["model_records_produced"] == 0
    assert runner.is_resumable(state["retry"]) is True
    assert state["interrupted"]["attempts"][-1]["infrastructure_failure"] is True
    assert state["interrupted"]["attempts"][-1]["model_records_produced"] == 1
    assert runner.is_resumable(state["interrupted"]) is False


def test_batch_exception_outside_dispatcher_is_terminal(tmp_path):
    unit = WorkUnit("bug", "model", "T311", "2.0.0", "bug", "RISK", 1)
    state = BatchRunner(tmp_path / "checkpoint.json").run(
        (unit,), lambda _: (_ for _ in ()).throw(ValueError("bug")), resume=False)
    assert state["bug"]["status"] == "FAILED"
    assert state["bug"]["attempts"][-1]["status"] == "FAILED"
    assert BatchRunner(tmp_path / "checkpoint.json").is_resumable(state["bug"]) is False


def test_dispatcher_success_propagates_journal_record_count(tmp_path, monkeypatch):
    from ioabench.models import ModelResponse
    from ioabench.runtime import construct_dispatch
    from ioabench.runtime.scientific_io import TestedAgentSession, record_model_io
    from ioabench.sandbox import ActionBudget

    async def fake(root, suite, case, model, profile, *, run_id, auxiliary_models=None):
        session = TestedAgentSession("lead", "org", "role", "p", ("t",),
                                     ActionBudget(max_rounds=4, max_model_calls=4,
                                                  max_peer_messages=4, max_tool_calls=4))
        record_model_io(session, {"messages": []}, ModelResponse(
            text="ok", tool_calls=(), finish_reason="stop", model_id="m",
            usage={}, provider_metadata={}))
        record_model_io(session, {"messages": [{"role": "user"}]}, ModelResponse(
            text="ok", tool_calls=(), finish_reason="stop", model_id="m",
            usage={}, provider_metadata={}))
        return {"status": "COMPLETED", "replay": {"model_records": []}}

    monkeypatch.setattr(construct_dispatch, "execute_construct_case", fake)
    result = construct_dispatch.execute_construct_case_sync(
        tmp_path, "T999", {"candidate_id": "count"}, object(), object(), run_id="run")
    assert result["status"] == "COMPLETED"
    assert result["model_records_produced"] == 2
    assert result["valid_model_behavior_observed"] is True


def test_campaign_requires_exact_90_case_coverage(tmp_path, monkeypatch):
    campaign = _campaign_module()
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    suite, version = "T311", "2.0.0"
    cases = [{"candidate_id": f"case-{index}"} for index in range(90)]
    dataset = tmp_path / "data" / "datasets" / suite / version
    dataset.mkdir(parents=True)
    (dataset / "cases.jsonl").write_text(
        "".join(json.dumps(case) + "\n" for case in cases), encoding="utf-8")
    run_id = f"{campaign.MODEL}-{suite}-{version}-v4.1-formal"
    run_dir = tmp_path / "data" / "runs" / run_id
    run_dir.mkdir(parents=True)

    results = {f"work-{index}": {"case_id": f"case-{index}", "status": "COMPLETED"}
               for index in range(89)}
    (run_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")
    assert campaign.formal_complete(suite, version) is False

    results["work-89"] = {"case_id": "case-89", "status": "INVALID_MODEL_OUTPUT"}
    (run_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")
    assert campaign.formal_complete(suite, version) is True


def test_campaign_child_process_pins_workspace_source(tmp_path, monkeypatch):
    campaign = _campaign_module()
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(campaign.subprocess, "run", fake_run)
    monkeypatch.setenv("PYTHONPATH", "existing")
    assert campaign.run_step(["python", "-c", "pass"]) == (0, "ok")
    expected = str(tmp_path / "src") + os.pathsep + "existing"
    assert captured["env"]["PYTHONPATH"] == expected
    assert captured["cwd"] == tmp_path
