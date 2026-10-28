import asyncio
import json
from pathlib import Path

import pytest

from ioabench.errors import ConfigurationError, ProviderPermanentError, ProviderTransientError
from ioabench.models import ModelProfile, ModelRequest, ModelResponse
from ioabench.v5.ai_generation.auxiliary_runtime import (
    AuxiliaryContract, AuxiliaryRouter, AuxiliaryUnavailable, RequestUnresolved,
    classify_provider_failure, redact, usage_cost, _retry_after,
)
from ioabench.v5.ai_generation.model_routing import resolve_display_candidate


CATALOG = [{"model_id": "first", "model_name": "First", "developer_id": 1},
           {"model_id": "backup", "developer_id": 2}]
REQUEST = ModelRequest([{"role": "user", "content": "Return JSON with value 42."}], {})


def parameter_schema(model_id="first"):
    return {"model_id": model_id, "protocols": ["openai.chat_completions"],
        "specs": {"max_output_tokens": 131072}, "domains": [{"capabilities": [
            {"key": "output-limit", "protocols": [{"protocol": "openai.chat_completions",
                "fields": [{"name": "max_tokens"}]}]}]}]}


def reply(model_id="first", text='{"value":42}', finish="stop"):
    return ModelResponse(text, model_id=model_id, finish_reason=finish,
                         usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                         provider_metadata={"model": model_id + "-dated", "transport_metadata": {"x-aihubmix-model": model_id}})


def contracts(*, gold=False):
    return [AuxiliaryContract(ModelProfile("aihubmix", row["model_id"], {}, {}),
                              {"max_tokens": 8192}, row, "preflight.json",
                              ("GENERATOR", "INDEPENDENT_AUDITOR", "CALIBRATOR", "AUX_PROTOCOL_PROBE"),
                              "gold.json" if gold else None) for row in CATALOG]


class Port:
    stop_on_provider_error = True

    def __init__(self, results):
        self.results, self.calls = list(results), []

    async def generate(self, profile, request):
        self.calls.append((profile, request))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def run(port, directory, *, role="GENERATOR", request_id="sample", **kwargs):
    router = AuxiliaryRouter(port, contracts(gold=kwargs.pop("gold", False)), CATALOG, directory,
                             sleep=lambda seconds: asyncio.sleep(0))
    return asyncio.run(router.invoke(role, request_id, REQUEST, **kwargs)), router


@pytest.mark.parametrize(("error", "category"), [
    (ConfigurationError("AIHUBMIX_API_KEY is required"), "MISSING_SECRET"),
    (ProviderPermanentError("HTTP 401"), "AUTH/PERMISSION"),
    (ProviderPermanentError("HTTP 403 insufficient_user_quota"), "AUTH/PERMISSION"),
    (ProviderPermanentError("HTTP 400 no_available_channel"), "PROVIDER_UNAVAILABLE"),
    (ProviderTransientError("HTTP 429"), "RATE_LIMIT"),
    (ProviderTransientError("HTTP 503"), "NETWORK_TRANSIENT"),
    (TimeoutError("timed out"), "NETWORK_TRANSIENT"),
    (ProviderPermanentError("HTTP 422 unsupported parameter: temperature"), "REQUEST_SCHEMA"),
    (ProviderPermanentError("RESPONSE_PARSE empty response"), "RESPONSE_PARSE"),
    (ProviderPermanentError("MODEL_ID_MISMATCH"), "MODEL_ID_MISMATCH"),
    (ValueError("MODEL_QUALITY contradiction"), "MODEL_QUALITY"),
    (ValueError("SCIENCE_GATE leakage"), "SCIENCE_GATE"),
])
def test_failure_classification(error, category):
    assert classify_provider_failure(error) == category


def test_no_channel_circuits_and_switches_exact_identity_without_retry(tmp_path):
    port = Port([ProviderPermanentError("HTTP 400 no_available_channel"), reply("backup")])
    response, router = run(port, tmp_path)
    assert response.model_id == "backup"
    assert [p.model_id for p, _ in port.calls] == ["first", "backup"]
    assert router.state["circuits"]["first"]["category"] == "PROVIDER_UNAVAILABLE"
    assert all(r.parameters == {"max_tokens": 8192} for _, r in port.calls)
    router.verify_ledger()


