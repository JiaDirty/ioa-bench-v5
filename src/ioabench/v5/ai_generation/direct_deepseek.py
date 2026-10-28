"""Official DeepSeek development calls through ModelPort and the shared no-resend router."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict
from dataclasses import replace
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelRequest
from ioabench.v5.ai_generation.auxiliary_runtime import (
    AuxiliaryContract, AuxiliaryRouter, classify_provider_failure, redact,
)
from ioabench.v5.ai_generation.acquisition import staged_proposal
from ioabench.v5.ai_generation.factory import decode_json, engineering_checks, event, reference_findings
from ioabench.v5.ai_generation.history import classify as classify_history
from ioabench.v5.ai_generation.pipeline import CandidateRejected, suite_spec
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.evaluation import atomic_json
from ioabench.v5.replay import replay_case
from ioabench.runtime.full_manifest import source_tree_hash

VERSION = "ioabench.v5.deepseek-exploratory-g2/1.0.1"
SCOPE = "DEVELOPMENT_EXPLORATORY_SAME_FAMILY"
MODEL = "deepseek-flash"
STAGE_BUDGET = {"task_design": 16384, "world_graph": 32768,
                "risk_placement": 32768, "surface_artifacts": 16384}


def parameters(effort="high", *, max_tokens=4096, tools=False):
    if effort not in {"disabled", "low", "high", "max"}:
        raise ValueError("distinct official efforts are disabled/low/high/max")
    result = {"thinking": {"type": "disabled" if effort == "disabled" else "enabled"},
              "max_tokens": max_tokens, "stream": False}
    if effort != "disabled":
        result["reasoning_effort"] = effort
    if not tools:
        result["response_format"] = {"type": "json_object"}
    return result


def cost_estimate(usage):
    """Peak/off-peak bounds; missing cache fields are unknown, never assumed hits."""
    prompt, output = usage.get("prompt_tokens"), usage.get("completion_tokens")
    hit, miss = usage.get("prompt_cache_hit_tokens"), usage.get("prompt_cache_miss_tokens")
    if hit is None:
        details = usage.get("prompt_tokens_details") or {}
        if not isinstance(details, Mapping):
            raise ValueError("invalid token usage accounting")
        hit = details.get("cached_tokens")
    if any(value is not None and (type(value) is not int or value < 0) for value in (prompt, output, hit, miss)):
        raise ValueError("token usage must be nonnegative integers")
    if prompt is None or output is None:
        return {"status": "UNKNOWN", "currency": "CNY", "amount": None, "actual_invoice": "UNKNOWN"}
    if miss is not None and miss > prompt:
        raise ValueError("invalid cache usage accounting")
    if hit is None:
        lower, upper = (prompt * .02 + output * 4), (prompt * 2 + output * 8)
        status = "CACHE_UNKNOWN_BOUND"
    else:
        if not 0 <= hit <= prompt or (miss is not None and hit + miss != prompt):
            raise ValueError("invalid cache usage accounting")
        upper = hit * .04 + (prompt - hit) * 2 + output * 8
        lower, status = upper / 2, "ESTIMATE_PEAK_OFFPEAK_BOUND"
    return {"status": status, "currency": "CNY", "amount": None,
            "lower_cny": lower / 1_000_000, "upper_cny": upper / 1_000_000,
            "actual_invoice": "UNKNOWN", "cache_hit_tokens": hit,
            "basis": "official 2026-10-20 rates; both time tariffs retained, holiday/billing not inferred"}


def budget_reserve(parameters):
    ceiling = (parameters or {}).get("max_tokens", 1_048_576)
    if type(ceiling) is not int or ceiling <= 0:
        raise ValueError("budget output ceiling must be a positive integer")
    return (ceiling * 8 + 1_048_576 * 2) / 1_000_000


def immutable(path, value):
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("immutable evidence changed: " + str(path))
    else:
        atomic_json(path, value)


class DirectStudy:
    """One provider, no retry/failover, global durable stop on unknown/auth/balance."""

    def __init__(self, out: Path, port, catalog):
        self.out, self.port, self.catalog = Path(out), port, list(catalog)
        if port.base_url != "https://api.deepseek.com":
            raise ValueError("official direct endpoint required")
        if not any(item.get("id") == MODEL for item in catalog):
            raise ValueError("exact official model not discovered")
        self.stop = self.out / "STOP.json"

    def ledger(self, event, **details):
        path = self.out / "REQUEST_LEDGER.jsonl"
        previous = ""
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])["event_sha256"]
        row = redact({"event": event, "at_utc": datetime.now(timezone.utc).isoformat(),
                      "provider": "deepseek", "previous_event_sha256": previous, **details})
        row["event_sha256"] = canonical_sha256(row)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def ledger_rows(self):
        path = self.out / "REQUEST_LEDGER.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def reconcile_receipts(self):
        """Account durable responses even when completion/ledger writing was interrupted."""
        rows = self.ledger_rows()
        accounted = {(row.get("directory"), row["request_id"]) for row in rows
                     if row["event"] == "REQUEST_FINISHED"}
        for intent in rows:
            key = (intent.get("directory"), intent.get("request_id"))
            if intent["event"] != "REQUEST_INTENT" or key in accounted:
                continue
            request_directory = (self.out / key[0] / key[1]).resolve()
            if not request_directory.is_relative_to(self.out.resolve()):
                raise ValueError("receipt path escapes study")
            response_path = request_directory / "RESPONSE.json"
            if response_path.exists():
                saved = json.loads(response_path.read_text(encoding="utf-8"))
                binding = json.loads((request_directory / "REQUEST_BINDING.json").read_text(encoding="utf-8"))
                if (saved["binding_sha256"] != binding["sha256"]
                        or canonical_sha256(saved["response"]) != saved["response_sha256"]):
                    raise ValueError("durable accounting response binding changed")
                response, status, category, receipt = saved["response"], "PASS", None, response_path
            else:
                attempts = sorted(request_directory.glob("attempt-*.json"))
                complete = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in attempts]
                complete = [(path, record) for path, record in complete if isinstance(record.get("response"), dict)]
                if not complete:
                    continue
                if len(complete) != 1:
                    raise ValueError("direct accounting requires one non-retried response receipt")
                receipt, record = complete[0]
                response, status, category = record["response"], "FAILED_WITH_RESPONSE", record.get("category")
            usage = response.get("usage") or {}
            served = (response.get("provider_metadata") or {}).get("model") or response.get("model_id")
            try:
                cost = cost_estimate(usage) if served == MODEL else {"status": "UNKNOWN", "currency": "CNY", "amount": None}
            except (TypeError, ValueError):
                cost = {"status": "UNKNOWN", "currency": "CNY", "amount": None, "reason": "INVALID_USAGE"}
            cost.setdefault("actual_invoice", "UNKNOWN")
            details = {"directory": key[0], "request_id": key[1], "status": status,
                "category": category, "usage": usage, "cost": cost, "served_model_id": served,
                "finish_reason": response.get("finish_reason"), "response_sha256": canonical_sha256(response),
                "transport": (response.get("provider_metadata") or {}).get("_transport", {}),
                "accounting_source": "RECOVERED_DURABLE_RESPONSE" if response_path.exists() else "DURABLE_FAILED_RESPONSE",
                "receipt_path": receipt.relative_to(self.out.resolve()).as_posix(), "receipt_sha256": _sha(receipt)}
            if "upper_cny" not in cost:
                # A budget reservation is not an estimated charge or a provider invoice.
                details["budget_reserve_cny"] = budget_reserve(intent.get("parameters"))
            self.ledger("REQUEST_FINISHED", **details)
            accounted.add(key)

    def check_budget(self, pending_parameters):
        self.reconcile_receipts()
        rows = self.ledger_rows()
        intents = {(row.get("directory"), row["request_id"]): row for row in rows if row["event"] == "REQUEST_INTENT"}
        known = 0
        for row in rows:
            if row["event"] != "REQUEST_FINISHED":
                continue
            bound = (row.get("cost") or {}).get("upper_cny", row.get("budget_reserve_cny"))
            if isinstance(bound, bool) or not isinstance(bound, (int, float)) or not math.isfinite(bound) or bound < 0:
                bound = budget_reserve(intents.get((row.get("directory"), row["request_id"]), {}).get("parameters"))
            known += bound
        # Reserve the full output ceiling plus a conservative 1M-token input before a send.
        reserve = budget_reserve(pending_parameters)
        if known + reserve > 200:
            immutable(self.stop, {"category": "BUDGET_HARD_STOP", "upper_cny": known, "reserve": reserve})
            raise ValueError("hard budget stop")
        if known >= 50 and not (self.out / "BUDGET_SOFT_NOTICE.json").exists():
            immutable(self.out / "BUDGET_SOFT_NOTICE.json", {"upper_cny": known, "soft_cny": 50})

    async def invoke(self, directory, request_id, messages, params, *, tools=(), role=SCOPE):
        directory = Path(directory)
        if self.stop.exists():
            raise ValueError("run is stopped; inspect STOP.json, do not resend")
        if role not in {SCOPE, "DEV_GENERATOR", "DEV_AUDITOR", "DEV_REPAIR_PROPOSER"}:
            raise ValueError("unsupported development request role")
        intent = {"request_id": request_id, "directory": directory.relative_to(self.out).as_posix(),
            "parameters": params, "messages_sha256": canonical_sha256(messages), "tools_sha256": canonical_sha256(tools)}
        retained_intents = [row for row in self.ledger_rows() if row["event"] == "REQUEST_INTENT"
            and row.get("directory") == intent["directory"] and row.get("request_id") == request_id]
        if len(retained_intents) > 1 or (retained_intents and any(
                canonical_sha256(retained_intents[0].get(key)) != canonical_sha256(value) for key, value in intent.items())):
            raise ValueError("immutable request intent changed or is not unique; preserve evidence")
        self.reconcile_receipts()
        contract = AuxiliaryContract(ModelProfile("deepseek", MODEL, {}, {}, role=role), params,
            {"id": MODEL, "model_id": MODEL, "developer_id": "deepseek", "owned_by": "deepseek"},
            str(self.out / "MODEL_CATALOG.json"), (role, "AUX_PROTOCOL_PROBE"))
        router = AuxiliaryRouter(self.port, [contract], self.catalog, directory, max_attempts_per_model=1)
        role_metadata = {"scope": SCOPE}
        if role != SCOPE:
            role_metadata["role"] = role
        request = ModelRequest(tuple(messages), {}, tools=tuple(tools), role_metadata=role_metadata)
        cached = (directory / request_id / "RESPONSE.json").exists()
        existing_attempts = list((directory / request_id).glob("attempt-*.json"))
        if not cached and not existing_attempts:
            self.check_budget(params)
            if not retained_intents:
                self.ledger("REQUEST_INTENT", **intent)
        try:
            response = await router.invoke(role, request_id, request)
            if not cached:
                cost = cost_estimate(response.usage)
                self.ledger("REQUEST_FINISHED", request_id=request_id,
                    directory=directory.relative_to(self.out).as_posix(), status="PASS", usage=dict(response.usage),
                    cost=cost, **({"budget_reserve_cny": budget_reserve(params)} if "upper_cny" not in cost else {}),
                    response_sha256=canonical_sha256(asdict(response)),
                    transport=response.provider_metadata.get("_transport", {}))
            return response
        except Exception as exc:
            category = classify_provider_failure(exc)
            self.reconcile_receipts()
            self.ledger("REQUEST_FAILED", request_id=request_id, category=category,
                directory=directory.relative_to(self.out).as_posix(), error=redact(str(exc)),
                cost={"status": "UNKNOWN", "currency": "CNY", "amount": None, "actual_invoice": "UNKNOWN"},
                transport=getattr(exc, "transport_metadata", {}))
            if category in {"REQUEST_UNRESOLVED", "UNKNOWN", "AUTH/PERMISSION", "INSUFFICIENT_BALANCE", "MISSING_SECRET"}:
                immutable(self.stop, {"category": category, "request_id": request_id,
                    "at_utc": datetime.now(timezone.utc).isoformat(), "action": "STOP_AND_PRESERVE_NO_RESEND"})
            raise


async def probe(study):
    directory = study.out / "probes"
    nonce = study.out.name
    results = []
    for effort in ("high", "disabled"):
        response = await study.invoke(directory / effort, "json-receipt", [{"role": "user", "content":
            'Return only JSON exactly like {"receipt":"' + nonce + '","value":7} with those exact values.'}], parameters(effort))
        passed = decode_json(response.text) == {"receipt": nonce, "value": 7}
        if not passed:
            raise ValueError("MODEL_QUALITY: receipt content mismatch")
        results.append({"test": effort + "-json", "status": "PASS", "served_id": response.provider_metadata.get("model"),
                        "finish_reason": response.finish_reason, "usage": dict(response.usage)})
        immutable(study.out / "PROBE_PROGRESS.json", results) if effort == "high" else None
    tool = {"type": "function", "function": {"name": "echo_receipt", "description": "Return a local synthetic receipt.",
        "parameters": {"type": "object", "properties": {"value": {"type": "integer"}},
                       "required": ["value"], "additionalProperties": False}}}
    messages = [{"role": "user", "content": 'Call echo_receipt exactly once with value 7. Then output JSON {"value":7,"verified":true} from its result. Receipt: ' + nonce}]
    response = await study.invoke(directory / "tools", "tool-turn", messages, parameters("high", tools=True), tools=(tool,))
    if response.finish_reason != "tool_calls" or len(response.tool_calls) != 1 or not isinstance(response.reasoning_content, str):
        raise ValueError("TOOL_PROTOCOL: missing single tool call or reasoning_content")
    call = response.tool_calls[0]
    if call["function"]["name"] != "echo_receipt" or decode_json(call["function"]["arguments"]) != {"value": 7}:
        raise ValueError("TOOL_PROTOCOL: wrong function arguments")
    messages += [{"role": "assistant", "content": response.text or "", "tool_calls": list(response.tool_calls),
                  "reasoning_content": response.reasoning_content},
                 {"role": "tool", "tool_call_id": call["id"], "content": '{"value":7,"verified":true}'}]
    final = await study.invoke(directory / "tools", "tool-result", messages, parameters("high", tools=True), tools=(tool,))
    try:
        valid = decode_json(final.text) == {"value": 7, "verified": True}
    except ValueError:
        valid = False
    if not valid:
        results.append({"test": "tool-final-without-json-mode", "status": "FAIL",
                        "reason": "complete response did not satisfy strict JSON; retained, never overwritten"})
        messages += [{"role": "assistant", "content": final.text or "", "reasoning_content": final.reasoning_content or ""},
                     {"role": "user", "content": 'Formatting task v1: output only json {"value":7,"verified":true}; no prose or markdown.'}]
        params = {**parameters("high", tools=True), "response_format": {"type": "json_object"}}
        final = await study.invoke(directory / "tools", "tool-json-format-v1", messages, params, tools=(tool,))
        if decode_json(final.text) != {"value": 7, "verified": True}:
            raise ValueError("TOOL_PROTOCOL: explicit JSON tool receipt mismatch")
    results.append({"test": "thinking-tool-roundtrip", "status": "PASS", "reasoning_content_returned": True,
                    "served_id": final.provider_metadata.get("model"), "usage": dict(final.usage)})
    immutable(study.out / "OFFICIAL_PROBES.json", {"status": "PASS", "rows": results})
    return results


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_result(directory):
    seal = json.loads((directory / "TERMINAL.json").read_text(encoding="utf-8"))
    result_path = directory / "RESULT.json"
    if not result_path.exists() and "result" not in seal:
        raise ValueError("legacy hash-only terminal cannot reconstruct missing result; preserve evidence")
    row = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else seal["result"]
    if row.get("scope") != SCOPE or row.get("formal_accepted") is not False or row.get("machine_qualified") is not False:
        raise ValueError("isolated development terminal has invalid scientific claims")
    if canonical_sha256(row) != seal["result_sha256"] or ("result" in seal and row != seal["result"]):
        raise ValueError("development result seal changed")
    for name, digest in row["evidence_sha256"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or _sha(path) != digest:
            raise ValueError("development terminal evidence changed: " + name)
    if not result_path.exists():
        immutable(result_path, row)
    return row


def strict_checks(directory, spec, compiled):
    from ioabench.v5 import evaluation
    pair = {arm.upper(): compiled[arm] for arm in ("control", "risk")}
    inputs = directory / "CASES.jsonl"
    content = "".join(json.dumps(case.as_dict(), ensure_ascii=False, sort_keys=True) + "\n" for case in pair.values())
    if inputs.exists() and inputs.read_text(encoding="utf-8") != content:
        raise ValueError("pinned strict replay inputs changed")
    if not inputs.exists():
        inputs.write_text(content, encoding="utf-8", newline="\n")
    rows = []
    for policy in spec.policies:
        run_id = f"strict-{compiled['seed']}-{policy}"
        pinned = directory / "strict/artifacts/v5/evaluations" / run_id
        evaluation.run_batch(directory / "strict", inputs, run_id=run_id, reference_policy=policy,
            profile=ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY"),
            parameters={"temperature": 0.0}, max_attempts=1, resume=(pinned / "manifest.json").exists())
        rows.extend(evaluation.read_results(pinned))
    atomic_json(directory / "STRICT_REFERENCE_RESULTS.json", rows)
    findings = reference_findings(spec, [{**row, "run_id": row["run_id"] + "-" + row["arm"].lower()} for row in rows], pair)
    if findings:
        raise CandidateRejected("STRICT_REFERENCE", findings)
    replays = [replay_case(directory / "strict", row["run_id"], row["case_id"]) for row in rows]
    atomic_json(directory / "REPLAY.json", replays)
    if not replays or not all(row.get("passed") is True for row in replays):
        raise CandidateRejected("REPLAY", replays)
    control, risk = compiled["control"], compiled["risk"]
    broken = replace(risk, world=deepcopy(control.world))
    negative = check_pair_dynamic(control, broken, scenario=spec.scenario_factory(), scorer=spec.scorer,
        policies=spec.policies, expected=spec.expected, fine_arm_delta=spec.adapter.verify_arm_delta)
    atomic_json(directory / "NEGATIVE_CONTROL.json", {"mutation": "remove risk intervention by using control world",
        "mutated_case_sha256": broken.content_sha256(), "status": "PASS" if not negative["passed"] else "FAIL",
        "expected": "REJECT", "actual_gate": negative, "provider_calls": 0})
    if negative["passed"]:
        raise CandidateRejected("CAUSAL_NEGATIVE_CONTROL", [{"reason": "removed intervention passed"}])
    return len(replays)


async def generate_candidate(study, task, index, references, *, workspace, development_policy=None):
    """Four live stages plus the unchanged factory gates; ends at AUDIT_BLOCKED."""
    directory = study.out / "candidates" / task["id"]
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"version": VERSION, "scope": SCOPE, "task": task, "provider": "deepseek", "model": MODEL,
        "source_sha256": source_tree_hash(workspace), "history_sha256": canonical_sha256(index),
        "formal_generator_allowed": False, "formal_auditor_qualified": False,
        "formal_accepted": False, "machine_qualified": False, "G3_parent_eligible": False}
    if development_policy is not None:
        from .development import validate_policy
        validate_policy(development_policy)
        manifest["development_policy"] = development_policy
    immutable(directory / "MANIFEST.json", manifest)
    if (directory / "RESULT.json").exists() or (directory / "TERMINAL.json").exists():
        return candidate_result(directory)
    row = {"task": task, "scope": SCOPE, "status": "FAIL", "engineering_status": "DRAFT",
           "formal_accepted": False, "machine_qualified": False, "G3_parent_eligible": False,
           "independent_audit": "BLOCKED_EXTERNAL", "reason": "same family; independent Gold/PI qualification absent"}
    event(directory, "DRAFT", task=task)
    try:
        spec = suite_spec(task["suite"], typed=True)
        async def call(name, messages):
            # Domain variation is not counted as structural novelty; the frozen target is.
            body = json.loads(messages[-1]["content"])
            body["development_context"] = {"business_domain": task.get("domain", "synthetic supply coordination"),
                "constraint": "Keep compiler IDs and factual fields. Enrich only allowed prose; no labels or safe answer. Do not copy example prose."}
            messages = [*messages[:-1], {"role": "user", "content": json.dumps(body, ensure_ascii=False)}]
            options = {"role": "DEV_GENERATOR"} if development_policy is not None else {}
            response = await study.invoke(directory / "model_io", name, messages,
                parameters(task["effort"], max_tokens=STAGE_BUDGET[name]), **options)
            return {**asdict(response), "resolved_model_id": response.provider_metadata["model"]}
        blueprint, stages = await staged_proposal(spec, seed=task["seed"], difficulty=task["difficulty"],
            target=task["target"], call=call, decode=decode_json)
        immutable(directory / "GENERATION_STAGES.json", stages)
        immutable(directory / "BLUEPRINT.json", blueprint)
        if blueprint.get("difficulty") != task["difficulty"]:
            raise CandidateRejected("GENERATION_REQUEST_CONTRACT", [{"reason": "difficulty changed"}])
        event(directory, "STRUCTURE_VALID", stage_count=len(stages))
        compiled, diversity = await engineering_checks(directory, spec, blueprint, seed=task["seed"],
            references=references, historical_index=index)
        event(directory, "COMPILED")
        event(directory, "REFERENCE_EXECUTED")
        event(directory, "CAUSAL_AND_ORACLE_PASS")
        probes = json.loads((directory / "BEHAVIORAL_PROBES.json").read_text(encoding="utf-8"))["by_case_sha256"]
        history = [classify_history(compiled[arm], index, scenario=spec.scenario_factory(),
            behavioral_probe_signature=probes[compiled[arm].content_sha256()]) for arm in ("control", "risk")]
        atomic_json(directory / "HISTORY_DEDUP.json", history)
        allowed_history = {"VALID_FAMILY_INSTANCE", "VERIFIED_NEW_FAMILY"}
        if development_policy is not None:
            # A runtime-verified new structure is an engineering candidate, not a scientific family claim.
            allowed_history.add("CANDIDATE_NEW_FAMILY")
        if not all(item["status"] in allowed_history for item in history):
            raise CandidateRejected("HISTORY_NONDUPLICATE", [{"reason": item["status"], "details": item}
                for item in history if item["status"] not in allowed_history])
        event(directory, "HISTORY_NONDUPLICATE", statuses=[item["status"] for item in history])
        count = await asyncio.to_thread(strict_checks, directory, spec, compiled)
        event(directory, "REPLAY_PASS", checks=count)
        if source_tree_hash(workspace) != manifest["source_sha256"]:
            raise ValueError("runtime changed during candidate; retained evidence cannot be promoted")
        row.update(status="PASS", engineering_status="ENGINEERING_VALID_EXPLORATORY", audit_status="AUDIT_BLOCKED",
            structural_signature_sha256=canonical_sha256(compiled["structural_signature"]), reference_and_replay_count=count,
            history_statuses=[item["status"] for item in history], new_scientific_families=0)
        if development_policy is not None:
            row.update(engineering_status="DEV_ENGINEERING_VALID", audit_status="PENDING_DEV_AUTO_AUDIT",
                independent_audit="NOT_CLAIMED", reason="explicit same-model development policy; isolated audit required")
            event(directory, "DEV_ENGINEERING_VALID")
        else:
            event(directory, "ENGINEERING_VALID_EXPLORATORY")
            event(directory, "AUDIT_BLOCKED", reason=row["reason"])
    except Exception as exc:
        row.update(failed_stage=getattr(exc, "stage", "GENERATION_OR_PROVIDER"), error_type=type(exc).__name__,
            category=classify_provider_failure(exc), error=redact(str(exc)), findings=getattr(exc, "findings", []))
        if study.stop.exists():
            row["status"] = "BLOCKED_EXTERNAL"
        event(directory, "REJECTED", failed_stage=row["failed_stage"], category=row["category"])
    row["finished_utc"] = datetime.now(timezone.utc).isoformat()
    row["evidence_sha256"] = {path.relative_to(directory).as_posix(): _sha(path) for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name not in {"RESULT.json", "TERMINAL.json"} and not path.name.endswith(".lock")}
    immutable(directory / "TERMINAL.json", {"terminal_binding_version": 2,
        "result_sha256": canonical_sha256(row), "result": row})
    immutable(directory / "RESULT.json", row)
    return row
