import copy

import pytest

from ioabench.errors import ModelUnsupportedError
from ioabench.v5.ai_generation.model_routing import (auxiliary_chat_parameters,
    ordered_catalog_candidates, served_catalog_entry, supports_feature)


def test_live_catalog_matching_is_exact_ordered_and_family_separated() -> None:
    catalog = [
        {"model_id": "qwen3.8-max", "model_name": "Qwen3.8 Max", "developer_id": "Alibaba",
         "features": "tools,structured_outputs"},
        {"model_id": "glm-5.3-flash", "model_name": "GLM 5.3 Flash", "developer_id": "Zhipu",
         "features": ["structured_outputs"]},
        {"model_id": "glm-5.3-flash-preview", "model_name": "GLM 5.3 Flash Preview",
         "developer_id": "Zhipu", "features": "structured_outputs"},
        {"model_id": "retired-model", "model_name": "Old Candidate", "developer_id": "Other",
         "features": "structured_outputs", "retire_stage": "deprecated"},
    ]

    generators = ordered_catalog_candidates(
        ["Qwen3.8 Max", "GLM-5.3-Flash"], catalog, required_feature="structured_outputs")
    reviewers = ordered_catalog_candidates(
        ["Qwen3.8 Max", "GLM-5.3-Flash", "Old Candidate"], catalog,
        exclude_developer_id="Alibaba", required_feature="structured_outputs")

    assert [entry["model_id"] for entry in generators] == ["qwen3.8-max", "glm-5.3-flash"]
    assert [entry["model_id"] for entry in reviewers] == ["glm-5.3-flash"]
    assert supports_feature(catalog[0], "structured_outputs")


def test_live_catalog_matching_does_not_guess_prefixes_or_ambiguous_names() -> None:
    catalog = [
        {"model_id": "model-v1", "model_name": "Strong Model", "developer_id": "A",
         "features": "structured_outputs"},
        {"model_id": "model-v2", "model_name": "Strong Model", "developer_id": "A",
         "features": "structured_outputs"},
        {"model_id": "qwen3.8-max-preview", "model_name": "Qwen3.8 Max Preview", "developer_id": "B",
         "features": "structured_outputs"},
    ]
    assert ordered_catalog_candidates(["Strong Model", "qwen3.8-max"], catalog) == []


@pytest.mark.parametrize(("vendor", "limit", "levels", "expected_effort", "json_mode"), [
    ("xiaomi", "max_completion_tokens", [], None, True),
    ("alibaba", "max_completion_tokens", ["low", "medium", "xhigh"], "medium", True),
    ("zhipu", "max_tokens", ["low", "high", "max"], "high", False),
    ("anthropic", "max_completion_tokens", ["low", "high"], "high", False),
    ("google", "max_completion_tokens", ["low", "medium", "high"], "high", True),
    ("openai", "max_completion_tokens", ["low", "medium", "high", "xhigh", "max"], "high", True),
])
def test_auxiliary_contract_respects_model_budget_effort_and_json_limits(vendor, limit, levels, expected_effort, json_mode):
    schema = {"vendor": vendor, "protocols": ["openai.chat_completions"],
              "specs": {"max_output_tokens": 32768}, "domains": [{"capabilities": [
                  {"key": key, "protocols": [{"protocol": "openai.chat_completions",
                   "fields": fields, "official": {"verdict": "official-model-level"}}]}
                  for key, fields in [("output-limit", [{"name": limit}]),
                                      ("reasoning-effort", [{"name": "reasoning_effort", "enum": levels, "default": expected_effort}]),
                                      ("thinking-toggle", []), ("structured-output-json", [])]
                  if key != "structured-output-json" or vendor != "zhipu"]}]}
    before = copy.deepcopy(schema)
    result = auxiliary_chat_parameters(schema)
    assert result[limit] == 32768
    assert result.get("reasoning_effort") == expected_effort
    assert ("response_format" in result) == json_mode
    if vendor in {"xiaomi", "zhipu"}:
        assert result["thinking"] == {"type": "enabled"}
    assert schema == before
    with pytest.raises(ModelUnsupportedError):
        auxiliary_chat_parameters({"protocols": ["openai.responses"]})


def documented_schema(model_id="glm-5.3-flash", *, vendor="zhipu", maximum=131072):
    return {"model_id": model_id, "vendor": vendor, "protocols": ["openai.chat_completions"],
        "specs": {"max_output_tokens": maximum}, "domains": [{"capabilities": [
            {"key": key, "protocols": [{"protocol": "openai.chat_completions", "fields": fields}]}
            for key, fields in [
                ("output-limit", [{"name": "max_tokens", "range": {"max": maximum}}]),
                ("reasoning-effort", [{"name": "reasoning_effort", "default": "max",
                    "enum": ["low", "medium", "high", "max"]}]),
                ("thinking-toggle", [{"name": "thinking.clear_thinking"}]),
                ("sampling-temperature", [{"name": "temperature", "default": 1.0},
                    {"name": "top_p", "default": 0.95}]),
                ("function-calling", []), ("structured-output-json", [])]]}]}


