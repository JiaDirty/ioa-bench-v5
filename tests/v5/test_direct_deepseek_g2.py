from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ioabench.errors import ProviderPermanentError, ProviderRequestUnresolved
from ioabench.models import ModelResponse
from ioabench.v5.ai_generation.direct_deepseek import DirectStudy, cost_estimate, immutable, parameters


class Port:
    base_url = "https://api.deepseek.com"
    def __init__(self, failure=None, model="deepseek-flash"):
        self.calls, self.failure, self.model = 0, failure, model
    async def generate(self, profile, request):
        self.calls += 1
        if self.failure:
            raise self.failure
        return ModelResponse(text='{"ok":true}', usage={"prompt_tokens": 10, "completion_tokens": 4},
            model_id=self.model, finish_reason="stop", provider_metadata={"model": self.model})


def invoke(study, request="fresh"):
    return asyncio.run(study.invoke(study.out / "io", request,
        [{"role": "user", "content": 'json {"ok":true}'}], parameters()))


def test_direct_cached_response_reentry_has_zero_sends_and_separate_provider_ledger(tmp_path):
    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    assert invoke(study).text == invoke(study).text
    assert port.calls == 1
    assert (tmp_path / "io/DEEPSEEK_ATTEMPTS.jsonl").exists()
    assert not list(tmp_path.rglob("AIHUBMIX*"))
    rows = [json.loads(line) for line in (tmp_path / "REQUEST_LEDGER.jsonl").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["REQUEST_INTENT", "REQUEST_FINISHED"]


def test_completed_receipt_recovers_missing_cost_once_and_blocks_next_send_at_budget(tmp_path, monkeypatch):
    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    original_ledger = study.ledger
    class CrashBetweenReceiptAndLedger(BaseException):
        pass
    def crash(event, **details):
        if event == "REQUEST_FINISHED":
            raise CrashBetweenReceiptAndLedger()
        return original_ledger(event, **details)
    monkeypatch.setattr(study, "ledger", crash)
    with pytest.raises(CrashBetweenReceiptAndLedger):
        invoke(study)
    assert port.calls == 1 and (tmp_path / "io/fresh/RESPONSE.json").exists()
    monkeypatch.setattr(study, "ledger", original_ledger)
    assert invoke(study).text == '{"ok":true}' and port.calls == 1
    rows = study.ledger_rows()
    finished = [row for row in rows if row["event"] == "REQUEST_FINISHED"]
    assert len(finished) == 1 and finished[0]["usage"] == {"prompt_tokens": 10, "completion_tokens": 4}
    assert finished[0]["accounting_source"] == "RECOVERED_DURABLE_RESPONSE"
    assert finished[0]["cost"]["upper_cny"] == pytest.approx(.000052)
    invoke(study)
    assert len(study.ledger_rows()) == len(rows)
    # The reserve alone is below 200; recovered real usage crosses the boundary.
    study.ledger("REQUEST_FINISHED", directory="prior", request_id="prior", status="PASS",
                 cost={"upper_cny": 197.87004})
    with pytest.raises(ValueError, match="hard budget stop"):
        invoke(study, "fresh-next")
    assert port.calls == 1


@pytest.mark.parametrize("usage,expected", [({"prompt_tokens": 10, "completion_tokens": 4096}, "CACHE_UNKNOWN_BOUND"),
                                           ({}, "UNKNOWN")])
def test_truncated_complete_response_cost_is_accounted_without_resend(tmp_path, usage, expected):
    class TruncatedPort(Port):
        async def generate(self, profile, request):
            self.calls += 1
            return ModelResponse(text="", model_id="deepseek-flash", finish_reason="length", usage=usage,
                                 provider_metadata={"model": "deepseek-flash"})
    port = TruncatedPort()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    with pytest.raises(ProviderPermanentError, match="RESPONSE_PARSE"):
        invoke(study)
    finished = [row for row in study.ledger_rows() if row["event"] == "REQUEST_FINISHED"]
    assert len(finished) == 1 and finished[0]["status"] == "FAILED_WITH_RESPONSE"
    assert finished[0]["usage"] == usage and finished[0]["cost"]["status"] == expected
    assert finished[0]["finish_reason"] == "length" and finished[0]["accounting_source"] == "DURABLE_FAILED_RESPONSE"
    if not usage:
        assert finished[0]["cost"]["amount"] is None and finished[0]["budget_reserve_cny"] > 0
    with pytest.raises(ProviderRequestUnresolved):
        invoke(study)
    assert port.calls == 1 and len([row for row in study.ledger_rows() if row["event"] == "REQUEST_FINISHED"]) == 1


@pytest.mark.parametrize("failure,category", [
    (ProviderRequestUnresolved("partial HTTP 200"), "REQUEST_UNRESOLVED"),
    (ProviderPermanentError("HTTP 401"), "AUTH/PERMISSION"),
    (ProviderPermanentError("HTTP 402"), "INSUFFICIENT_BALANCE"),
    (ProviderPermanentError("HTTP 403"), "AUTH/PERMISSION"),
])
def test_global_stop_prevents_even_a_new_task_after_unknown_auth_or_balance(tmp_path, failure, category):
    port = Port(failure)
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    with pytest.raises(Exception): invoke(study)
    assert json.loads((tmp_path / "STOP.json").read_text())["category"] == category
    with pytest.raises(ValueError, match="stopped"): invoke(study, "new-task")
    assert port.calls == 1


def test_wrong_served_model_is_rejected_and_not_resent(tmp_path):
    port = Port(model="other")
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}, {"id": "other"}])
    with pytest.raises(ProviderPermanentError, match="MODEL_ID_MISMATCH"): invoke(study)
    with pytest.raises(ProviderRequestUnresolved): invoke(study)
    assert port.calls == 1


