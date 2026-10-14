from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from ioabench.errors import ModelUnsupportedError


def _key(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())


def supports_feature(entry: Mapping[str, Any], feature: str) -> bool:
    features = entry.get("features", ())
    if isinstance(features, str):
        features = re.split(r"[,\s]+", features)
    return feature in features


def auxiliary_chat_parameters(schema: Mapping[str, Any] | None, *, max_tokens: int,
                              effort: str = "high") -> dict[str, Any]:
    """Use the per-model official contract without changing frozen SUT requests."""
    if schema is None:
        # No published model schema: basic documented Chat API only; qualify by a live probe.
        return {"max_completion_tokens": max_tokens}
    if "openai.chat_completions" not in schema.get("protocols", []):
        raise ModelUnsupportedError("model schema does not support Chat Completions")
    capabilities = {}
    for domain in schema.get("domains", []):
        for capability in domain.get("capabilities", []):
            protocol = next((item for item in capability.get("protocols", [])
                             if item.get("protocol") == "openai.chat_completions"), None)
            if protocol and protocol.get("official", {}).get("verdict") != "not-applicable":
                capabilities[capability["key"]] = protocol
    limit_fields = capabilities.get("output-limit", {}).get("fields", [])
    names = {field.get("name") for field in limit_fields}
    limit_name = "max_completion_tokens" if "max_completion_tokens" in names else "max_tokens"
    ceiling = schema.get("specs", {}).get("max_output_tokens", max_tokens)
    parameters: dict[str, Any] = {limit_name: min(max_tokens, int(ceiling))}
    effort_fields = list(capabilities.get("reasoning-effort", {}).get("fields", []))
    effort_fields += [item for item in schema.get("standalone_overrides", [])
                      if item.get("protocol") == "openai.chat_completions"
                      and item.get("field") == "reasoning_effort"]
    levels = next((field.get("enum") for field in effort_fields if field.get("enum")), [])
    selected_effort = next((level for level in [effort, "medium", "high", "low"] if level in levels), None)
    if selected_effort:
        parameters["reasoning_effort"] = selected_effort
    if "thinking-toggle" in capabilities and schema.get("vendor") in {"xiaomi", "zhipu"}:
        parameters["thinking"] = {"type": "enabled"}
    # Claude's json_object degrades on the gateway; strict local validation still applies.
    if "structured-output-json" in capabilities and schema.get("vendor") != "anthropic":
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