def test_staged_generator_families_are_all_excluded_from_judging(tmp_path):
    port = Port([])
    with pytest.raises(AuxiliaryUnavailable, match="NO_QUALIFIED_MODEL"):
        run(port, tmp_path, role="INDEPENDENT_AUDITOR", gold=True, generator_developer_id=[1, 2])
    assert not port.calls


@pytest.mark.parametrize("discounted", [False, True])
def test_qualification_loader_rechecks_bound_probe_and_rejects_unqualified_judge(tmp_path, discounted):
    from dataclasses import asdict
    import hashlib
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.evaluation import atomic_json
    from ioabench.v5.ai_generation.auxiliary_runtime import qualified_contracts
    probe = tmp_path / "probe"
    parameters = {"max_tokens": 8192 if discounted else 131072}
    binding = {"contracts": [{"profile": {"model_id": "first"}, "parameters": parameters}]}
    atomic_json(probe / "REQUEST_BINDING.json", {"binding": binding, "sha256": canonical_sha256(binding)})
    response = asdict(reply())
    atomic_json(probe / "RESPONSE.json", {"response": response, "response_sha256": canonical_sha256(response),
                                           "binding_sha256": canonical_sha256(binding)})
    atomic_json(tmp_path / "MODEL_CATALOG.json", CATALOG)
    atomic_json(tmp_path / "AIHUBMIX_PREFLIGHT.json", {"candidates": [{"requested_model_id": "first",
        "live_probe": "PASS", "response_evidence": str(probe / "RESPONSE.json"),
        "actual_parameters": parameters, "endpoint": "https://api.inferera.com/v1/chat/completions"}]})
    atomic_json(tmp_path / "schemas/first.json", parameter_schema())
    atomic_json(tmp_path / "SHA256SUMS.json", {"files": {path.relative_to(tmp_path).as_posix():
        hashlib.sha256(path.read_bytes()).hexdigest() for path in tmp_path.rglob("*.json")}})
    if discounted:
        with pytest.raises(ValueError, match="documented full configuration"):
            qualified_contracts(tmp_path, workspace=tmp_path, role="GENERATOR", model_ids=["first"])
        return
    _, loaded, endpoint = qualified_contracts(tmp_path, workspace=tmp_path, role="GENERATOR", model_ids=["first"])
    assert loaded[0].parameters["max_tokens"] == 131072 and endpoint.endswith("/v1")
    with pytest.raises(ValueError, match="fixed controls"):
        qualified_contracts(tmp_path, workspace=tmp_path, role="INDEPENDENT_AUDITOR", model_ids=["first"])
    atomic_json(probe / "RESPONSE.json", {"response": "forged"})
    with pytest.raises(ValueError, match="preflight evidence changed"):
        qualified_contracts(tmp_path, workspace=tmp_path, role="GENERATOR", model_ids=["first"])


@pytest.mark.parametrize("failure", [ProviderTransientError("HTTP 429 retry-after: 0"), ProviderTransientError("HTTP 503")])
def test_retry_is_bounded_then_switches_and_restores_state(tmp_path, failure):
    port = Port([failure, failure, reply("backup")])
    response, router = run(port, tmp_path)
    assert response.model_id == "backup"
    assert len(port.calls) == 3
    restored = AuxiliaryRouter(Port([]), contracts(), CATALOG, tmp_path)
    assert restored.state == router.state
    restored.restore("first", preflight_evidence="new-preflight.json", judge_gold_evidence="new-gold.json")
    assert "first" not in restored.state["circuits"]


def test_long_retry_after_defers_model_instead_of_long_blocking_wait(tmp_path):
    port = Port([ProviderTransientError('HTTP 429 {"retry-after":"900"}'), reply("backup")])
    run(port, tmp_path)
    assert len(port.calls) == 2


def test_http_date_retry_after_and_wrapper_failure_category():
    assert _retry_after(ProviderTransientError('HTTP 429 {"retry-after":"Thu, 01 Jan 1970 00:01:40 GMT"}'), 90) == 10
    assert classify_provider_failure(AuxiliaryUnavailable("all candidates blocked", category="PROVIDER_UNAVAILABLE")) == "PROVIDER_UNAVAILABLE"