def test_cost_missing_cache_is_a_bound_and_invalid_cache_is_rejected():
    unknown = cost_estimate({"prompt_tokens": 100, "completion_tokens": 10})
    cached = cost_estimate({"prompt_tokens": 100, "completion_tokens": 10, "prompt_cache_hit_tokens": 100})
    assert unknown["status"] == "CACHE_UNKNOWN_BOUND" and unknown["amount"] is None
    assert unknown["upper_cny"] > cached["upper_cny"]
    with pytest.raises(ValueError):
        cost_estimate({"prompt_tokens": 100, "completion_tokens": 10, "prompt_cache_hit_tokens": 101})
    assert cost_estimate({})["status"] == "UNKNOWN"


def test_immutable_evidence_and_only_distinct_documented_efforts(tmp_path):
    path = tmp_path / "retained.json"
    immutable(path, {"old": True})
    with pytest.raises(ValueError, match="immutable"): immutable(path, {"old": False})
    for effort in ("medium", "xhigh", "none"):
        with pytest.raises(ValueError): parameters(effort)
    assert "reasoning_effort" not in parameters("disabled")


def test_sealed_result_restores_interrupted_terminal_without_provider_calls(tmp_path, monkeypatch):
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.ai_generation import direct_deepseek as module
    from ioabench.v5.evaluation import atomic_json

    task = {"id": "interrupted", "suite": "T331", "seed": 1, "effort": "high", "difficulty": "M", "target": {}}
    directory = tmp_path / "candidates/interrupted"
    directory.mkdir(parents=True)
    manifest = {"version": module.VERSION, "scope": module.SCOPE, "task": task,
                "provider": "deepseek", "model": "deepseek-flash", "source_sha256": "pinned-runtime",
                "history_sha256": canonical_sha256({}), "formal_generator_allowed": False,
                "formal_auditor_qualified": False, "formal_accepted": False,
                "machine_qualified": False, "G3_parent_eligible": False}
    atomic_json(directory / "MANIFEST.json", manifest)
    row = {"scope": module.SCOPE, "task": task, "status": "FAIL", "formal_accepted": False,
           "machine_qualified": False, "finished_utc": "pinned-finish-time", "evidence_sha256": {
               "MANIFEST.json": module._sha(directory / "MANIFEST.json")}}
    terminal = {"terminal_binding_version": 2, "result_sha256": canonical_sha256(row), "result": row}
    atomic_json(directory / "TERMINAL.json", terminal)
    before = (directory / "TERMINAL.json").read_bytes()
    monkeypatch.setattr(module, "source_tree_hash", lambda workspace: "pinned-runtime")
    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    restored = asyncio.run(module.generate_candidate(study, task, {}, [], workspace=tmp_path))
    assert restored == row and module.candidate_result(directory) == row
    assert (directory / "TERMINAL.json").read_bytes() == before and port.calls == 0
    atomic_json(directory / "TERMINAL.json", {"result_sha256": canonical_sha256(row)})
    assert module.candidate_result(directory) == row  # Retained hash-only results remain readable.
    (directory / "RESULT.json").unlink()
    with pytest.raises(ValueError, match="legacy hash-only"):
        module.candidate_result(directory)
    assert port.calls == 0


