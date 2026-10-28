from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from ioabench.errors import ModelUnsupportedError

USER_CANDIDATES = (
    "gpt-6.1-sol", "glm-5.3-flash", "mimo-v2.6-pro", "claude-haiku-5-5",
    "mimo-v2.6-flash", "qwen3.8-flash", "deepseek-v4.1-flash-1017", "glm-5.3",
)


def _key(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())


def supports_feature(entry: Mapping[str, Any], feature: str) -> bool:
    features = entry.get("features", ())
    if isinstance(features, str):
        features = re.split(r"[,\s]+", features)
    return feature in features


def auxiliary_chat_parameters(schema: Mapping[str, Any] | None, *,
                              effort: str | None = None, for_tools: bool = False) -> dict[str, Any]:
    return auxiliary_parameters(schema, effort=effort, for_tools=for_tools)


def auxiliary_parameters(schema: Mapping[str, Any] | None, *, protocol: str = "openai.chat_completions",
                         effort: str | None = None, for_tools: bool = False,
                         output_budget: int | None = None,
                         catalog_entry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Use the per-model official contract without changing frozen SUT requests."""
    if schema is None:
        raise ModelUnsupportedError("exact model parameter schema is required")
    if protocol not in {"openai.chat_completions", "openai.responses", "anthropic.messages"} or protocol not in schema.get("protocols", []):
        raise ModelUnsupportedError("model schema does not support requested protocol")
    capabilities = {}
    for domain in schema.get("domains", []):
        for capability in domain.get("capabilities", []):
            contract = next((item for item in capability.get("protocols", [])
                             if item.get("protocol") == protocol), None)
            if contract and contract.get("official", {}).get("verdict") not in {
                    "not-applicable", "do-not-send", "unsupported-by-model"}:
                capabilities[capability["key"]] = contract
    limit_fields = capabilities.get("output-limit", {}).get("fields", [])
    names = {field.get("name") for field in limit_fields}
    limit_name = ("max_output_tokens" if protocol == "openai.responses" else
                  "max_completion_tokens" if "max_completion_tokens" in names else "max_tokens")
    if limit_name not in names:
        raise ModelUnsupportedError("documented protocol output-limit field is required")
    ceiling = schema.get("specs", {}).get("max_output_tokens")
    field_ceilings = [field.get("range", {}).get("max") for field in limit_fields
                      if field.get("name") == limit_name and field.get("range", {}).get("max")]
    ceilings = [value for value in [ceiling, (catalog_entry or {}).get("max_output"), *field_ceilings]
                if isinstance(value, int) and not isinstance(value, bool) and value > 0]
    if not ceilings:
        raise ModelUnsupportedError("exact numeric maximum output tokens is undocumented")
    parameters: dict[str, Any] = {limit_name: min(ceilings)}
    if output_budget is not None:
        if isinstance(output_budget, bool) or not isinstance(output_budget, int) or not 1 <= output_budget <= min(ceilings):
            raise ModelUnsupportedError("explicit study output budget outside documented model limit")
        minimum = max([1, *[field.get("range", {}).get("min", 1) for field in limit_fields if field.get("name") == limit_name]])
        if output_budget < minimum:
            raise ModelUnsupportedError("explicit study output budget below protocol minimum")
        parameters[limit_name] = output_budget
    effort_fields = list(capabilities.get("reasoning-effort", {}).get("fields", []))
    effort_fields += [item for item in schema.get("standalone_overrides", [])
                      if item.get("protocol") == protocol
                      and item.get("field") in {"reasoning_effort", "reasoning.effort", "output_config.effort"}]
    levels = next((field.get("enum") for field in effort_fields if field.get("enum")), [])
    model_id = str(schema.get("model_id", ""))
    if effort is None:
        for display in USER_CANDIDATES:
            match = re.fullmatch(r"(.+?)\s+\(([^()]+)\)", display)
            if match and _key(match.group(1)) == _key(model_id):
                effort = match.group(2).casefold()
                break
    documented_default = next((item.get("default") for item in schema.get("specs", {}).get("reasoning_options", [])
                               if item.get("type") == "effort" and item.get("default") in levels), None)
    selected_effort = effort or documented_default or next((field.get("default", field.get("value")) for field in effort_fields
                                      if field.get("default", field.get("value"))), None)
    if selected_effort is not None and selected_effort not in levels:
        raise ModelUnsupportedError("requested/default reasoning effort is not documented: " + selected_effort)
    if levels and selected_effort is None:
        raise ModelUnsupportedError("documented default reasoning effort is required")
    if selected_effort:
        if protocol == "openai.responses":
            parameters["reasoning"] = {"effort": selected_effort}
        elif protocol == "anthropic.messages":
            parameters["output_config"] = {"effort": selected_effort}
        else:
            parameters["reasoning_effort"] = selected_effort
    if "thinking-toggle" in capabilities and schema.get("vendor") in {"xiaomi", "zhipu", "deepseek"}:
        parameters["thinking"] = {"type": "enabled"}
    elif "thinking-toggle" in capabilities and schema.get("vendor") == "anthropic":
        parameters["thinking"] = {"type": "adaptive"}
    if schema.get("vendor") == "zhipu":
        if any(field.get("name") == "thinking.clear_thinking"
               for field in capabilities.get("thinking-toggle", {}).get("fields", [])):
            parameters["thinking"]["clear_thinking"] = False
        for field in capabilities.get("sampling-temperature", {}).get("fields", []):
            if field.get("name") in {"temperature", "top_p"} and "default" in field:
                parameters[field["name"]] = field["default"]
    if for_tools:
        if ("function-calling" not in capabilities
                or any(item.get("protocol") == protocol
                       and item.get("field") == "tool_choice" and item.get("status") == "unsupported-by-model"
                       for item in schema.get("standalone_overrides", []))
                or (protocol == "openai.chat_completions" and model_id == "gpt-6-luna" and selected_effort != "none")):
            raise ModelUnsupportedError("documented Chat tools incompatible with this model/effort; no effort downgrade")
    # Claude's json_object degrades on the gateway; strict local validation still applies.
    if not for_tools and "structured-output-json" in capabilities and schema.get("vendor") != "anthropic":
        if protocol == "openai.responses":
            parameters["text"] = {"format": {"type": "json_object"}}
        elif protocol == "openai.chat_completions":
            parameters["response_format"] = {"type": "json_object"}
    return parameters


def served_catalog_entry(metadata: Mapping[str, Any], catalog: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Gateway billing/model header is authoritative; never infer aliases by name similarity."""
    model_id = (metadata.get("transport_metadata") or {}).get("x-aihubmix-model") or metadata.get("model")
    return next((entry for entry in catalog
                 if str(entry.get("model_id") or entry.get("id")) == model_id), None)


def ordered_catalog_candidates(names: Iterable[str], catalog: Iterable[Mapping[str, Any]], *,
                               exclude_ids: Iterable[str] = (),
                               exclude_developer_id: str | None = None,
                               required_feature: str | None = None) -> list[Mapping[str, Any]]:
    """Resolve policy display names to exact live catalog entries, in policy order."""
    entries = [entry for entry in catalog if isinstance(entry, Mapping)]
    excluded_ids = set(exclude_ids)
    excluded_developer = (exclude_developer_id or "").casefold()
    selected: list[Mapping[str, Any]] = []
    selected_ids: set[str] = set()

    for name in names:
        candidate_key = _key(name)
        exact_ids = [entry for entry in entries if _key(str(entry.get("model_id") or entry.get("id") or "")) == candidate_key]
        exact_names = [entry for entry in entries if _key(str(entry.get("model_name") or "")) == candidate_key]
        matches = exact_ids if len(exact_ids) == 1 else exact_names if not exact_ids and len(exact_names) == 1 else []
        if not matches:
            continue
        entry = matches[0]
        model_id = str(entry.get("model_id") or entry.get("id") or "")
        developer_id = str(entry.get("developer_id") or "")
        retirement = str(entry.get("retire_stage") or "").casefold()
        if (not model_id or model_id in excluded_ids or model_id in selected_ids
                or not developer_id or developer_id.casefold() == excluded_developer
                or "retir" in retirement or "deprecat" in retirement
                or (required_feature and not supports_feature(entry, required_feature))):
            continue
        selected.append(entry)
        selected_ids.add(model_id)
    return selected


def resolve_display_candidate(display_name: str, catalog: Iterable[Mapping[str, Any]],
                              schemas: Mapping[str, Mapping[str, Any] | None]) -> dict[str, Any]:
    """Interpret a parenthesized effort only after an exact model-specific schema proves it."""
    entries = list(catalog)
    exact = ordered_catalog_candidates([display_name], entries)
    if exact:
        return {"display_name": display_name, "status": "RESOLVED", "entry": dict(exact[0]),
                "effort": None, "interpretation": "exact live catalog identity"}
    match = re.fullmatch(r"(.+?)\s+\(([^()]+)\)", display_name)
    if not match:
        return {"display_name": display_name, "status": "UNRESOLVED_MODEL_ID"}
    base, requested = match.group(1), match.group(2).casefold()
    matches = ordered_catalog_candidates([base], entries)
    if len(matches) != 1:
        return {"display_name": display_name, "status": "UNRESOLVED_MODEL_ID"}
    entry = matches[0]
    model_id = str(entry.get("model_id") or entry.get("id"))
    schema = schemas.get(model_id)
    if not schema:
        return {"display_name": display_name, "status": "UNVERIFIED_CONFIGURATION",
                "candidate_model_id": model_id}
    try:
        parameters = auxiliary_chat_parameters(schema, effort=requested)
    except ModelUnsupportedError as exc:
        return {"display_name": display_name, "status": "CAPABILITY_UNSUPPORTED",
                "candidate_model_id": model_id, "reason": str(exc)}
    if parameters.get("reasoning_effort") != requested:
        return {"display_name": display_name, "status": "UNVERIFIED_CONFIGURATION",
                "candidate_model_id": model_id, "requested_label": requested}
    return {"display_name": display_name, "status": "RESOLVED", "entry": dict(entry),
            "effort": requested, "interpretation": "model-specific Chat reasoning_effort enum"}
