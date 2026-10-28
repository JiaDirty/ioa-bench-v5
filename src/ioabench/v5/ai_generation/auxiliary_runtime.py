"""Bounded, evidence-preserving auxiliary failover through the existing ModelPort."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping, Sequence

from ioabench.errors import (ConfigurationError, ModelUnsupportedError, ProviderPermanentError,
                            ProviderTransientError, ProviderRequestUnresolved)
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelPort, ModelProfile, ModelRequest, ModelResponse
from ioabench.v5.ai_generation.model_routing import auxiliary_chat_parameters, served_catalog_entry
from ioabench.v5.evaluation import atomic_json, safe_id, writer_lock

ROUTING_VERSION = "ioabench.v5.auxiliary-routing/1.3.2"
WIRE_REQUEST_FORMAT = "ioabench.v5.auxiliary-wire/2"


def engineering_contracts(path: Path, *, workspace: Path, model_ids: Sequence[str]):
    """Read the opt-in engineering generator profile; this cannot qualify an auditor."""
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.v5.ai_generation.factory import tested_family
    path = Path(path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("version") != "ioabench.v5.engineering-routing-profile/1"
            or payload.get("source_sha256") != source_tree_hash(workspace)):
        raise ValueError("engineering routing version/source changed; regenerate its evidence")
    sums = payload.get("evidence_sha256", {})
    if not {"SCORECARD_ALL_MODELS.json", "MODEL_CATALOG.json", "BENCHMARK_TASKSET_FROZEN.json"} <= sums.keys():
        raise ValueError("engineering routing requires bound comparison evidence")
    for name, expected in sums.items():
        target = (path.parent / name).resolve()
        if not target.is_relative_to(path.parent) or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError("engineering routing evidence changed: " + name)
    catalog = json.loads((path.parent / "MODEL_CATALOG.json").read_text(encoding="utf-8"))
    scores = json.loads((path.parent / "SCORECARD_ALL_MODELS.json").read_text(encoding="utf-8"))
    contracts = []
    for model_id in dict.fromkeys(model_ids):
        chosen = next((item for item in payload.get("contracts", [])
                       if item.get("contract", {}).get("profile", {}).get("model_id") == model_id
                       and item.get("recommended_role") != "INDEPENDENT_AUDITOR_CANDIDATE_NOT_QUALIFIED"), None)
        score = next((item for item in scores if chosen and item["config_id"] == chosen["config_id"]), None)
        if not score or score["R_pass"] != 8 or score["Q_completed"] != 8 or not score["engineering_nonduplicate_valid_pairs"]:
            raise ValueError("generator has no complete engineering comparison: " + model_id)
        entry = next(item for item in catalog if (item.get("model_id") or item.get("id")) == model_id)
        if tested_family(entry, catalog):
            raise ValueError("frozen tested family excluded from engineering generator routing")
        config, candidate = score["parameter_binding"], chosen["contract"]
        parameters = dict(config["parameters"])
        for name in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            if name in parameters:
                parameters[name] = 16384
        if (candidate["parameters"] != parameters or config["model"] != model_id
                or candidate["profile"].get("provider") != "aihubmix"
                or candidate["profile"].get("capabilities") != {"endpoint_family": config["protocol"]}):
            raise ValueError("generator parameters/protocol differ from comparison")
        contracts.append(AuxiliaryContract(ModelProfile("aihubmix", model_id,
            {"endpoint_family": config["protocol"]}, {}, role="GENERATOR"), parameters, entry,
            str(path), ("GENERATOR",), None))
    if not contracts or payload.get("base_url") not in {"https://aihubmix.com/v1", "https://api.inferera.com/v1"}:
        raise ValueError("nonempty verified official engineering route required")
    return catalog, contracts, payload["base_url"]


def qualified_contracts(preflight: Path, *, workspace: Path, role: str, model_ids: Sequence[str],
                        gold: Mapping[str, Path] | None = None,
                        for_tools: bool = False):
    """Load actual successful probes and, for judges, recheck bound fixed-control results."""
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    preflight = Path(preflight).resolve()
    sums = read(preflight / "SHA256SUMS.json")["files"]
    for name, expected in sums.items():
        if digest(preflight / name) != expected:
            raise ValueError("preflight evidence changed: " + name)
    prepared, catalog = read(preflight / "AIHUBMIX_PREFLIGHT.json"), read(preflight / "MODEL_CATALOG.json")
    from ioabench.v5.ai_generation.factory import tested_family
    contracts, endpoints = [], set()
    for model_id in model_ids:
        row = next((item for item in prepared["candidates"] if item.get("requested_model_id") == model_id), None)
        if not row or row.get("live_probe") != "PASS":
            raise ValueError("candidate is not exact-ID preflight qualified: " + model_id)
        entry = next(item for item in catalog if (item.get("model_id") or item.get("id")) == model_id)
        if tested_family(entry, catalog) and role in {"GENERATOR", "JUDGE", "INDEPENDENT_AUDITOR", "CALIBRATOR"}:
            raise ValueError("frozen tested family excluded from auxiliary data selection")
        evidence = Path(row["response_evidence"])
        evidence = evidence if evidence.is_absolute() else workspace / evidence
        response = read(evidence)
        binding = read(evidence.parent / "REQUEST_BINDING.json")
        if (canonical_sha256(binding["binding"]) != binding["sha256"]
                or response["binding_sha256"] != binding["sha256"]
                or canonical_sha256(response["response"]) != response["response_sha256"]
                or (served_catalog_entry(response["response"]["provider_metadata"], catalog) or {}).get("model_id") != model_id):
            raise ValueError("preflight response/binding/identity is invalid")
        schema_name = "schemas/" + model_id + ".json"
        if schema_name not in sums:
            raise ValueError("preflight must bind the exact model schema")
        schema = read(preflight / schema_name)
        parameters = auxiliary_chat_parameters(schema)
        if row["actual_parameters"] != parameters:
            raise ValueError("preflight parameters differ from documented full configuration; run a new preflight")
        bound_contracts = binding["binding"].get("contracts", [])
        if not any(item.get("profile", {}).get("model_id") == model_id
                   and item.get("parameters") == parameters for item in bound_contracts):
            raise ValueError("preflight request does not bind the actual model parameters")
        if for_tools:
            parameters = auxiliary_chat_parameters(schema, for_tools=True)
        gold_evidence = None
        if role in {"JUDGE", "INDEPENDENT_AUDITOR"}:
            gold_directory = (gold or {}).get(model_id)
            if not gold_directory:
                raise ValueError("independent auditor requires fixed controls")
            result = read(gold_directory / "CONTROL_RESULT.json")
            from ioabench.runtime.full_manifest import source_tree_hash
            control_contract = read(gold_directory / "CONTROL_CONTRACT.json")
            parameter_binding = gold_directory / "PARAMETER_BINDING.json"
            if ("PARAMETER_BINDING.json" not in result["evidence_sha256"]
                    or not parameter_binding.is_file()
                    or read(parameter_binding).get("actual_parameters") != parameters):
                raise ValueError("judge controls do not bind the current parameters")
            if control_contract.get("runtime_source_sha256") != source_tree_hash(workspace):
                raise ValueError("judge control runtime source changed; qualify the current version")
            for name, expected in result["evidence_sha256"].items():
                if digest(gold_directory / name) != expected:
                    raise ValueError("judge control evidence changed: " + name)
            from ioabench.v5.ai_generation.judge_controls import CONTROL_VERSION, score_control, summarize_controls
            from ioabench.v5.ai_generation.quality import QUALITY_VERSION
            controls = read(gold_directory / "GOLD_CONTROLS.json")
            if control_contract.get("controls_sha256") != canonical_sha256(controls):
                raise ValueError("judge control input binding changed")
            if any(control.get("version") != CONTROL_VERSION or control["view"].get("review_view_version") != QUALITY_VERSION for control in controls):
                raise ValueError("judge controls predate the active input/factual-evidence contract")
            rows = [score_control(control, read(gold_directory / control["id"] / "REVIEW.json")) for control in controls]
            checked = summarize_controls(rows)
            if (result.get("auditor") != model_id or result.get("status") != "ENGINEERING_CONTROLS_PASS"
                    or not checked["passed"] or checked["gold_count"] != result["gold_count"]
                    or checked["correct"] != result["correct"]):
                raise ValueError("judge fixed controls do not qualify this model")
            gold_evidence = str((gold_directory / "CONTROL_RESULT.json").resolve())
        contracts.append(AuxiliaryContract(ModelProfile("aihubmix", model_id, {}, {}, role=role), parameters,
            entry, str(evidence.resolve()), (role,), gold_evidence))
        endpoints.add(row["endpoint"].removesuffix("/chat/completions"))
    if len(endpoints) != 1 or not contracts:
        raise ValueError("one verified endpoint and nonempty role-qualified pool required")
    return catalog, contracts, endpoints.pop()


def _complete_response(response: ModelResponse, request: ModelRequest) -> None:
    if response.finish_reason == "tool_calls":
        if not request.tools or not response.tool_calls:
            raise ProviderPermanentError("RESPONSE_PARSE: unsolicited or empty tool response")
        for call in response.tool_calls:
            if (not isinstance(call, Mapping) or not isinstance(call.get("id"), str)
                    or not call["id"] or not isinstance(call.get("function"), Mapping)):
                raise ProviderPermanentError("RESPONSE_PARSE: malformed tool-call envelope")
        return
    if response.finish_reason != "stop" or response.tool_calls or not response.text or not response.text.strip():
        raise ProviderPermanentError("RESPONSE_PARSE: empty response or incomplete finish_reason")


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): ("[REDACTED]" if re.search(
            r"authorization|api[_-]?key|bearer|secret|access[_-]?token", str(key), re.I)
            else redact(item)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", value)
        value = re.sub(r"(?i)\bbearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
        return re.sub(r"(?i)([?&](?:key|api_key|token|access_token)=)[^&\s]+", r"\1[REDACTED]", value)
    return value


def _http_status(error: Exception | str) -> int | None:
    if isinstance(getattr(error, "http_status", None), int):
        return error.http_status
    text = str(error)
    # A body length, port, or token count is not evidence of an HTTP response.
    match = re.search(r'"http_status"\s*:\s*"?(\d{3})\b', text)
    if not match:
        match = re.search(r'\bHTTP\s+(\d{3})\b', text, re.I)
    return int(match.group(1)) if match else None


def classify_provider_failure(error: Exception | str) -> str:
    if getattr(error, "category", None):
        return error.category
    text = str(error).casefold()
    status = _http_status(error)
    if isinstance(error, ConfigurationError) or "missing_secret" in text or "api_key is required" in text:
        return "MISSING_SECRET"
    if status in {401, 403} or any(word in text for word in ("unauthorized", "permission denied", "insufficient_user_quota")):
        return "AUTH/PERMISSION"
    if status == 402:
        return "INSUFFICIENT_BALANCE"
    if isinstance(error, ModelUnsupportedError) or any(word in text for word in ("no_available_channel", "no channel", "no route", "retired")):
        return "PROVIDER_UNAVAILABLE"
    if status == 429 or "rate limit" in text:
        return "RATE_LIMIT"
    if "model_id_mismatch" in text:
        return "MODEL_ID_MISMATCH"
    if status == 0 or (status is not None and status >= 500):
        return "NETWORK_TRANSIENT"
    if isinstance(error, json.JSONDecodeError) or any(word in text for word in ("response_parse", "no choices", "response choice", "response message", "non-object", "non-json", "empty response", "truncated")):
        return "RESPONSE_PARSE"
    if status in {400, 422} or "unsupported parameter" in text:
        return "REQUEST_SCHEMA"
    if "science_gate" in text:
        return "SCIENCE_GATE"
    if "model_quality" in text:
        return "MODEL_QUALITY"
    if any(word in text for word in ("timeout", "timed out", "deadline", "connection", "network")):
        return "NETWORK_TRANSIENT"
    if isinstance(error, ProviderTransientError):
        return "NETWORK_TRANSIENT"
    return "UNKNOWN"


class AuxiliaryUnavailable(ProviderPermanentError):
    def __init__(self, message: str, *, category: str | None = None):
        super().__init__(message)
        self.category = category


class RequestUnresolved(ProviderRequestUnresolved):
    """A sent request has no durable response; never send the same paid task again."""


@dataclass(frozen=True)
class AuxiliaryContract:
    profile: ModelProfile
    parameters: Mapping[str, Any]
    entry: Mapping[str, Any]
    preflight_evidence: str
    allowed_roles: Sequence[str] = ("GENERATOR",)
    judge_gold_evidence: str | None = None


def _retry_after(error: Exception, now: float) -> float:
    match = re.search(r'retry-after[\"\s:=>]+([^\"};\n]+)', str(error), re.I)
    if not match:
        return 1.0
    value = match.group(1).strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - now)
        except (ValueError, TypeError):
            return 1.0


def usage_cost(response: ModelResponse, entry: Mapping[str, Any]) -> dict[str, Any]:
    usage, pricing = dict(response.usage), entry.get("pricing") or {}
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion = usage.get("completion_tokens", usage.get("output_tokens"))
    if prompt is None or completion is None or not all(key in pricing for key in ("input", "output")):
        return {"status": "NOT_RETURNED", "currency": "USD", "amount": None}
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    created = int(usage.get("cache_creation_input_tokens") or 0)
    amount = ((int(prompt) - int(cached) - created) * float(pricing["input"])
              + int(cached) * float(pricing.get("cache_read", pricing["input"]))
              + int(completion) * float(pricing["output"])) / 1_000_000
    if created and "cache_write" not in pricing:
        return {"status": "PARTIAL_CACHE_CREATION_RATE_UNKNOWN", "currency": "USD", "amount": None,
                "known_subtotal": amount, "unknown_cache_creation_tokens": created}
    amount += created * float(pricing.get("cache_write", 0)) / 1_000_000
    return {"status": "ESTIMATED", "currency": "USD", "amount": amount,
            "basis": "live catalog token rates; excludes unreturned usage, tiered pricing and discounts"}


class AuxiliaryRouter:
    def __init__(self, port: ModelPort, contracts: Sequence[AuxiliaryContract], catalog,
                 directory: Path, *, max_attempts_per_model: int = 2,
                 cooldown_seconds: float = 300, sleep=asyncio.sleep, now=time.time) -> None:
        if max_attempts_per_model not in {1, 2, 3} or cooldown_seconds <= 0:
            raise ValueError("bounded attempts (1..3) and positive cooldown are required")
        if getattr(port, "stop_on_provider_error", True) is False:
            raise ValueError("router requires adapter retries disabled to count every paid attempt")
        self.port, self.contracts, self.catalog = port, tuple(contracts), list(catalog)
        providers = {item.profile.provider for item in contracts} or {"aihubmix"}
        if len(providers) != 1 or not providers <= {"aihubmix", "deepseek"}:
            raise ValueError("one supported provider per auxiliary ledger required")
        self.provider_prefix = next(iter(providers)).upper()
        self.directory, self.max_attempts = Path(directory), max_attempts_per_model
        self.cooldown, self.sleep, self.now = cooldown_seconds, sleep, now
        self.directory.mkdir(parents=True, exist_ok=True)
        state_path = self.directory / (self.provider_prefix + "_ROUTING_STATE.json")
        self.state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"circuits": {}, "auth_blocked": False}
        self._busy = False
        self.verify_ledger()

    def verify_ledger(self):
        # Historical read-only verifiers pass a directory-only namespace, without a router.
        prefix = getattr(self, "provider_prefix", "AIHUBMIX")
        path, previous = self.directory / (prefix + "_ATTEMPTS.jsonl"), ""
        for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
            row = json.loads(line)
            digest = row.pop("event_sha256")
            if row["previous_event_sha256"] != previous or canonical_sha256(row) != digest:
                raise ValueError("auxiliary attempt ledger integrity failed")
            previous = digest

    def _save(self):
        atomic_json(self.directory / (self.provider_prefix + "_ROUTING_STATE.json"), self.state)

    def _event(self, **row):
        path = self.directory / (self.provider_prefix + "_ATTEMPTS.jsonl")
        previous = ""
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            previous = json.loads(lines[-1])["event_sha256"] if lines else ""
        row = redact({"at_utc": datetime.fromtimestamp(self.now(), timezone.utc).isoformat(),
                      "routing_version": ROUTING_VERSION, "previous_event_sha256": previous, **row})
        row["event_sha256"] = canonical_sha256(row)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _open(self, model_id: str, category: str):
        self.state["circuits"][model_id] = {"category": category, "recover_after_epoch": self.now() + self.cooldown,
                                                "recovery": "new successful preflight required"}
        self._save()

    def restore(self, model_id: str, *, preflight_evidence: str, judge_gold_evidence: str | None = None):
        if not preflight_evidence:
            raise ValueError("fresh preflight evidence is required")
        contract = next(item for item in self.contracts if item.profile.model_id == model_id)
        if any(role in contract.allowed_roles for role in ("JUDGE", "INDEPENDENT_AUDITOR")) and not judge_gold_evidence:
            raise ValueError("judge recovery requires fresh gold controls")
        self.state["circuits"].pop(model_id, None)
        self._event(event="CIRCUIT_RESTORED", model_id=model_id, preflight_evidence=preflight_evidence,
                    judge_gold_evidence=judge_gold_evidence)
        self._save()

    async def invoke(self, role: str, request_id: str, request: ModelRequest, *,
                     generator_developer_id: str | int | None = None,
                     validate: Callable[[ModelResponse], None] | None = None) -> ModelResponse:
        if role not in {"GENERATOR", "JUDGE", "INDEPENDENT_AUDITOR", "CALIBRATOR", "AUX_PROTOCOL_PROBE",
                        "DEVELOPMENT_EXPLORATORY_SAME_FAMILY", "DEV_GENERATOR", "DEV_AUDITOR", "DEV_REPAIR_PROPOSER",
                        "DEVELOPMENT_AUTO_AUDITED", "TREE_FACTORY"}:
            raise ValueError("frozen SUT/formal roles are excluded from auxiliary routing")
        safe_id(request_id)
        if self._busy:
            raise RuntimeError("one auxiliary request per router at a time")
        self._busy = True
        try:
            with writer_lock(self.directory):
                return await self._invoke(role, request_id, request, generator_developer_id, validate)
        finally:
            self._busy = False

    async def _invoke(self, role, request_id, request, generator_developer_id, validate):
        request_directory = self.directory / request_id
        request_directory.mkdir(exist_ok=True)
        binding = {"role": role, "request": asdict(request), "generator_developer_id": generator_developer_id,
                   "contracts": [asdict(item) for item in self.contracts]}
        binding_hash = canonical_sha256(binding)
        binding_path = request_directory / "REQUEST_BINDING.json"
        if binding_path.exists() and json.loads(binding_path.read_text(encoding="utf-8"))["sha256"] != binding_hash:
            raise ValueError("immutable auxiliary request/model policy changed")
        if not binding_path.exists():
            atomic_json(binding_path, {"sha256": binding_hash, "binding": redact(binding)})
        response_path = request_directory / "RESPONSE.json"
        if response_path.exists():
            saved = json.loads(response_path.read_text(encoding="utf-8"))
            if (saved["binding_sha256"] != binding_hash
                    or canonical_sha256(saved["response"]) != saved["response_sha256"]):
                raise ValueError("response binding changed")
            response = ModelResponse(**{**saved["response"], "tool_calls": tuple(saved["response"].get("tool_calls", ()))})
            _complete_response(response, request)
            if validate:
                validate(response)
            return response
        attempts = sorted(request_directory.glob("attempt-*.json"))
        if attempts:
            # Every invocation is a request boundary; failed terminal tasks need a new id too.
            raise RequestUnresolved("REQUEST_UNRESOLVED: no durable task response; use retained attempt evidence before a new task")
        if self.state["auth_blocked"]:
            raise AuxiliaryUnavailable("AUTH/PERMISSION: credential is blocked for this run")
        last_error = None
        for contract in self.contracts:
            model_id = contract.profile.model_id
            if role not in contract.allowed_roles or not contract.preflight_evidence or model_id in self.state["circuits"]:
                continue
            generator_ids = generator_developer_id if isinstance(generator_developer_id, (list, tuple, set)) else [generator_developer_id]
            if role in {"JUDGE", "INDEPENDENT_AUDITOR"} and (
                    not contract.judge_gold_evidence or generator_developer_id is None
                    or str(contract.entry.get("developer_id")) in {str(item) for item in generator_ids}):
                continue
            for ordinal in range(1, self.max_attempts + 1):
                attempt_id = f"{request_id}-{model_id}-{ordinal}"
                path = request_directory / f"attempt-{len(list(request_directory.glob('attempt-*.json'))) + 1:03d}.json"
                wire_request = replace(request, parameters=dict(contract.parameters),
                                       role_metadata={**request.role_metadata, "role": role, "attempt_id": attempt_id,
                                                      "stream_evidence_path": str(path.with_suffix('.sse'))})
                profile = replace(contract.profile, role=role)
                started = self.now()
                record = {"attempt_id": attempt_id, "request_id": request_id, "role": role,
                          "requested_model_id": model_id, "actual_parameters": dict(contract.parameters),
                          "wire_request_format": WIRE_REQUEST_FORMAT,
                          "stream_evidence_path": str(path.with_suffix('.sse')),
                          "request_sha256": canonical_sha256(asdict(wire_request)), "status": "REQUEST_STARTED"}
                atomic_json(path, redact(record))
                self._event(event="REQUEST_STARTED", **record)
                try:
                    response = await self.port.generate(profile, wire_request)
                    served = served_catalog_entry(response.provider_metadata, self.catalog)
                    record.update(response=asdict(response), served_model_id=(served or {}).get("model_id") or (served or {}).get("id"),
                                  usage=dict(response.usage), cost=usage_cost(response, contract.entry))
                    if not served or str(served.get("model_id") or served.get("id")) != model_id:
                        raise ProviderPermanentError("MODEL_ID_MISMATCH: requested and served catalog identities differ")
                    _complete_response(response, wire_request)
                    if validate:
                        validate(response)
                    record.update(status="SUCCEEDED", elapsed_seconds=self.now() - started)
                    atomic_json(path, redact(record))
                    self._event(event="REQUEST_FINISHED", **record)
                    self.state["circuits"].pop(model_id, None)
                    self._save()
                    saved_response = redact(asdict(response))
                    atomic_json(response_path, {"binding_sha256": binding_hash, "response": saved_response,
                                               "response_sha256": canonical_sha256(saved_response)})
                    return response
                except Exception as exc:
                    category = classify_provider_failure(exc)
                    last_error = exc
                    ambiguous = category == "REQUEST_UNRESOLVED" or (category == "NETWORK_TRANSIENT" and not _http_status(exc))
                    record.update(status="REQUEST_UNRESOLVED" if ambiguous else "FAILED", category=category,
                                  error_type=type(exc).__name__, error=redact(str(exc)), elapsed_seconds=self.now() - started,
                                  transport_metadata=redact(getattr(exc, "transport_metadata", {})))
                    atomic_json(path, redact(record))
                    self._event(event="REQUEST_FINISHED", **record)
                    if category in {"AUTH/PERMISSION", "MISSING_SECRET", "INSUFFICIENT_BALANCE"}:
                        self.state["auth_blocked"] = True
                        self._save()
                        raise
                    if category in {"MODEL_QUALITY", "SCIENCE_GATE", "UNKNOWN", "RESPONSE_PARSE",
                                    "REQUEST_SCHEMA", "MODEL_ID_MISMATCH"}:
                        raise
                    self._open(model_id, category)
                    if ambiguous:
                        unresolved = RequestUnresolved("REQUEST_UNRESOLVED: sent request lacks a response; no duplicate request or model failover for this task")
                        unresolved.transport_metadata = record["transport_metadata"]
                        raise unresolved from exc
                    delay = _retry_after(exc, self.now()) if category == "RATE_LIMIT" else 1.0
                    if category in {"RATE_LIMIT", "NETWORK_TRANSIENT"} and ordinal < self.max_attempts and delay <= 60:
                        await self.sleep(delay)
                        continue
                    self._event(event="MODEL_FAILOVER", request_id=request_id, from_model_id=model_id,
                                reason=category, next_action="next preflight-qualified independent candidate at request boundary")
                    break
        category = classify_provider_failure(last_error) if last_error else "NO_QUALIFIED_MODEL"
        raise AuxiliaryUnavailable(f"all role-qualified candidates unavailable; last category={category}", category=category)
