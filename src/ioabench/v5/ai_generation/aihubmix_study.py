"""AIHubMix development channel for deepseek-v4.1-flash-1017 (DEVELOPMENT_AUTO_AUDITED).

Mirrors the official-DirectStudy contract (durable ledger, one attempt per unique
request, global stop on unknown/auth/balance, immutable evidence) with the
AIHubMix gateway identity, USD budget stops from the frozen pilot config, and
study-provided audit parameters so protocol-1.2 audits run on this provider too.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract, AuxiliaryRouter, RequestUnresolved, classify_provider_failure, redact
from ioabench.models import ModelProfile, ModelRequest
from ioabench.models.aihubmix import DEFAULT_BASE_URL
from ioabench.v5.evaluation import atomic_json

PROVIDER = "aihubmix"
MODEL = "deepseek-v4.1-flash-1017"
BASE_URL = DEFAULT_BASE_URL
SCOPE = "DEVELOPMENT_AUTO_AUDITED"
STUDY_VERSION = "ioabench.v5.aihubmix-tree-study/1.1.0"
# R2 (2026-10-24): the user explicitly authorized unlimited paid usage for this
# round — the frozen R1 USD stops (5 soft / 20 hard) are NO LONGER request gates.
# Usage and worst-case cost bounds are still recorded on every receipt; the R1
# STOP.json/ledger keeps its original meaning and is never rewritten.
BUDGET_GATE_ENABLED = False
SOFT_SPEND_USD = 5.0
HARD_SPEND_USD = 20.0
# Quality-first output profile (03_AIHubMix_QualityFirst.yaml): base 131072,
# complex 262144, ceiling 393216 only after a live parameter probe accepts it.
OUTPUT_PROFILE = {"base_max_tokens": 131072, "complex_max_tokens": 262144,
                  "ceiling_max_tokens": 393216, "effort_default": "high",
                  "effort_complex": "max"}
# No published unit price is bound to this key; bound every request with a
# conservative deepseek-class worst case until a real usage-derived bound exists.
WORST_CASE_USD_PER_MTOK = (2.0, 8.0)
STOP_CATEGORIES = {"REQUEST_UNRESOLVED", "UNKNOWN", "AUTH/PERMISSION",
                   "INSUFFICIENT_BALANCE", "MISSING_SECRET"}


def parameters(effort: str = "high", *, max_tokens: int = 131072, tools: bool = False):
    if effort not in {"disabled", "low", "high", "max"}:
        raise ValueError("effort must be disabled/low/high/max")
    result = {"thinking": {"type": "disabled" if effort == "disabled" else "enabled"},
              "max_tokens": max_tokens,
              # streaming keeps long thinking turns alive past the gateway's
              # ~80-100s non-streaming cutoff; the adapter aggregates SSE chunks
              "stream": not tools}
    if effort != "disabled":
        result["reasoning_effort"] = effort
    if not tools:
        result["response_format"] = {"type": "json_object"}
    return result


def cost_bound(usage) -> dict:
    """Worst-case USD bound from reported usage; missing usage stays UNKNOWN."""
    prompt, output = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if prompt is None or output is None:
        return {"status": "UNKNOWN", "currency": "USD", "amount": None,
                "actual_invoice": "UNKNOWN"}
    upper = (prompt * WORST_CASE_USD_PER_MTOK[0] + output * WORST_CASE_USD_PER_MTOK[1]) / 1_000_000
    return {"status": "WORST_CASE_BOUND", "currency": "USD", "lower_usd": 0.0,
            "upper_usd": round(upper, 6), "actual_invoice": "UNKNOWN"}


def budget_reserve(params, messages=None) -> float:
    ceiling = (params or {}).get("max_tokens", 65536)
    if type(ceiling) is not int or ceiling <= 0:
        raise ValueError("budget output ceiling must be a positive integer")
    # measure the actual pending prompt (chars/3 overestimates tokens for this mix)
    if messages is not None:
        input_tokens = len(json.dumps(list(messages), ensure_ascii=False)) // 3
    else:
        input_tokens = 200_000
    # worst-case output plus the measured input at the worst-case unit price
    return (input_tokens * WORST_CASE_USD_PER_MTOK[0] + ceiling * WORST_CASE_USD_PER_MTOK[1]) / 1_000_000


def immutable(path: Path, value) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("immutable evidence changed: " + str(path))
    else:
        atomic_json(path, value)


class AihubmixStudy:
    """One AIHubMix model, no retry/failover, durable stop, USD budget stops."""

    def __init__(self, out: Path, port, catalog):
        self.out, self.port, self.catalog = Path(out), port, list(catalog)
        if getattr(port, "base_url", BASE_URL) != BASE_URL:
            raise ValueError("the frozen AIHubMix gateway endpoint is required")
        entry = next((item for item in self.catalog
                      if (item.get("id") or item.get("model_id")) == MODEL), None)
        if entry is None:
            raise ValueError("exact AIHubMix model not discovered in the authenticated catalog")
        self.catalog_entry = entry
        self.stop = self.out / "STOP.json"

    # audit_packet consumes these study hooks (protocol 1.2 audits on this provider)
    audit_parameters = staticmethod(parameters)
    audit_served_model = MODEL

    def ledger(self, event, **details):
        path = self.out / "REQUEST_LEDGER.jsonl"
        previous = ""
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])["event_sha256"]
        row = redact({"event": event, "at_utc": datetime.now(timezone.utc).isoformat(),
                      "provider": PROVIDER, "model": MODEL,
                      "previous_event_sha256": previous, **details})
        row["event_sha256"] = canonical_sha256(row)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def ledger_rows(self):
        path = self.out / "REQUEST_LEDGER.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def check_budget(self, pending_parameters, messages=None):
        """R2: usage observability only. The USD stops are disabled by explicit
        user authorization for this round (BUDGET_GATE_ENABLED); costs remain
        recorded on every receipt and are never a request-refusal condition."""
        known = 0.0
        for row in self.ledger_rows():
            if row.get("event") not in {"REQUEST_FINISHED", "REQUEST_RECONCILED"}:
                continue
            bound = (row.get("cost") or {}).get("upper_usd", row.get("budget_reserve_usd"))
            if isinstance(bound, bool) or not isinstance(bound, (int, float)) or not math.isfinite(bound) or bound < 0:
                bound = budget_reserve(row.get("parameters"))
            known += bound
        reserve = budget_reserve(pending_parameters, messages)
        atomic_json(self.out / "SPEND_OBSERVABILITY.json",
                    {"version": STUDY_VERSION, "budget_gate_enabled": BUDGET_GATE_ENABLED,
                     "known_upper_usd": round(known, 6),
                     "pending_reserve_usd": round(reserve, 6), "actual_invoice": "UNKNOWN",
                     "note": "no request is refused on cost in R2; user-authorized"})
        if BUDGET_GATE_ENABLED and known + reserve > HARD_SPEND_USD:
            immutable(self.stop, {"category": "BUDGET_HARD_STOP", "upper_usd": known,
                                  "reserve_usd": reserve, "hard_limit_usd": HARD_SPEND_USD})
            raise ValueError("hard budget stop")
        if BUDGET_GATE_ENABLED and known >= SOFT_SPEND_USD \
                and not (self.out / "BUDGET_SOFT_NOTICE.json").exists():
            immutable(self.out / "BUDGET_SOFT_NOTICE.json",
                      {"upper_usd": known, "soft_usd": SOFT_SPEND_USD})

    async def invoke(self, directory, request_id, messages, params, *, tools=(), role=SCOPE):
        directory = Path(directory)
        if self.stop.exists():
            raise ValueError("run is stopped; inspect STOP.json, do not resend")
        if role not in {SCOPE, "DEV_GENERATOR", "DEV_AUDITOR", "DEV_REPAIR_PROPOSER", "TREE_FACTORY"}:
            raise ValueError("unsupported development request role")
        intent = {"request_id": request_id,
                  "directory": directory.relative_to(self.out).as_posix(),
                  "parameters": params,
                  "messages_sha256": canonical_sha256(messages),
                  "tools_sha256": canonical_sha256(list(tools))}
        retained = [row for row in self.ledger_rows() if row.get("event") == "REQUEST_INTENT"
                    and row.get("directory") == intent["directory"]
                    and row.get("request_id") == request_id]
        if len(retained) > 1 or (retained and any(
                canonical_sha256(retained[0].get(key)) != canonical_sha256(value)
                for key, value in intent.items())):
            raise ValueError("immutable request intent changed or is not unique; preserve evidence")
        cached = (directory / request_id / "RESPONSE.json").exists()
        attempts = list((directory / request_id).glob("attempt-*.json"))
        if retained and not cached and not attempts:
            raise RequestUnresolved("REQUEST_UNRESOLVED: retained intent has no durable terminal; never resend")
        if not cached and not attempts:
            self.check_budget(params, messages)
            if not retained:
                self.ledger("REQUEST_INTENT", **intent)
        try:
            from dataclasses import asdict
            from ioabench.models.types import ModelResponse
            cached_path = directory / request_id / "RESPONSE.json"
            fresh = not cached_path.exists()
            if cached_path.exists():
                saved = json.loads(cached_path.read_text(encoding="utf-8"))
                # the router persists a {binding_sha256, response} wrapper
                saved = saved.get("response", saved)
                response = ModelResponse(text=saved.get("text"), model_id=saved.get("model_id", MODEL),
                                         finish_reason=saved.get("finish_reason"),
                                         usage=saved.get("usage") or {},
                                         provider_metadata=saved.get("provider_metadata") or {},
                                         tool_calls=saved.get("tool_calls") or (),
                                         reasoning_content=saved.get("reasoning_content"))
                fresh = False
            else:
                contract = AuxiliaryContract(
                    ModelProfile(PROVIDER, MODEL, {}, {}, role=role), params,
                    {"id": MODEL, "model_id": MODEL,
                     "developer_id": self.catalog_entry.get("developer_id") or "deepseek",
                     "owned_by": self.catalog_entry.get("owned_by") or "deepseek"},
                    str(self.out / "MODEL_CATALOG.json"), (role, "AUX_PROTOCOL_PROBE"))
                router = AuxiliaryRouter(self.port, [contract], self.catalog, directory,
                                         max_attempts_per_model=1)
                role_metadata = {"scope": SCOPE}
                if role != SCOPE:
                    role_metadata["role"] = role
                request = ModelRequest(tuple(messages), {}, tools=tuple(tools),
                                       role_metadata=role_metadata)
                response = await router.invoke(role, request_id, request)
            # the authoritative gateway routing header wins; the body carries the
            # underlying deployment id (project routing convention since v1.2)
            transport = response.provider_metadata.get("transport_metadata") or {}
            header_model = transport.get("x-aihubmix-model")
            served = response.provider_metadata.get("model")
            if not (header_model == MODEL or served == MODEL):
                raise ValueError(f"served identity {served!r}/header {header_model!r} "
                                 f"is not the frozen {MODEL}")
            if fresh:
                payload = asdict(response)
                self.ledger("REQUEST_FINISHED", request_id=request_id,
                            directory=intent["directory"], status="PASS",
                            usage=dict(payload.get("usage") or {}), cost=cost_bound(payload.get("usage") or {}),
                            budget_reserve_usd=budget_reserve(params),
                            served_model_id=served, gateway_header_model=header_model,
                            response_sha256=canonical_sha256(payload),
                            transport=transport)
            return response
        except Exception as exc:
            category = classify_provider_failure(exc)
            self.ledger("REQUEST_FAILED", request_id=request_id, category=category,
                        directory=intent["directory"], error=redact(str(exc)),
                        cost={"status": "UNKNOWN", "currency": "USD", "amount": None,
                              "actual_invoice": "UNKNOWN"},
                        transport=getattr(exc, "transport_metadata", {}))
            if category in STOP_CATEGORIES:
                immutable(self.stop, {"category": category, "request_id": request_id,
                                      "at_utc": datetime.now(timezone.utc).isoformat(),
                                      "action": "STOP_AND_PRESERVE_NO_RESEND"})
            raise