def test_timeout_marks_unresolved_never_duplicates_and_next_task_uses_backup(tmp_path):
    port = Port([TimeoutError("connection timed out"), reply("backup")])
    with pytest.raises(RequestUnresolved):
        run(port, tmp_path)
    assert len(port.calls) == 1
    with pytest.raises(RequestUnresolved):
        run(port, tmp_path)
    assert len(port.calls) == 1
    response, _ = run(port, tmp_path, request_id="next-distinct-task")
    assert response.model_id == "backup"


@pytest.mark.parametrize("response", [reply(text=""), reply(finish="length"), reply("unrequested")])
def test_abnormal_response_and_identity_mismatch_retained_without_switch(tmp_path, response):
    port = Port([response, reply("backup")])
    with pytest.raises(ProviderPermanentError):
        run(port, tmp_path)
    assert len(port.calls) == 1
    attempt = json.loads((tmp_path / "sample" / "attempt-001.json").read_text())
    assert attempt["response"]["text"] == response.text
    assert attempt["category"] in {"RESPONSE_PARSE", "MODEL_ID_MISMATCH"}


def test_auth_stops_credential_and_all_candidates_immediately(tmp_path):
    port = Port([ProviderPermanentError("HTTP 401"), reply("backup")])
    with pytest.raises(ProviderPermanentError):
        run(port, tmp_path)
    assert len(port.calls) == 1
    with pytest.raises(AuxiliaryUnavailable, match="credential"):
        run(port, tmp_path, request_id="another")
    assert len(port.calls) == 1


def test_judge_needs_gold_and_different_generator_family(tmp_path):
    port = Port([reply("backup")])
    with pytest.raises(AuxiliaryUnavailable):
        run(port, tmp_path / "no-gold", role="INDEPENDENT_AUDITOR", generator_developer_id=1)
    assert not port.calls
    response, _ = run(port, tmp_path / "gold", role="INDEPENDENT_AUDITOR", generator_developer_id=1, gold=True)
    assert response.model_id == "backup"


def test_quality_failure_never_switches_judge_to_get_pass(tmp_path):
    port = Port([reply(), reply("backup")])
    def reject(_):
        raise ValueError("SCIENCE_GATE negative control failed")
    with pytest.raises(ValueError, match="SCIENCE_GATE"):
        run(port, tmp_path, validate=reject)
    assert len(port.calls) == 1


def test_tool_response_and_followup_replay_keep_reasoning_without_failover(tmp_path):
    from dataclasses import replace
    tools = ({"type": "function", "function": {"name": "read_fact", "parameters": {"type": "object"}}},)
    call = {"id": "fact-1", "type": "function", "function": {"name": "read_fact", "arguments": "{}"}}
    tool_reply = replace(reply(text=None, finish="tool_calls"), tool_calls=(call,), reasoning_content="Need the local fact.")
    port = Port([tool_reply, reply()])
    router = AuxiliaryRouter(port, contracts(), CATALOG, tmp_path)
    first_request = replace(REQUEST, tools=tools)
    first = asyncio.run(router.invoke("CALIBRATOR", "first-turn", first_request))
    assert first == tool_reply
    assert asyncio.run(router.invoke("CALIBRATOR", "first-turn", first_request)) == first
    messages = [*REQUEST.messages, {"role": "assistant", "content": None, "tool_calls": [call],
                                   "reasoning_content": first.reasoning_content},
                {"role": "tool", "tool_call_id": "fact-1", "content": '{"value":42}'}]
    followup = ModelRequest(messages, {}, tools=tools)
    assert asyncio.run(router.invoke("CALIBRATOR", "second-turn", followup)).text == '{"value":42}'
    assert len(port.calls) == 2 and not router.state["circuits"]
    assert port.calls[1][1].messages[1]["reasoning_content"] == "Need the local fact."


@pytest.mark.parametrize("tools,calls", [
    ((), ({"id": "fact-1", "function": {"name": "read_fact", "arguments": "{}"}},)),
    (({"type": "function", "function": {"name": "read_fact"}},), ()),
    (({"type": "function", "function": {"name": "read_fact"}},), ({"function": {}},)),
])
def test_malformed_tool_envelopes_stop_as_output_failures(tmp_path, tools, calls):
    from dataclasses import replace
    port = Port([replace(reply(text=None, finish="tool_calls"), tool_calls=calls), reply("backup")])
    router = AuxiliaryRouter(port, contracts(), CATALOG, tmp_path)
    with pytest.raises(ProviderPermanentError, match="RESPONSE_PARSE"):
        asyncio.run(router.invoke("CALIBRATOR", "tool-task", replace(REQUEST, tools=tools)))
    assert len(port.calls) == 1 and not router.state["circuits"]


