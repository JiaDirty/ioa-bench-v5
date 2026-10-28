"""S1 stays a one-request gate; all providers in these tests are local Mock."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.models import ModelResponse


ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/v5" / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("code,returncode,expected", [
    (401, 0, "AUTH_OR_PERMISSION"), (403, 0, "AUTH_OR_PERMISSION"),
    (400, 0, "SCHEMA"), (429, 0, "RATE_LIMIT"), (500, 0, "UPSTREAM"),
    (200, 0, "HTTP_REACHED"), (None, 6, "DNS"), (None, 7, "NETWORK_CONNECT"),
    (None, 60, "TLS"), (None, 28, "UNRESOLVED_EXTERNAL")])
def test_http_classification_never_turns_curl000_into_401(code, returncode, expected):
    assert module("diagnose_provider_network").classify_http(code, returncode) == expected


def test_proxy_context_does_not_expose_credentials():
    info = module("diagnose_provider_network").proxy_description("https://user:password@127.0.0.1:7897/?key=secret")
    assert info == {"set": True, "scheme": "https", "host": "127.0.0.1", "port": 7897, "has_credentials": True}
    assert "secret" not in json.dumps(info) and "password" not in json.dumps(info)


@pytest.mark.parametrize("connect,tls,expected", [(0, 0, "NETWORK_CONNECT"), (0.1, 0, "TLS"),
                                               (0.1, 0.2, "NETWORK_READ_TIMEOUT")])
def test_timeout_phase_uses_observed_timings(connect, tls, expected):
    assert module("diagnose_provider_network").classify_http(None, 28, {
        "time_connect": connect, "time_appconnect": tls}) == expected


@pytest.mark.parametrize("failure", [None, "401", "no-http"])
def test_single_completion_receipt_resume_and_stop(tmp_path, monkeypatch, failure):
    probe = module("provider_round02_probe")
    calls = []
    model = "mimo-v2.6-pro"

    class FakePort:
        stop_on_provider_error = True

        def __init__(self, **kwargs):
            self._requester = lambda *args: {}

        async def discover_models(self):
            return [{"model_id": model, "pricing": {"input": 1, "output": 2}}]

        async def describe_model(self, model_id):
            return {"model_id": model_id, "vendor": "xiaomi", "protocols": ["openai.chat_completions"],
                    "specs": {"max_output_tokens": 4096}, "domains": [{"capabilities": [
                        {"key": "output-limit", "protocols": [{"protocol": "openai.chat_completions",
                         "fields": [{"name": "max_completion_tokens", "range": {"min": 1, "max": 4096}}]}]}]}]}

        async def generate(self, profile, request):
            calls.append((profile, request))
            if failure == "401":
                raise ProviderPermanentError("HTTP 401")
            if failure == "no-http":
                raise ProviderTransientError("network timeout without HTTP")
            receipt = json.loads(request.messages[0]["content"].split("text: ", 1)[1])
            return ModelResponse(text=json.dumps(receipt), tool_calls=(),
                                 usage={"prompt_tokens": 10, "completion_tokens": 5}, model_id=model,
                                 provider_metadata={"model": model, "transport_metadata": {"http_status": 200}},
                                 finish_reason="stop")

    monkeypatch.setattr(probe, "AIHubMixAdapter", FakePort)
    monkeypatch.setattr(probe, "load_workspace_env", lambda _: None)
    base = "https://api.inferera.com/v1"
    asyncio.run(probe.run(tmp_path, base))
    original = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    asyncio.run(probe.run(tmp_path, base))
    assert len(calls) == 1
    assert original == {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    result = json.loads((tmp_path / "S1_RESULT.json").read_text())
    assert result["status"] == ("PASS" if failure is None else "BLOCKED")
    assert result["provider_recovered"] == ("YES" if failure is None else "UNVERIFIED")
    attempts = list((tmp_path / "model_io").glob("*/attempt-*.json"))
    assert len(attempts) == 1
    if failure == "no-http":
        assert json.loads(attempts[0].read_text())["status"] == "REQUEST_UNRESOLVED"
    assert calls[0][1].parameters["max_completion_tokens"] == 2048
    assert "response_format" not in calls[0][1].parameters  # No JSON/word-only prompt mismatch.
