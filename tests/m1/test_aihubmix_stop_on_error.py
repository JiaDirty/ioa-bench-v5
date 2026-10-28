"""The opt-in auxiliary policy makes one transport attempt and exposes its failure."""
import asyncio
import io
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from ioabench.errors import ModelUnsupportedError, ProviderPermanentError, ProviderTransientError
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
import ioabench.models.aihubmix as module


PROFILE = ModelProfile("aihubmix", "auxiliary-model", {}, {}, role="GENERATOR")
REQUEST = ModelRequest(({"role": "user", "content": "hello"},), {})


@pytest.mark.parametrize("failure", ["http", "connection", "json"])
def test_post_urllib_failure_is_one_primary_attempt(monkeypatch, failure):
    calls = []
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    monkeypatch.setattr(module.time, "sleep", lambda _: pytest.fail("unexpected retry delay"))

    def urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        if failure == "http":
            raise HTTPError(request.full_url, 429, "busy", None, None)
        if failure == "connection":
            raise URLError("connection unavailable")
        response = io.BytesIO(b"not JSON")
        response.headers = {}
        return response

    monkeypatch.setattr(module, "urlopen", urlopen)
    adapter = AIHubMixAdapter(api_key="test-secret", stop_on_provider_error=True)
    with pytest.raises(ProviderTransientError):
        asyncio.run(adapter.generate(PROFILE, REQUEST))
    assert len(calls) == 1
    assert calls[0][0] == "https://api.inferera.com/v1/chat/completions"
    # Subtracting monotonic deadlines can round a fraction above the budget.
    assert 0 < calls[0][1] <= 900 + 1e-6


@pytest.mark.parametrize("failure", ["transient", "permanent", "no-response"])
def test_post_windows_curl_does_not_change_transport_or_endpoint(monkeypatch, failure):
    calls = []
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(module.shutil, "which", lambda _: "curl.exe")
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: pytest.fail("unexpected urllib fallback"))
    monkeypatch.setattr(module.time, "sleep", lambda _: pytest.fail("unexpected retry delay"))

    def curl(base_url, method, path, body, key, timeout):
        calls.append((base_url, method, path, timeout))
        if failure == "transient":
            raise ProviderTransientError("channel unavailable")
        if failure == "permanent":
            raise ProviderPermanentError("invalid request")
        return None

    monkeypatch.setattr(module, "_curl_json", curl)
    adapter = AIHubMixAdapter(api_key="test-secret", stop_on_provider_error=True)
    expected = ProviderPermanentError if failure == "permanent" else ProviderTransientError
    with pytest.raises(expected):
        asyncio.run(adapter.generate(PROFILE, REQUEST))
    assert len(calls) == 1
    assert calls[0][:3] == ("https://api.inferera.com/v1", "POST", "/chat/completions")
    assert 0 < calls[0][3] <= 900


@pytest.mark.parametrize("missing", [False, True], ids=["request-error", "model-unavailable"])
def test_resolve_stops_without_alternative_catalog(missing):
    calls = []

    def requester(method, path, body):
        calls.append(path)
        if missing:
            return {"data": [{"id": "different-model"}]}
        raise ProviderTransientError("catalog unavailable")

    adapter = AIHubMixAdapter(api_key="test-secret", requester=requester, stop_on_provider_error=True)
    with pytest.raises(ModelUnsupportedError if missing else ProviderTransientError):
        asyncio.run(adapter.resolve(PROFILE.model_id))
    assert calls == ["/models"]


@pytest.mark.parametrize("stop", [False, True])
@pytest.mark.parametrize("invalid_detail", [False, True])
def test_discovery_preserves_normal_enrichment_but_exposes_failure_when_enabled(stop, invalid_detail):
    calls = []

    def requester(method, path, body):
        calls.append(path)
        if path == "/models":
            return {"data": [{"id": PROFILE.model_id}]}
        if invalid_detail:
            return {"data": "invalid catalog"}
        raise ProviderTransientError("detail catalog unavailable")

    adapter = AIHubMixAdapter(api_key="test-secret", requester=requester, stop_on_provider_error=stop)
    if stop:
        with pytest.raises(ProviderPermanentError if invalid_detail else ProviderTransientError):
            asyncio.run(adapter.discover_models())
    else:
        assert asyncio.run(adapter.discover_models()) == ({"id": PROFILE.model_id},)
    assert calls == ["/models", "/api/v1/models"]


def test_stop_on_error_allows_successful_catalog_enrichment():
    calls = []

    def requester(method, path, body):
        calls.append(path)
        if path == "/models":
            return {"data": [{"id": PROFILE.model_id}]}
        return {"data": [{"model_id": PROFILE.model_id, "developer_id": "Example"}]}

    adapter = AIHubMixAdapter(api_key="test-secret", requester=requester, stop_on_provider_error=True)
    discovered = asyncio.run(adapter.discover_models())
    assert discovered[0]["id"] == PROFILE.model_id
    assert discovered[0]["developer_id"] == "Example"
    assert calls == ["/models", "/api/v1/models"]


def test_default_retry_behavior_remains_available(monkeypatch):
    calls = []
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    adapter = AIHubMixAdapter(api_key="test-secret")

    def request_once(method, path, body, *, deadline):
        calls.append(path)
        if len(calls) == 1:
            raise ProviderTransientError("temporary failure")
        return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}

    monkeypatch.setattr(adapter, "_request_json_once", request_once)
    assert asyncio.run(adapter.generate(PROFILE, REQUEST)).text == "ok"
    assert calls == ["/chat/completions", "/chat/completions"]


def test_default_resolve_fallback_is_unchanged():
    calls = []

    def requester(method, path, body):
        calls.append(path)
        if path == "/models":
            raise ProviderTransientError("primary catalog unavailable")
        return {"data": [{"id": PROFILE.model_id}]}

    adapter = AIHubMixAdapter(api_key="test-secret", requester=requester)
    assert asyncio.run(adapter.resolve(PROFILE.model_id)).model_id == PROFILE.model_id
    assert calls == ["/models", "/api/v1/models"]