def test_invalid_tool_action_is_not_reinterpreted_as_provider_failure(tmp_path):
    from dataclasses import replace
    tools = ({"type": "function", "function": {"name": "read_fact"}},)
    call = {"id": "fact-1", "type": "function", "function": {"name": "unpermitted", "arguments": "{}"}}
    port = Port([replace(reply(text=None, finish="tool_calls"), tool_calls=(call,)), reply("backup")])
    router = AuxiliaryRouter(port, contracts(), CATALOG, tmp_path)
    def reject_action(_):
        raise ValueError("MODEL_QUALITY: action outside the permitted tool set")
    with pytest.raises(ValueError, match="MODEL_QUALITY"):
        asyncio.run(router.invoke("CALIBRATOR", "tool-task", replace(REQUEST, tools=tools), validate=reject_action))
    assert len(port.calls) == 1 and not router.state["circuits"]


def test_completed_response_replays_and_tampering_rejected(tmp_path):
    port = Port([reply()])
    first, _ = run(port, tmp_path)
    second, _ = run(port, tmp_path)
    assert first == second and len(port.calls) == 1
    path = tmp_path / "sample" / "RESPONSE.json"
    value = json.loads(path.read_text())
    value["response"]["text"] = "changed"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="binding"):
        run(port, tmp_path)


def test_ledger_tampering_is_detected(tmp_path):
    _, router = run(Port([reply()]), tmp_path)
    path = tmp_path / "AIHUBMIX_ATTEMPTS.jsonl"
    path.write_text(path.read_text().replace('"event": "REQUEST_STARTED"', '"event": "CHANGED"'))
    with pytest.raises(ValueError, match="integrity"):
        router.verify_ledger()


def test_formal_role_and_model_policy_mutation_rejected(tmp_path):
    port = Port([reply()])
    with pytest.raises(ValueError, match="frozen SUT"):
        run(port, tmp_path, role="SUT")
    run(port, tmp_path)
    router = AuxiliaryRouter(port, contracts(), CATALOG, tmp_path)
    with pytest.raises(ValueError, match="immutable"):
        asyncio.run(router.invoke("CALIBRATOR", "sample", REQUEST))


def test_redaction_and_usage_estimate():
    private = {"Authorization": "Bearer hidden", "nested": {"api_key": "secret"},
               "error": "Bearer hidden sk-1234 https://test/?token=bad&x=1"}
    assert "hidden" not in json.dumps(redact(private)) and "sk-1234" not in json.dumps(redact(private))
    assert "token=bad" not in json.dumps(redact(private))
    estimate = usage_cost(reply(), {"pricing": {"input": 2, "output": 10}})
    assert estimate["status"] == "ESTIMATED" and estimate["amount"] == pytest.approx(0.00007)


def test_display_effort_requires_exact_model_schema_and_no_ambiguous_aliases():
    schema = {"specs": {"max_output_tokens": 131072}, "protocols": ["openai.chat_completions"], "domains": [{"capabilities": [
        {"key": "output-limit", "protocols": [{"protocol": "openai.chat_completions", "fields": [{"name": "max_tokens"}]}]},
        {"key": "reasoning-effort", "protocols": [{"protocol": "openai.chat_completions", "fields": [
            {"name": "reasoning_effort", "enum": ["low", "medium", "high"]}]}]}]}]}
    assert resolve_display_candidate("First (Medium)", CATALOG, {})["status"] == "UNVERIFIED_CONFIGURATION"
    result = resolve_display_candidate("First (Medium)", CATALOG, {"first": schema})
    assert result["entry"]["model_id"] == "first" and result["effort"] == "medium"
    assert resolve_display_candidate("First (Max)", CATALOG, {"first": schema})["status"] == "CAPABILITY_UNSUPPORTED"
    assert resolve_display_candidate("First Next", CATALOG, {})["status"] == "UNRESOLVED_MODEL_ID"
    assert resolve_display_candidate("First (Medium)", CATALOG, {"first": {"protocols": ["openai.responses"]}})["status"] == "CAPABILITY_UNSUPPORTED"