def test_documented_maximum_and_glm_recommendations_are_not_discounted():
    result = auxiliary_chat_parameters(documented_schema())
    assert result == {"max_tokens": 131072, "reasoning_effort": "max",
        "thinking": {"type": "enabled", "clear_thinking": False},
        "temperature": 1.0, "top_p": 0.95, "response_format": {"type": "json_object"}}


@pytest.mark.parametrize(("model_id", "maximum", "effort"), [
    ("gpt-6.1-sol", 128000, "medium"), ("gpt-6-luna", 128000, "max"),
    ("gemini-3.8-flash", 65536, "high")])
def test_user_effort_is_preserved_and_incompatible_tools_never_downgrade(model_id, maximum, effort):
    schema = documented_schema(model_id, vendor="other", maximum=maximum)
    if model_id == "gpt-6.1-sol":
        schema["standalone_overrides"] = [{"protocol": "openai.chat_completions",
            "field": "tool_choice", "status": "unsupported-by-model"}]
    assert auxiliary_chat_parameters(schema, effort=effort)["reasoning_effort"] == effort
    if model_id.startswith("gpt-"):
        with pytest.raises(ModelUnsupportedError, match="no effort downgrade"):
            auxiliary_chat_parameters(schema, effort=effort, for_tools=True)
    else:
        assert "response_format" not in auxiliary_chat_parameters(schema, effort=effort, for_tools=True)


def test_missing_limits_or_unsupported_effort_fail_before_provider_call():
    schema = documented_schema()
    with pytest.raises(ModelUnsupportedError, match="effort"):
        auxiliary_chat_parameters(schema, effort="xhigh")
    schema["specs"] = {}
    schema["domains"][0]["capabilities"][0]["protocols"][0]["fields"][0].pop("range")
    with pytest.raises(ModelUnsupportedError, match="numeric"):
        auxiliary_chat_parameters(schema)
    with pytest.raises(ModelUnsupportedError, match="schema"):
        auxiliary_chat_parameters(None)


def test_gateway_identity_header_resolves_dated_body_but_does_not_guess_aliases():
    catalog = [{"model_id": "gpt-6.1-sol", "developer_id": 12},
               {"model_id": "claude-sonnet-5-5", "developer_id": 2}]
    metadata = {"model": "gpt-6.1-sol-2026-09-29"}
    assert served_catalog_entry(metadata, catalog) is None
    metadata["transport_metadata"] = {"x-aihubmix-model": "gpt-6.1-sol"}
    assert served_catalog_entry(metadata, catalog) == catalog[0]
    metadata["transport_metadata"] = {"x-aihubmix-model": "unknown", "x-aihubmix-fallback": "true"}
    assert served_catalog_entry(metadata, catalog) is None


@pytest.mark.parametrize(("finish", "gateway_id", "expected"), [
    ("stop", "aux", "PASS"), ("length", "aux", "NOT_QUALIFIED"),
    ("stop", "other", "NOT_QUALIFIED")])
def test_protocol_probe_requires_correct_content_complete_output_and_independent_identity(finish, gateway_id, expected):
    import asyncio
    import importlib.util
    from pathlib import Path
    from ioabench.models import ModelProfile, ModelResponse

    spec = importlib.util.spec_from_file_location("aux_probe", Path(__file__).resolve().parents[2] / "scripts/aux_model_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Adapter:
        base_url = "https://test.invalid/v1"
        async def resolve(self, model_id):
            return ModelProfile("aihubmix", model_id, {}, {})
        async def describe_model(self, model_id):
            return {"protocols": ["openai.chat_completions"], "specs": {"max_output_tokens": 131072},
                "domains": [{"capabilities": [{"key": "output-limit", "protocols": [{
                    "protocol": "openai.chat_completions", "fields": [{"name": "max_completion_tokens"}]}]}]}]}
        async def generate(self, profile, request):
            assert request.parameters == {"max_completion_tokens": 131072}
            return ModelResponse(text='{"probe":"ioa-protocol-20261012","value":42}', model_id="aux",
                finish_reason=finish, provider_metadata={"model": "aux-dated",
                    "transport_metadata": {"x-aihubmix-model": gateway_id}})
    catalog = [{"model_id": "aux", "developer_id": 1}, {"model_id": "other", "developer_id": 2}]
    result = asyncio.run(module.probe_protocol(Adapter(), "aux", catalog))
    assert result["status"] == expected
