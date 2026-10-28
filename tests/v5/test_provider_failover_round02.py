"""Mock only: ambiguous sends cannot become retries through incidental numbers."""
import asyncio
from dataclasses import replace
import json

import pytest

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.models import ModelProfile, ModelRequest, ModelResponse
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract, AuxiliaryRouter, RequestUnresolved


CATALOG = [{"model_id": "primary", "developer_id": 1}, {"model_id": "backup", "developer_id": 2}]
REQUEST = ModelRequest([{"role": "user", "content": "Return JSON."}], {})


def response(model="primary", **changes):
    return replace(ModelResponse(text='{"ok":true}', model_id=model, finish_reason="stop",
                                 provider_metadata={"model": model}), **changes)


class MockPort:
    stop_on_provider_error = True

    def __init__(self, results):
        self.results, self.calls = list(results), []

    async def generate(self, profile, request):
        self.calls.append((profile.model_id, request))
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def router(port, directory):
    contracts = [AuxiliaryContract(ModelProfile("aihubmix", row["model_id"], {}, {}), {"max_tokens": 1024},
                                  row, "MOCK_ONLY", ("AUX_PROTOCOL_PROBE",)) for row in CATALOG]
    return AuxiliaryRouter(port, contracts, CATALOG, directory, sleep=lambda _: asyncio.sleep(0))


@pytest.mark.parametrize("incidental", [500, 503, 512, 599])
def test_no_http_incidental_5xx_is_never_retried_even_after_restart(tmp_path, incidental):
    error = ProviderTransientError('AIHubMix curl response was empty; ' + json.dumps(
        {"curl_returncode": 28, "http_status": "000", "response_characters": incidental}))
    port = MockPort([error, response(), response("backup")])
    first = router(port, tmp_path)
    with pytest.raises(RequestUnresolved):
        asyncio.run(first.invoke("AUX_PROTOCOL_PROBE", "task", REQUEST))
    with pytest.raises(RequestUnresolved):
        asyncio.run(router(port, tmp_path).invoke("AUX_PROTOCOL_PROBE", "task", REQUEST))
    assert len(port.calls) == 1
    attempt = json.loads((tmp_path / "task/attempt-001.json").read_text())
    assert attempt["status"] == "REQUEST_UNRESOLVED"


@pytest.mark.parametrize("failure", ["json", "empty", "tool", "400"])
def test_bad_output_or_schema_stops_without_provider_fallback(tmp_path, failure):
    item = {"json": response(text="bad JSON"), "empty": response(text=""),
            "tool": response(text=None, finish_reason="tool_calls"),
            "400": ProviderPermanentError("HTTP 400 unsupported parameter")}[failure]
    port = MockPort([item, response("backup")])
    def validate(reply):
        json.loads(reply.text)
    with pytest.raises((ValueError, ProviderPermanentError)):
        asyncio.run(router(port, tmp_path).invoke("AUX_PROTOCOL_PROBE", "task", REQUEST, validate=validate))
    assert len(port.calls) == 1
    rows = [json.loads(line) for line in (tmp_path / "AIHUBMIX_ATTEMPTS.jsonl").read_text().splitlines()]
    assert not any(row["event"] == "MODEL_FAILOVER" for row in rows)


@pytest.mark.parametrize("code", [401, 403])
def test_auth_stops_shared_credential_across_restart(tmp_path, code):
    port = MockPort([ProviderPermanentError(f"HTTP {code}"), response("backup")])
    with pytest.raises(ProviderPermanentError):
        asyncio.run(router(port, tmp_path).invoke("AUX_PROTOCOL_PROBE", "task", REQUEST))
    with pytest.raises(ProviderPermanentError):
        asyncio.run(router(port, tmp_path).invoke("AUX_PROTOCOL_PROBE", "different-task", REQUEST))
    assert len(port.calls) == 1


@pytest.mark.parametrize("code", [429, 500])
def test_explicit_http_transient_has_bounded_retry_and_named_fallback(tmp_path, code):
    port = MockPort([ProviderTransientError(f"HTTP {code}"), ProviderTransientError(f"HTTP {code}"), response("backup")])
    result = asyncio.run(router(port, tmp_path).invoke("AUX_PROTOCOL_PROBE", "task", REQUEST))
    assert result.model_id == "backup"
    assert [model for model, _ in port.calls] == ["primary", "primary", "backup"]


def test_completed_tool_first_turn_interrupted_final_never_restarts_cycle(tmp_path):
    call = {"id": "read-1", "function": {"name": "read_fact", "arguments": "{}"}}
    port = MockPort([response(text=None, finish_reason="tool_calls", tool_calls=(call,)),
                     ProviderTransientError("network timed out"), response("backup")])
    first_request = replace(REQUEST, tools=({"type": "function", "function": {"name": "read_fact"}},))
    first = asyncio.run(router(port, tmp_path).invoke("AUX_PROTOCOL_PROBE", "tool-start", first_request))
    followup = ModelRequest([*REQUEST.messages, {"role": "assistant", "content": "", "tool_calls": [call]},
                            {"role": "tool", "content": '{"value":42}', "tool_call_id": "read-1"}], {})
    with pytest.raises(RequestUnresolved):
        asyncio.run(router(port, tmp_path).invoke("AUX_PROTOCOL_PROBE", "tool-final", followup))
    restored = router(port, tmp_path)
    assert asyncio.run(restored.invoke("AUX_PROTOCOL_PROBE", "tool-start", first_request)) == first
    with pytest.raises(RequestUnresolved):
        asyncio.run(restored.invoke("AUX_PROTOCOL_PROBE", "tool-final", followup))
    assert len(port.calls) == 2
    restored.verify_ledger()
