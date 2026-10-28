from dataclasses import asdict
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import asyncio

import pytest

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.models import ModelProfile, ModelResponse
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract

SPEC = spec_from_file_location("probe_next_model_controls", Path(__file__).resolve().parents[2] / "scripts/v5/probe_next_model_controls.py")
control = module_from_spec(SPEC)
SPEC.loader.exec_module(control)


def contract(model="m1"):
    return AuxiliaryContract(ModelProfile("aihubmix", model, {}, {}, "AUX_PROTOCOL_PROBE"), {"max_tokens": 16},
        {"model_id": model, "developer_id": model, "pricing": {"input": 1, "output": 2}}, "verified-local-fixture", ("AUX_PROTOCOL_PROBE",))


def job(kind="TRUNCATION_NEGATIVE", ident="j1", models=("m1",)):
    return {"id": ident, "kind": kind, "contracts": [asdict(contract(model)) for model in models], "prompt": "JSON control"}


def response(model="m1", finish="stop"):
    return ModelResponse('{"probe":"next-controls","value":42}', provider_metadata={"model": model},
                         model_id=model, finish_reason=finish, usage={"prompt_tokens": 5, "completion_tokens": 16, "total_tokens": 21})


class FakePort:
    stop_on_provider_error = True

    def __init__(self, items):
        self.items, self.calls = list(items), 0

    async def generate(self, profile, request):
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def execute(tmp_path, task, items):
    port = control.SharedCredentialPort(FakePort(items))
    catalog = [contract(model).entry for model in ("m1", "m2")]
    result = asyncio.run(control.run_control(tmp_path, task, "frozen-plan", port, catalog, asyncio.Semaphore(1)))
    return result, port


def test_protocol_preference_requires_actual_json_pass():
    item = {"requested_model_id": "gpt-6.1-sol", "protocols": [
        {"protocol": "openai.chat_completions", "json": "PASS"}, {"protocol": "openai.responses", "json": "PASS"}]}
    assert control.protocol_for(item) == "openai.responses"
    item["protocols"][1]["json"] = "FAIL"
    assert control.protocol_for(item) == "openai.chat_completions"
    item["protocols"][0]["json"] = "FAIL"
    with pytest.raises(ValueError, match="previously verified"):
        control.protocol_for(item)


def test_real_length_evidence_is_required_not_merely_an_error(tmp_path):
    result, port = execute(tmp_path, job(), [response(finish="length")])
    assert result["status"] == "PASS" and result["observed_finishes"] == ["length"]
    assert result["unresolved"] == 0 and port.adapter_calls == 1
    assert control.observed_result(job(), [{"category": "REQUEST_SCHEMA", "error": "HTTP400"}])["status"] == "FAIL"


def test_disabled_acceptance_does_not_pass_rejection_control(tmp_path):
    result, port = execute(tmp_path, job("THINKING_DISABLED_REJECTION"), [response()])
    assert result["status"] == "FAIL" and port.adapter_calls == 1


def test_legacy400_failover_control_stops_under_round02_schema_policy(tmp_path):
    result, port = execute(tmp_path, job("PARAMETER400_FAILOVER", models=("m1", "m2")), [
        ProviderPermanentError("AIHubMix HTTP 400 incompatible integer"), response("m2")])
    assert result["status"] == "FAIL" and result["attempts"] == 1 and port.adapter_calls == 1
    assert result["actual_models"] == [None]


def test_unknown_disconnect_is_retained_never_resent_or_failed_over(tmp_path):
    result, port = execute(tmp_path, job("PARAMETER400_FAILOVER", models=("m1", "m2")), [
        ProviderTransientError("connection lost after send"), response("m2")])
    assert result["status"] == "FAIL" and result["unresolved"] == 1 and port.adapter_calls == 1


def test_401_stops_queued_shared_credential_controls(tmp_path):
    async def check():
        port = control.SharedCredentialPort(FakePort([ProviderPermanentError("AIHubMix HTTP 401 invalid credential"), response()]))
        semaphore = asyncio.Semaphore(1)
        tasks = [job("DOCUMENTED_MAXIMUM_ACCEPTANCE", ident=ident) for ident in ("a", "b")]
        results = await asyncio.gather(*(control.run_control(tmp_path, task, "plan", port, [contract().entry], semaphore) for task in tasks))
        assert [row["status"] for row in results] == ["FAIL", "NOT_RUN"]
        assert port.adapter_calls == 1 and port.auth_stopped
    asyncio.run(check())


def test_resume_checks_evidence_before_provider_use(tmp_path):
    task = job("DOCUMENTED_MAXIMUM_ACCEPTANCE")
    result, port = execute(tmp_path, task, [response()])
    assert result["status"] == "PASS"
    reread = asyncio.run(control.run_control(tmp_path, task, "frozen-plan", None, [], asyncio.Semaphore(1)))
    assert reread == result
    evidence = tmp_path / task["id"] / next(iter(result["evidence_sha256"]))
    evidence.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence changed"):
        asyncio.run(control.run_control(tmp_path, task, "frozen-plan", None, [], asyncio.Semaphore(1)))


def retained_fixture(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("version = 1\n", encoding="utf-8")
    task = job("DOCUMENTED_MAXIMUM_ACCEPTANCE")
    plan = {"jobs": [task], "sources_sha256": {str(source): control.sha(source)}}
    control.atomic_json(tmp_path / "PREREGISTRATION.json", plan)
    port = control.SharedCredentialPort(FakePort([response()]))
    row = asyncio.run(control.run_control(tmp_path, task, control.canonical_sha256(plan), port, [contract().entry], asyncio.Semaphore(1)))
    control.usage_report(tmp_path)
    control.atomic_json(tmp_path / "REPORT.json", {"preregistration_sha256": control.canonical_sha256(plan),
        "rows": [row], "counts": {"PASS": 1}, "status": "PASS"})
    return source


def test_readonly_verification_preserves_source_drift_and_never_creates_provider(tmp_path, monkeypatch):
    source = retained_fixture(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("retained verification must not create a provider")
    monkeypatch.setattr(control, "AIHubMixAdapter", forbidden)
    source.write_text("version = 2\n", encoding="utf-8")
    result = control.verify_retained(tmp_path)
    assert result["verification_status"] == "PASS" and result["source_binding_status"] == "PARTIAL"
    assert result["source_binding_reason"] == "SOURCE_DRIFT"
    assert result["verified_requests"] == 1 and result["provider_calls_this_verification"] == 0
    assert result["provider_created"] is False and result["original_results_rejudged"] is False
    assert str(source) in result["source_drift"]


def test_readonly_verification_rejects_corrupted_aggregate(tmp_path):
    retained_fixture(tmp_path)
    path = tmp_path / "REPORT.json"
    result = control.read(path)
    result["counts"] = {"PASS": 2}
    control.atomic_json(path, result)
    with pytest.raises(ValueError, match="aggregate/control mismatch"):
        control.verify_retained(tmp_path)