def test_preflight_script_runs_fake_live_corpus_and_terminal_resume_without_calls(tmp_path, monkeypatch):
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "scripts/v5/aihubmix_preflight.py"
    spec = importlib.util.spec_from_file_location("factory_provider_preflight", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("Local fixture API documentation.")
    monkeypatch.setenv("AIHUBMIX_API_KEY", "not-a-real-key")
    monkeypatch.setattr(module, "load_workspace_env", lambda _: None)
    monkeypatch.setattr(module, "USER_CANDIDATES", ("First (Medium)", "Unknown Next"))
    schema = {"model_id": "first", "specs": {"max_output_tokens": 131072}, "protocols": ["openai.chat_completions"], "domains": [{"capabilities": [
        {"key": "output-limit", "protocols": [{"protocol": "openai.chat_completions", "fields": [{"name": "max_tokens"}]}]},
        {"key": "reasoning-effort", "protocols": [{"protocol": "openai.chat_completions", "fields": [
            {"name": "reasoning_effort", "enum": ["low", "medium", "high"]}]}]}]}]}
    class FakePort(Port):
        async def discover_models(self):
            return CATALOG
        async def describe_model(self, model_id):
            return schema
    port = FakePort([reply(text='{"probe":"ioa-factory-20261019","value":42}')])
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **_: port)
    out = tmp_path / "out"
    result = asyncio.run(module.preflight(out, docs, live=True, timeout=1))
    assert result["passed"] == 1 and result["completion_attempts"] == 1
    assert result["candidates"][1]["status"] == "UNRESOLVED_MODEL_ID"
    assert result["usage"]["total_tokens"] == 15
    assert asyncio.run(module.preflight(out, docs, live=True, timeout=1)) == result
    assert len(port.calls) == 1


@pytest.mark.parametrize("live", [False, True])
def test_preflight_missing_secret_never_constructs_provider(tmp_path, monkeypatch, live):
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "scripts/v5/aihubmix_preflight.py"
    spec = importlib.util.spec_from_file_location("preflight_without_secret", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("Complete fixture documentation.")
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)
    monkeypatch.setattr(module, "load_workspace_env", lambda _: None)
    def forbidden_provider(**_):
        pytest.fail("missing/offline secret must not create a Provider")
    monkeypatch.setattr(module, "AIHubMixAdapter", forbidden_provider)
    result = asyncio.run(module.preflight(tmp_path / "out", docs, live=live, timeout=1))
    assert result["status"] == ("MISSING_SECRET" if live else "OFFLINE_DOC_INVENTORY_COMPLETE")
    assert result["provider_calls"] == 0
    assert all(row["status"] == "NOT_RUN" for row in result["candidates"])


def test_preflight_bad_credential_stops_remaining_candidates_and_redacts(tmp_path, monkeypatch):
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "scripts/v5/aihubmix_preflight.py"
    spec = importlib.util.spec_from_file_location("preflight_bad_secret", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("Fixture local documentation.")
    fake_secret = "sk-" + "intentionally-fake-test-value"
    monkeypatch.setenv("AIHUBMIX_API_KEY", fake_secret)
    monkeypatch.setattr(module, "load_workspace_env", lambda _: None)
    monkeypatch.setattr(module, "USER_CANDIDATES", ("first", "backup"))
    class FakePort(Port):
        async def discover_models(self):
            return CATALOG
        async def describe_model(self, model_id):
            return parameter_schema(model_id)
    port = FakePort([ProviderPermanentError("HTTP 401 Authorization: Bearer " + fake_secret)])
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **_: port)
    out = tmp_path / "out"
    result = asyncio.run(module.preflight(out, docs, live=True, timeout=1))
    assert result["status"] == "AUTH_BLOCKED" and len(port.calls) == 1
    assert result["candidates"][0]["category"] == "AUTH/PERMISSION"
    assert result["candidates"][1]["status"] == "NOT_RUN"
    assert all(fake_secret not in item.read_text(encoding="utf-8")
               for item in out.rglob("*") if item.is_file())
