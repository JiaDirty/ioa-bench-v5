from __future__ import annotations

import asyncio

import pytest

from ioabench.errors import ModelUnsupportedError
from ioabench.models import DeepSeekAdapter, ModelProfile, ModelRequest


def test_direct_deepseek_catalog_resolution_and_response_parsing() -> None:
    def requester(method, path, body):
        if method == "GET" and path == "/models":
            return {"data": [{"id": "deepseek-flash"}]}
        assert method == "POST" and path == "/chat/completions"
        assert body["model"] == "deepseek-flash"
        assert body["messages"][0]["role"] == "user"
        return {"id": "probe-1", "model": "deepseek-flash", "choices": [{
            "message": {"content": "READY", "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 3}}

    adapter = DeepSeekAdapter(api_key="fixture", requester=requester)
    profile = asyncio.run(adapter.resolve("deepseek-flash"))
    response = asyncio.run(adapter.generate(profile, ModelRequest(
        ({"role": "user", "content": "Reply READY."},), {"temperature": 0.0})))
    assert profile.provider == "deepseek"
    assert response.text == "READY"
    assert response.provider_metadata["model"] == "deepseek-flash"
    assert adapter.base_url == "https://api.deepseek.com"


def test_direct_deepseek_forwards_official_thinking_wire_format() -> None:
    def requester(method, path, body):
        assert (method, path) == ("POST", "/chat/completions")
        assert body["thinking"] == {"type": "enabled"}
        assert body["reasoning_effort"] == "high"
        assert body["messages"][1]["reasoning_content"] == "prior reasoning"
        return {"model": "deepseek-flash", "choices": [{"message": {
            "content": "Done", "reasoning_content": "current reasoning"}, "finish_reason": "stop"}]}

    adapter = DeepSeekAdapter(api_key="fixture", requester=requester)
    profile = ModelProfile("deepseek", "deepseek-flash", {}, {})
    response = asyncio.run(adapter.generate(profile, ModelRequest((
        {"role": "system", "content": "Follow the task."},
        {"role": "assistant", "content": "", "reasoning_content": "prior reasoning"},
        {"role": "user", "content": "Continue."}),
        {"thinking": {"type": "enabled"}, "reasoning_effort": "high"})))
    assert response.text == "Done"
    assert response.reasoning_content == "current reasoning"


def test_direct_deepseek_rejects_unknown_model() -> None:
    adapter = DeepSeekAdapter(api_key="fixture", requester=lambda *_: {"data": []})
    with pytest.raises(ModelUnsupportedError):
        asyncio.run(adapter.resolve("missing-model"))


def test_direct_cli_uses_explicit_official_configuration(tmp_path, monkeypatch) -> None:
    from scripts.v5 import run_deepseek_flash_smoke as smoke

    class Adapter:
        base_url = "https://api.deepseek.com"

        def __init__(self, **kwargs):
            pass

        async def resolve(self, model_id):
            return ModelProfile("deepseek", model_id, {}, {})

        async def discover_models(self):
            return ({"id": "deepseek-flash"},)

    captured = {}
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "DeepSeekAdapter", Adapter)
    monkeypatch.setattr(smoke, "run_batch", lambda *a, **kw: captured.update(kw) or {})
    monkeypatch.setattr(smoke, "read_cases", lambda path: [])
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")
    monkeypatch.setattr("sys.argv", ["smoke", "--cases", "cases.jsonl", "--run-id", "fresh"])
    assert smoke.main() == 0
    assert captured["parameters"] == {"thinking": {"type": "enabled"}, "reasoning_effort": "high",
                                      "stream": False, "max_tokens": 131072}
    assert captured["expected_identity"]["base_url"] == Adapter.base_url
    assert captured["required_model_id"] == "deepseek-flash"


def test_direct_cli_refuses_overwrite_before_provider(tmp_path, monkeypatch) -> None:
    from scripts.v5 import run_deepseek_flash_smoke as smoke

    directory = tmp_path / "artifacts/v5/evaluations/existing"
    directory.mkdir(parents=True)
    probe = directory / "identity-probe.json"
    probe.write_text("historical evidence", encoding="utf-8")
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["smoke", "--cases", "cases.jsonl", "--run-id", "existing"])
    with pytest.raises(SystemExit, match="already exists"):
        smoke.main()
    assert probe.read_text(encoding="utf-8") == "historical evidence"
