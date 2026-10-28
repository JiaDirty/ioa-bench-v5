"""Local Mock checks for the paid study's stop and replay boundaries."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.models import ModelResponse


def study_module():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts/v5"))
    spec = importlib.util.spec_from_file_location("round02_study", root / "scripts/v5/benchmark_provider_round02.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("failure,stopped", [(None, False), ("401", True), ("403", True),
    ("unknown", True), ("partial-http", True), ("400", False), ("500", False), ("429", False)])
def test_study_global_stop_and_terminal_no_resend(tmp_path, failure, stopped):
    module = study_module()
    (tmp_path / "MODEL_CATALOG.json").write_text(json.dumps([{"model_id": "model"}]))
    config = {"id": "model--default", "model": "model", "protocol": "openai.chat_completions", "parameters": {}}
    calls = []

    class Port:
        stop_on_provider_error = True

        async def generate(self, profile, request):
            calls.append(request)
            if failure == "unknown":
                raise ProviderTransientError("network timeout without HTTP")
            if failure == "partial-http":
                error = ProviderTransientError('transport interrupted; {"http_status":"200"}')
                error.category = "REQUEST_UNRESOLVED"
                raise error
            if failure:
                raise ProviderPermanentError("HTTP " + failure)
            return ModelResponse(text="receipt", usage={"prompt_tokens": 1, "completion_tokens": 1},
                provider_metadata={"model": "model", "transport_metadata": {"http_status": 200}},
                model_id="model", finish_reason="stop")

    study = module.Study(tmp_path, Port())
    async def invoke():
        return await study.invoke(config, tmp_path / "model_io", "fresh", [{"role": "user", "content": "receipt"}])
    if failure:
        with pytest.raises(Exception):
            asyncio.run(invoke())
        assert study.stop_path.exists() is stopped
        with pytest.raises(Exception):
            asyncio.run(invoke())
    else:
        assert asyncio.run(invoke()).text == asyncio.run(invoke()).text == "receipt"
    assert len(calls) == 1
    if stopped:
        with pytest.raises(RuntimeError, match="study stopped"):
            asyncio.run(study.invoke(config, tmp_path / "other", "new", []))
        assert len(calls) == 1


def test_probe_receipt_is_strict_and_effort_is_protocol_specific():
    module = study_module()
    assert module._effort({"reasoning": {"effort": "high"}}) == "high"
    assert module._effort({"output_config": {"effort": "max"}}) == "max"
    assert module._effort({"reasoning_effort": "low"}) == "low"
    with pytest.raises(ValueError, match="MODEL_QUALITY"):
        module._text(type("Response", (), {"text": "other"})(), "receipt")


def test_tool_precheck_uses_live_catalog_output_ceiling(tmp_path):
    mod = study_module()
    (tmp_path / "MODEL_CATALOG.json").write_text(json.dumps([{"model_id": "model", "max_output": 4096}]))
    (tmp_path / "schemas").mkdir()
    schema = {"protocols": ["openai.chat_completions"], "domains": [{"capabilities": [
        {"key": "output-limit", "protocols": [{"protocol": "openai.chat_completions", "fields": [{"name": "max_tokens"}]}]},
        {"key": "function-calling", "protocols": [{"protocol": "openai.chat_completions", "fields": []}]}]}]}
    (tmp_path / "schemas/model.json").write_text(json.dumps(schema))
    config = {"id": "model", "model": "model", "protocol": "openai.chat_completions", "parameters": {"max_tokens": 4096}}
    study = mod.Study(tmp_path, object())
    token = mod.canonical_sha256({"run": tmp_path.name, "config": config, "batch": "p1"})[:24]
    values = [ModelResponse(text=token), ModelResponse(text=json.dumps({"receipt": token, "value": 42})),
        ModelResponse(text=json.dumps({"receipt": token})), ModelResponse(text=None, tool_calls=[{"id": "call", "function": {
            "name": "echo_receipt", "arguments": '{"value":42}'}}]), ModelResponse(text='{"received":42}')]
    async def invoke(*args, **kwargs):
        value = values.pop(0)
        if kwargs.get("validate"):
            kwargs["validate"](value)
        return value
    study.invoke = invoke
    assert asyncio.run(study.protocol(config))["status"] == "PASS"
    assert values == []
