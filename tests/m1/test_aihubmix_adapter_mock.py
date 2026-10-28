import asyncio
import threading
import time

import pytest

from ioabench.errors import ModelUnsupportedError, ProviderPermanentError, ProviderTransientError
from ioabench.models import AIHubMixAdapter, ModelRequest


def test_adapter_resolves_exact_id_and_generates_without_network() -> None:
    calls = []

    def requester(method, path, body):
        calls.append((method, path, dict(body)))
        if path == "/models":
            return {"data": [{"id": "deepseek-v4.1-flash", "capabilities": {"tools": True}}]}
        return {"id": "response-1", "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"total_tokens": 3}}

    adapter = AIHubMixAdapter(api_key="secret", requester=requester)
    profile = asyncio.run(adapter.resolve("deepseek-v4.1-flash"))
    response = asyncio.run(adapter.generate(profile, ModelRequest(messages=({"role": "user", "content": "hello"},), parameters={"temperature": 0})))

    assert profile.model_id == "deepseek-v4.1-flash"
    assert response.model_id == "deepseek-v4.1-flash"
    assert response.text == "ok"
    assert calls[1][2]["model"] == "deepseek-v4.1-flash"


def test_adapter_never_substitutes_requested_model() -> None:
    adapter = AIHubMixAdapter(api_key="secret", requester=lambda *_: {"data": [{"id": "other-model"}]})
    with pytest.raises(ModelUnsupportedError):
        asyncio.run(adapter.resolve("deepseek-v4.1-flash"))


def test_adapter_accepts_current_model_catalog_shape() -> None:
    def requester(method, path, body):
        assert path in {"/models", "/api/v1/models"}
        return {"data": [{"model_id": "deepseek-v4.1-flash", "features": "tools", "endpoints": "chat_completions"}]}

    profile = asyncio.run(AIHubMixAdapter(api_key="secret", requester=requester).resolve("deepseek-v4.1-flash"))
    assert profile.capabilities["features"] == "tools"
    assert profile.capabilities["endpoints"] == "chat_completions"


def test_adapter_discovers_authenticated_catalog() -> None:
    def requester(method, path, body):
        assert method == "GET" and body == {}
        if path == "/models":
            return {"data": [{"model_id": "qwen3.8-max"}]}
        assert path == "/api/v1/models"
        return {"data": [{"model_id": "qwen3.8-max", "model_name": "Qwen3.8 Max",
                          "developer_id": "Alibaba", "features": "structured_outputs"}]}

    models = asyncio.run(AIHubMixAdapter(api_key="secret", requester=requester).discover_models())
    assert models[0]["model_id"] == "qwen3.8-max"
    assert models[0]["developer_id"] == "Alibaba"


def test_malformed_provider_response_is_typed() -> None:
    adapter = AIHubMixAdapter(api_key="secret", requester=lambda *_: {"choices": []})
    profile = type("Profile", (), {"provider": "aihubmix", "model_id": "model"})()
    with pytest.raises(ProviderPermanentError):
        asyncio.run(adapter.generate(profile, ModelRequest(messages=({"role": "user", "content": "hello"},), parameters={})))


def test_adapter_provider_io_does_not_block_batch_event_loop() -> None:
    active_requests = 0
    peak_active_requests = 0
    state_lock = threading.Lock()

    def requester(method, path, body):
        nonlocal active_requests, peak_active_requests
        if method == "POST":
            with state_lock:
                active_requests += 1
                peak_active_requests = max(peak_active_requests, active_requests)
            time.sleep(0.05)
            with state_lock:
                active_requests -= 1
        return {"id": "response-1", "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}

    adapter = AIHubMixAdapter(api_key="secret", requester=requester)
    profile = type("Profile", (), {"provider": "aihubmix", "model_id": "model"})()

    async def generate_in_parallel() -> None:
        request = ModelRequest(messages=({"role": "user", "content": "hello"},), parameters={})
        await asyncio.gather(adapter.generate(profile, request), adapter.generate(profile, request))

    asyncio.run(generate_in_parallel())
    assert peak_active_requests == 2


def test_adapter_parses_reasoning_channels_and_keeps_served_identity() -> None:
    def requester(method, path, body):
        return {"id": "resp-9", "model": "deepseek-v4-1-flash-260910",
                "choices": [{"message": {"role": "assistant", "content": None,
                                          "reasoning_content": "weigh the ledger first",
                                          "reasoning_details": [{"type": "thinking", "thinking": "weigh the ledger first"}],
                                          "tool_calls": [{"id": "c1", "type": "function",
                                                          "function": {"name": "t", "arguments": "{}"}}]},
                            "finish_reason": "tool_calls"}],
                "usage": {"total_tokens": 5}}

    adapter = AIHubMixAdapter(api_key="secret", requester=requester)
    profile = type("Profile", (), {"provider": "aihubmix", "model_id": "deepseek-v4.1-flash"})()
    response = asyncio.run(adapter.generate(profile, ModelRequest(messages=({"role": "user", "content": "hi"},), parameters={})))

    assert response.reasoning_content == "weigh the ledger first"
    assert response.reasoning_details == [{"type": "thinking", "thinking": "weigh the ledger first"}]
    assert response.provider_metadata["model"] == "deepseek-v4-1-flash-260910"
    assert response.provider_metadata["endpoint_family"] == "openai-chat-completions"
    assert response.model_id == "deepseek-v4.1-flash"


def test_http_error_statuses_are_classified_not_swallowed(monkeypatch) -> None:
    import ioabench.models.aihubmix as module
    from urllib.error import HTTPError

    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    attempts = []

    def fake_urlopen(request, timeout):
        attempts.append(request)
        raise HTTPError(str(request.full_url), code, "err", None, None)

    for code, expected in ((400, ProviderPermanentError), (403, ProviderPermanentError),
                           (404, ModelUnsupportedError), (429, ProviderTransientError)):
        attempts.clear()
        monkeypatch.setattr(module, "urlopen", fake_urlopen)
        adapter = AIHubMixAdapter(api_key="secret")
        with pytest.raises(expected):
            adapter._request_json_once("POST", "/chat/completions", {"model": "m", "messages": []})
        assert len(attempts) == 1  # a typed HTTP status must not trigger the fallback base URL


def test_request_timeout_is_one_budget_across_retry_and_fallback(monkeypatch) -> None:
    import ioabench.models.aihubmix as module
    from urllib.error import HTTPError

    clock = [0.0]
    timeouts = []
    sleeps = []
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    def urlopen(request, timeout):
        timeouts.append(timeout)
        if len(timeouts) == 1:
            raise HTTPError(str(request.full_url), 429, "busy", None, None)
        clock[0] += timeout
        raise TimeoutError("deadline")

    monkeypatch.setattr(module.time, "sleep", sleep)
    monkeypatch.setattr(module, "urlopen", urlopen)
    adapter = AIHubMixAdapter(api_key="secret", request_timeout=2.0)
    with pytest.raises(ProviderTransientError, match="deadline exceeded"):
        adapter._request_json("POST", "/chat/completions", {"model": "m", "messages": []})

    assert timeouts == [2.0, 0.5]
    assert sleeps == [1.5]


def test_official_schema_fetch_is_opt_in_cached_and_confined_to_provider() -> None:
    calls = []
    def requester(method, path, body):
        calls.append(path)
        if path == "/model-data/index.json":
            return {"models": [{"id": "aux", "path": "models/aux.abc.json"}]}
        return {"model_id": "aux", "protocols": ["openai.chat_completions"]}
    adapter = AIHubMixAdapter(api_key="secret", requester=requester)
    first = asyncio.run(adapter.describe_model("aux"))
    assert asyncio.run(adapter.describe_model("aux")) == first
    assert asyncio.run(adapter.describe_model("missing")) is None
    assert calls == ["/model-data/index.json", "/model-data/models/aux.abc.json"]
    adapter = AIHubMixAdapter(api_key="secret", requester=lambda *_: {
        "models": [{"id": "aux", "path": "models/../../secret.json"}]})
    with pytest.raises(ProviderPermanentError, match="schema path"):
        asyncio.run(adapter.describe_model("aux"))


def test_curl_preserves_only_documented_identity_headers(monkeypatch) -> None:
    import json
    from pathlib import Path
    from types import SimpleNamespace
    import ioabench.models.aihubmix as module

    def run(command, **kwargs):
        assert "--http1.1" in command
        Path(command[command.index("--dump-header") + 1]).write_text(
            "HTTP/1.1 200 Connection established\n\nHTTP/1.1 200 OK\n"
            "X-Aihubmix-Model: aux\nX-Aihubmix-Fallback: false\n"
            "Set-Cookie: sensitive\nX-Structured-Output-Degraded: unsupported\n\n")
        return SimpleNamespace(stdout=json.dumps({"model": "aux-2026-10-12"}) + "\n__IOA_STATUS__200", returncode=0)
    monkeypatch.setattr(module.shutil, "which", lambda _: "curl.exe")
    monkeypatch.setattr(module.subprocess, "run", run)
    payload = module._curl_json("https://aihubmix.com/v1", "POST", "/chat/completions", {}, "secret", 2)
    assert payload["transport_metadata"] == {"x-aihubmix-model": "aux", "x-aihubmix-fallback": "false",
                                             "x-structured-output-degraded": "unsupported", "http_status": 200}
    assert payload["model"] == "aux-2026-10-12"