def test_missing_result_recovery_validates_sealed_evidence_before_writing(tmp_path):
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.ai_generation import direct_deepseek as module
    from ioabench.v5.evaluation import atomic_json
    row = {"scope": module.SCOPE, "status": "PASS", "formal_accepted": False, "machine_qualified": False,
           "evidence_sha256": {"missing.json": "0" * 64}}
    atomic_json(tmp_path / "TERMINAL.json", {"result_sha256": canonical_sha256(row), "result": row})
    with pytest.raises(FileNotFoundError):
        module.candidate_result(tmp_path)
    assert not (tmp_path / "RESULT.json").exists()


def test_strict_replay_creates_real_pinned_reference_manifests(tmp_path):
    from ioabench.v5.ai_generation.acquisition import program_proposal
    from ioabench.v5.ai_generation.direct_deepseek import strict_checks
    from ioabench.v5.ai_generation.pipeline import compile_and_gate, run_reference_policies, suite_spec
    from ioabench.models import ModelProfile
    from ioabench.v5.evaluation import atomic_json
    spec = suite_spec("T331", typed=True)
    blueprint = program_proposal(spec, seed=193, difficulty="M")
    compiled = compile_and_gate(spec, blueprint, seed=193)
    rows = run_reference_policies(spec, tmp_path / "replay", {arm.upper(): compiled[arm]
        for arm in ("control", "risk")}, run_id="trial-193",
        profile=ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY"))
    atomic_json(tmp_path / "REFERENCE_RESULTS.json", rows)
    assert strict_checks(tmp_path, spec, compiled) == len(spec.policies) * 2
    assert len(list((tmp_path / "strict/artifacts/v5/evaluations").glob("*/manifest.json"))) == len(spec.policies)
    assert json.loads((tmp_path / "NEGATIVE_CONTROL.json").read_text())["status"] == "PASS"


def test_thinking_tool_keeps_empty_reasoning_and_retains_strict_output_failure(tmp_path):
    from ioabench.v5.ai_generation.direct_deepseek import probe
    class ToolPort(Port):
        async def generate(self, profile, request):
            self.calls += 1
            if self.calls in {1, 2}:
                text, tools, reason = json.dumps({"receipt": tmp_path.name, "value": 7}), (), "r"
            elif self.calls == 3:
                text, tools, reason = "", ({"id": "call-1", "type": "function", "function": {
                    "name": "echo_receipt", "arguments": '{"value":7}'}},), ""
            elif self.calls == 4:
                assert request.messages[-2]["reasoning_content"] == ""
                text, tools, reason = 'Receipt: {"value":7,"verified":true}', (), "r"
            else:
                assert self.calls == 5 and request.parameters["response_format"] == {"type": "json_object"}
                text, tools, reason = '{"value":7,"verified":true}', (), ""
            return ModelResponse(text=text, tool_calls=tools, reasoning_content=reason, model_id="deepseek-flash",
                usage={"prompt_tokens": 10, "completion_tokens": 4},
                provider_metadata={"model": "deepseek-flash"}, finish_reason="tool_calls" if tools else "stop")
    port = ToolPort()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    first = asyncio.run(probe(study))
    assert [row["status"] for row in first] == ["PASS", "PASS", "FAIL", "PASS"]
    assert asyncio.run(probe(study)) == first and port.calls == 5


def test_complete_response_without_usage_keeps_unknown_cost_and_reserves_budget(tmp_path):
    class NoUsagePort(Port):
        async def generate(self, profile, request):
            self.calls += 1
            return ModelResponse(text='{}', usage={}, model_id='deepseek-flash', finish_reason='stop',
                                 provider_metadata={'model': 'deepseek-flash'})
    port = NoUsagePort()
    study = DirectStudy(tmp_path, port, [{'id': 'deepseek-flash'}])
    study.ledger('REQUEST_FINISHED', directory='prior', request_id='prior', cost={'upper_cny': 195.5})
    asyncio.run(study.invoke(tmp_path / 'io', 'missing-usage', [], parameters(max_tokens=65536)))
    finished = [row for row in study.ledger_rows() if row['event'] == 'REQUEST_FINISHED'][-1]
    assert finished['cost']['status'] == 'UNKNOWN' and finished['cost']['amount'] is None
    assert finished['budget_reserve_cny'] == pytest.approx(2.62144)
    with pytest.raises(ValueError, match='hard budget stop'):
        asyncio.run(study.invoke(tmp_path / 'io', 'must-not-send', [], parameters(max_tokens=65536)))
    assert port.calls == 1


def test_legacy_finished_unknown_cost_is_reserved_from_its_intent_without_rewriting_history(tmp_path):
    study = DirectStudy(tmp_path, Port(), [{'id': 'deepseek-flash'}])
    study.ledger('REQUEST_FINISHED', directory='prior', request_id='prior', cost={'upper_cny': 195.5})
    study.ledger('REQUEST_INTENT', directory='io', request_id='legacy', parameters=parameters(max_tokens=65536))
    study.ledger('REQUEST_FINISHED', directory='io', request_id='legacy', cost={'status': 'UNKNOWN', 'amount': None})
    before = (tmp_path / 'REQUEST_LEDGER.jsonl').read_bytes()
    with pytest.raises(ValueError, match='hard budget stop'):
        study.check_budget(parameters(max_tokens=65536))
    assert (tmp_path / 'REQUEST_LEDGER.jsonl').read_bytes() == before


@pytest.mark.parametrize('field,value', [('prompt_tokens', -1), ('completion_tokens', -1),
    ('prompt_cache_hit_tokens', -1), ('prompt_cache_miss_tokens', -1), ('completion_tokens', 1.5), ('prompt_tokens', True)])
def test_invalid_usage_cannot_create_negative_or_fractional_accounting(field, value):
    usage = {'prompt_tokens': 10, 'completion_tokens': 4, field: value}
    with pytest.raises(ValueError, match='nonnegative integers'):
        cost_estimate(usage)


def test_unclassified_provider_failure_stops_all_subsequent_paid_tasks(tmp_path):
    port = Port(RuntimeError('unclassified provider fault'))
    study = DirectStudy(tmp_path, port, [{'id': 'deepseek-flash'}])
    with pytest.raises(RuntimeError):
        invoke(study)
    assert json.loads(study.stop.read_text())['category'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='stopped'):
        invoke(study, 'new-paid-task')
    assert port.calls == 1


def test_intent_only_interruption_recovers_one_submission_and_report_denominator(tmp_path, monkeypatch):
    from ioabench.v5.ai_generation import direct_deepseek as module
    import importlib.util
    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    class InterruptedBeforeAttempt(BaseException):
        pass
    async def interrupt(*args, **kwargs):
        raise InterruptedBeforeAttempt()
    with monkeypatch.context() as interrupted:
        interrupted.setattr(module.AuxiliaryRouter, "invoke", interrupt)
        with pytest.raises(InterruptedBeforeAttempt):
            invoke(study)
    assert port.calls == 0 and not list((tmp_path / "io/fresh").glob("attempt-*.json"))
    assert [row["event"] for row in study.ledger_rows()] == ["REQUEST_INTENT"]
    assert invoke(study).text == '{"ok":true}' and port.calls == 1
    assert [row["event"] for row in study.ledger_rows()] == ["REQUEST_INTENT", "REQUEST_FINISHED"]
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("intent_recovery_report", scripts / "report_development_factory.py")
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    requests, events = report.ledger(tmp_path / "REQUEST_LEDGER.jsonl")
    assert len(requests) == 1 and len(events) == 2 and requests[0]["finished"]["status"] == "PASS"


@pytest.mark.parametrize("changed", ["parameters", "messages", "tools"])
def test_retained_intent_mismatch_refuses_send_and_keeps_ledger_bytes(tmp_path, changed):
    from ioabench.hashing import canonical_sha256
    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    messages, options, tools = [{"role": "user", "content": "json original"}], parameters(), ()
    study.ledger("REQUEST_INTENT", directory="io", request_id="fresh", parameters=options,
        messages_sha256=canonical_sha256(messages), tools_sha256=canonical_sha256(tools))
    before = (tmp_path / "REQUEST_LEDGER.jsonl").read_bytes()
    if changed == "parameters":
        options = parameters(max_tokens=8192)
    elif changed == "messages":
        messages = [{"role": "user", "content": "json changed"}]
    else:
        tools = ({"type": "function", "function": {"name": "changed", "parameters": {"type": "object"}}},)
    with pytest.raises(ValueError, match="immutable request intent"):
        asyncio.run(study.invoke(tmp_path / "io", "fresh", messages, options, tools=tools))
    assert port.calls == 0 and (tmp_path / "REQUEST_LEDGER.jsonl").read_bytes() == before
    assert not list(tmp_path.rglob("attempt-*.json")) and not list(tmp_path.rglob("RESPONSE.json"))


def test_nonunique_retained_intent_is_not_rewritten_or_sent(tmp_path):
    from ioabench.hashing import canonical_sha256
    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    for _ in range(2):
        study.ledger("REQUEST_INTENT", directory="io", request_id="fresh", parameters=parameters(),
            messages_sha256=canonical_sha256([]), tools_sha256=canonical_sha256(()))
    before = (tmp_path / "REQUEST_LEDGER.jsonl").read_bytes()
    with pytest.raises(ValueError, match="not unique"):
        asyncio.run(study.invoke(tmp_path / "io", "fresh", [], parameters()))
    assert port.calls == 0 and (tmp_path / "REQUEST_LEDGER.jsonl").read_bytes() == before


def test_retained_started_attempt_is_still_unknown_and_never_resent(tmp_path):
    from ioabench.hashing import canonical_sha256
    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    study.ledger("REQUEST_INTENT", directory="io", request_id="fresh", parameters=parameters(),
        messages_sha256=canonical_sha256([]), tools_sha256=canonical_sha256(()))
    request = tmp_path / "io/fresh"
    request.mkdir(parents=True)
    attempt = request / "attempt-001.json"
    attempt.write_text('{"status":"REQUEST_STARTED"}', encoding="utf-8")
    before = attempt.read_bytes()
    with pytest.raises(ProviderRequestUnresolved):
        asyncio.run(study.invoke(tmp_path / "io", "fresh", [], parameters()))
    assert port.calls == 0 and attempt.read_bytes() == before
    assert len([row for row in study.ledger_rows() if row["event"] == "REQUEST_INTENT"]) == 1
    assert json.loads(study.stop.read_text())["category"] == "REQUEST_UNRESOLVED"
