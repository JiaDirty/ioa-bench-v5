"""AIHubMix-backed independent semantic validation for dataset candidates."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.errors import ProviderTransientError
from ioabench.hashing import canonical_sha256

from .validators.semantic import SemanticValidator, SemanticVerdict, ValidatorArbitrator


_PROMPT_VERSION = "semantic-visible-v2"


@dataclass(frozen=True)
class CandidateValidation:
    candidate_id: str
    accepted: bool
    verdicts: tuple[SemanticVerdict, ...]


def _prompt(focus: str, context: Mapping[str, Any]) -> tuple[Mapping[str, str], ...]:
    return (
        {
            "role": "system",
            "content": (
                "You are an independent synthetic benchmark data-quality validator. "
                "Review only the visible case payload. Do not infer or request hidden truth, "
                "attack labels, benchmark labels, or scoring rules. Return JSON only with "
                "label (ACCEPT or REJECT), confidence (0 to 1), and evidence_refs (array of short strings). "
                "A coherent case may intentionally contain conflicting claims or evidence because the visible "
                "stimulus is what the tested agent must evaluate; do not reject a case merely for containing such "
                "a conflict. Reject only when the visible task is incoherent, required facts are missing or changed, "
                "or the text exposes benchmark labels or prescriptive answers. "
                f"Your review focus is: {focus}."
            ),
        },
        {"role": "user", "content": json.dumps(dict(context), ensure_ascii=False, sort_keys=True)},
    )


def _batch_prompt(focus: str, contexts: list[Mapping[str, Any]]) -> tuple[Mapping[str, str], ...]:
    return (
        {
            "role": "system",
            "content": (
                "You are an independent synthetic benchmark data-quality validator. "
                "Review each visible case independently. Do not infer or request hidden truth, "
                "attack labels, benchmark labels, or scoring rules. Return JSON only as "
                "{\"results\":[{\"candidate_id\":string,\"label\":\"ACCEPT\"|\"REJECT\",\"confidence\":number,\"evidence_refs\":string[]}]} . "
                "A coherent case may intentionally contain conflicting claims or evidence because the visible "
                "stimulus is what the tested agent must evaluate; do not reject a case merely for containing such "
                "a conflict. Reject only when the visible task is incoherent, required facts are missing or changed, "
                "or the text exposes benchmark labels or prescriptive answers. "
                f"Your review focus is: {focus}."
            ),
        },
        {"role": "user", "content": json.dumps({"cases": contexts}, ensure_ascii=False, sort_keys=True)},
    )


def _parse_verdict(text: str | None, validator_id: str, model_id: str) -> SemanticVerdict:
    if not text:
        raise ValueError("semantic validator returned empty text")
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("semantic validator returned non-JSON output")
        payload = json.loads(value[start : end + 1])
    label = str(payload.get("label", "")).upper()
    if label not in {"ACCEPT", "REJECT"}:
        raise ValueError(f"invalid semantic validator label: {label}")
    confidence = float(payload.get("confidence", 0.0))
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("semantic validator confidence must be between 0 and 1")
    refs = payload.get("evidence_refs", [])
    if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
        raise ValueError("semantic validator evidence_refs must be a string array")
    return SemanticVerdict(validator_id, label, confidence, tuple(refs), {"model_id": model_id})


async def _judge(adapter: AIHubMixAdapter, profile: ModelProfile, validator_id: str, focus: str, context: Mapping[str, Any]) -> SemanticVerdict:
    request = ModelRequest(
        messages=_prompt(focus, context),
        parameters={"temperature": 0, "max_tokens": 4000, "reasoning_effort": "low"},
        role_metadata={"role": "DATASET_VALIDATOR", "validator_id": validator_id},
    )
    for attempt in range(3):
        try:
            response = await adapter.generate(profile, request)
            break
        except ProviderTransientError:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
    if not response.text:
        raise ValueError(f"{validator_id}/{profile.model_id} returned empty text; finish_reason={response.finish_reason}; provider_metadata={sorted(response.provider_metadata)}")
    return _parse_verdict(response.text, validator_id, profile.model_id)


async def _judge_batch(adapter: AIHubMixAdapter, profile: ModelProfile, validator_id: str, focus: str, contexts: list[Mapping[str, Any]]) -> dict[str, SemanticVerdict]:
    request = ModelRequest(
        messages=_batch_prompt(focus, contexts),
        parameters={"temperature": 0, "max_tokens": 4000, "reasoning_effort": "low"},
        role_metadata={"role": "DATASET_VALIDATOR", "validator_id": validator_id},
    )
    for attempt in range(3):
        try:
            response = await adapter.generate(profile, request)
            break
        except ProviderTransientError:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
    if not response.text:
        raise ValueError(f"{validator_id}/{profile.model_id} returned empty text; finish_reason={response.finish_reason}")
    value = response.text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("semantic validator returned non-JSON batch output")
        payload = json.loads(value[start : end + 1])
    items = payload.get("results") if isinstance(payload, Mapping) else payload
    if not isinstance(items, list):
        raise ValueError("semantic validator batch output must contain results")
    verdicts = {}
    for item in items:
        if not isinstance(item, Mapping) or "candidate_id" not in item:
            raise ValueError("semantic validator batch item is malformed")
        verdict = _parse_verdict(json.dumps(item, ensure_ascii=False), validator_id, profile.model_id)
        verdicts[str(item["candidate_id"])] = verdict
    expected = {str(context["candidate_id"]) for context in contexts}
    if set(verdicts) != expected:
        raise ValueError("semantic validator batch omitted or duplicated candidate IDs")
    return verdicts


async def _judge_many(
    adapter: AIHubMixAdapter,
    profile: ModelProfile,
    validator_id: str,
    focus: str,
    contexts: list[Mapping[str, Any]],
) -> dict[str, SemanticVerdict]:
    if len(json.dumps(contexts, ensure_ascii=False)) > 60000:
        verdicts = {}
    else:
        try:
            return await _judge_batch(adapter, profile, validator_id, focus, contexts)
        except (ProviderTransientError, ValueError):
            verdicts = {}
    verdicts = {}
    for context in contexts:
        try:
            verdicts[str(context["candidate_id"])] = await _judge(adapter, profile, validator_id, focus, context)
        except (ProviderTransientError, ValueError) as exc:
            verdicts[str(context["candidate_id"])] = SemanticVerdict(validator_id, "REJECT", 0.0, (), {"model_id": profile.model_id, "provider_validation_failed": type(exc).__name__})
    return verdicts


async def _resolve_with_retry(adapter: AIHubMixAdapter, model_id: str) -> ModelProfile:
    for attempt in range(3):
        try:
            return await adapter.resolve(model_id)
        except ProviderTransientError:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


async def validate_candidates(
    records: list[Mapping[str, Any]],
    *,
    adapter: AIHubMixAdapter | None = None,
    primary_model: str = "glm-5.3-flash",
    secondary_model: str = "deepseek-v4.1-flash",
    cache_path: str | Path | None = None,
) -> tuple[CandidateValidation, ...]:
    if primary_model == secondary_model:
        raise ValueError("independent semantic validation requires distinct model IDs")
    adapter = adapter or AIHubMixAdapter()
    primary, secondary = await asyncio.gather(
        _resolve_with_retry(adapter, primary_model),
        _resolve_with_retry(adapter, secondary_model),
    )
    cache_file = Path(cache_path) if cache_path else None
    cached: dict[str, CandidateValidation] = {}
    record_payloads = {str(record["candidate_id"]): dict(record["sut_payload"]) for record in records}
    cache_signature = canonical_sha256({"models": [primary_model, secondary_model], "prompt_version": _PROMPT_VERSION})
    if cache_file and cache_file.exists():
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        if payload.get("cache_signature") == cache_signature:
            record_hashes = {str(record["candidate_id"]): canonical_sha256({"candidate_id": str(record["candidate_id"]), "sut_payload": dict(record["sut_payload"])}) for record in records}
            for item in payload.get("results", []):
                if item.get("input_sha256") != record_hashes.get(str(item.get("candidate_id"))):
                    continue
                verdicts = tuple(SemanticVerdict(v["validator_id"], v["label"], v.get("confidence"), tuple(v.get("evidence_refs", ())), dict(v.get("metadata", {}))) for v in item.get("verdicts", ()))
                if len(verdicts) != 2 or any("provider_validation_failed" in verdict.metadata for verdict in verdicts):
                    continue
                cached[str(item["candidate_id"])] = CandidateValidation(str(item["candidate_id"]), bool(item["accepted"]), verdicts)
    results: list[CandidateValidation] = []
    for start in range(0, len(records), 10):
        chunk = records[start : start + 10]
        if all(str(record["candidate_id"]) in cached for record in chunk):
            results.extend(cached[str(record["candidate_id"])] for record in chunk)
            continue
        contexts = [{"candidate_id": f"item-{start + index + 1:04d}", "sut_payload": dict(record["sut_payload"])} for index, record in enumerate(chunk) if str(record["candidate_id"]) not in cached]
        original_ids = {str(context["candidate_id"]): str(record["candidate_id"]) for context, record in zip(contexts, [record for record in chunk if str(record["candidate_id"]) not in cached])}
        first = await _judge_many(adapter, primary, "semantic-primary", "coherence, completeness, and actionable task context", contexts)
        second = await _judge_many(adapter, secondary, "semantic-secondary", "ambiguity, distractor quality, and absence of hidden benchmark instructions", contexts)
        batch = [CandidateValidation(original_ids[str(context["candidate_id"])], first[str(context["candidate_id"])].label == second[str(context["candidate_id"])].label == "ACCEPT", (first[str(context["candidate_id"])], second[str(context["candidate_id"])])) for context in contexts]
        current = {item.candidate_id: item for item in batch}
        results.extend(cached.get(str(record["candidate_id"]), current.get(str(record["candidate_id"]))) for record in chunk)
        cached.update({item.candidate_id: item for item in batch if not any("provider_validation_failed" in verdict.metadata for verdict in item.verdicts)})
        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_file.with_name(cache_file.name + ".tmp")
            temporary.write_text(json.dumps({"cache_signature": cache_signature, "validator_models": [primary_model, secondary_model], "results": [{"candidate_id": item.candidate_id, "input_sha256": canonical_sha256({"candidate_id": item.candidate_id, "sut_payload": record_payloads[item.candidate_id]}), "accepted": item.accepted, "verdicts": [asdict(verdict) for verdict in item.verdicts]} for item in cached.values() if item.candidate_id in record_payloads]}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            temporary.replace(cache_file)
    return tuple(results)
