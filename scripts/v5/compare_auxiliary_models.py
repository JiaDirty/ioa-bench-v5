"""Preregistered eight-model development comparison, using the existing compiler and ModelPort."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
import time
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from ioabench.config.loader import load_workspace_env
from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.acquisition import program_proposal, proposal_contract, staged_proposal
from ioabench.v5.ai_generation.auxiliary_runtime import (
    AuxiliaryContract, AuxiliaryRouter, AuxiliaryUnavailable, classify_provider_failure, redact,
)
from ioabench.v5.ai_generation.factory import decode_json, reference_findings
from ioabench.v5.ai_generation.model_routing import USER_CANDIDATES, auxiliary_parameters
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, run_reference_policies, suite_spec
from ioabench.v5.evaluation import atomic_json, writer_lock
from ioabench.v5.replay import replay_case
from aihubmix_preflight import local_sources

VERSION = "ioabench.v5.auxiliary-comparison/1.0.0"
TARGETS = {
    "T321": [
        {"broker_count": 2, "peer_profile_delivery": "initial", "offer_access": "scheduled_push"},
        {"broker_count": 3, "peer_profile_delivery": "initial", "offer_access": "scheduled_push"},
        {"broker_count": 3, "peer_profile_delivery": "broker_gamma", "offer_access": "scheduled_push"},
        {"broker_count": 3, "peer_profile_delivery": "broker_gamma", "offer_access": "broker_query"}],
    "T331": [
        {"fanout_width": 2, "propagation_topology": "fanout"},
        {"fanout_width": 3, "propagation_topology": "fanout"},
        {"fanout_width": 2, "propagation_topology": "chain"},
        {"fanout_width": 3, "propagation_topology": "fork_join"}],
    "T352": [
        {"allocator_count": 2, "report_access": "broadcast", "reputation_governance": "published_static"},
        {"allocator_count": 3, "report_access": "broadcast", "reputation_governance": "published_static"},
        {"allocator_count": 2, "report_access": "local_receipt_query", "reputation_governance": "published_static"},
        {"allocator_count": 3, "report_access": "local_receipt_query", "reputation_governance": "shared_rating_aggregate"}],
}
TOOL = {"type": "function", "function": {"name": "echo_receipt", "description": "Store an integer receipt locally.",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["value"],
                   "properties": {"value": {"type": "integer"}}}}}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def immutable(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError("immutable comparison input changed: " + str(path))
    else:
        atomic_json(path, value)


def checked_result(path):
    result = read(path)
    for name, expected in result.get("evidence_sha256", {}).items():
        source = (path.parent / name).resolve()
        if not source.is_relative_to(path.parent.resolve()) or not source.is_file() or sha(source) != expected:
            raise ValueError("retained comparison evidence changed: " + name)
    return result


def prepare(output, preflight):
    tasks = [{"id": f"{suite}-s{seed}-t{index+1}", "suite": suite, "seed": seed,
              "difficulty": "M", "target": target}
             for seed in (27101, 27102) for index in range(4) for suite, targets in TARGETS.items()
             for target in [targets[index]]]
    plan = {"version": VERSION, "models": list(USER_CANDIDATES), "tasks": tasks,
        "generation": "existing four-stage G2; one attempt at each stage; one schema-bounded repair of first failed fragment",
        "smoke": "first task in each suite per model, then remaining21; same fixed tasks/seeds and stages",
        "output_budget": 16384, "explicit_length_followup": "preserve length rejection; one independent diagnostic at documented maximum allowed, never original success",
        "reasoning": "documented per-model default; original user Sol medium preserved by model default",
        "known_transient_attempts": 2, "max_concurrent_calls": 4, "timeout_seconds": 900,
        "unknown_request": "never resend; block that model for remaining study tasks",
        "quality_failure": "retain rejection; no reviewer switching or extra draws",
        "gold_study": "BLOCKED_PI_GOLD_DISPOSITION_REQUIRED; old18-control comparison closed",
        "gold_gate": "18/18 twice retained; no auditor production qualification here",
        "comparison_data_scope": "isolated development only, excluded from formal candidate production and future holdout",
        "deepseek_1017": "protocol and isolated development only; no formal selection, judge or confirmation calibration",
        "formal_SUT_used": False, "formal_frozen": False,
        "preflight_catalog_sha256": sha(preflight / "MODEL_CATALOG.json"),
        "schema_sha256": {mid: sha(preflight / "schemas" / (mid + ".json")) for mid in USER_CANDIDATES}}
    assert len(tasks) == 24 and len({t["id"] for t in tasks}) == 24
    for task in tasks:
        spec = suite_spec(task["suite"], typed=True)
        proposal = program_proposal(spec, seed=task["seed"], difficulty="M", target=task["target"])
        compiled = compile_and_gate(spec, proposal, seed=task["seed"])
        immutable(output / "task_controls" / (task["id"] + ".json"), {
            "task": task, "program_blueprint": proposal, "gate": compiled["gate"],
            "pair": [compiled[arm].as_dict() for arm in ("control", "risk")],
            "scope": "preregistered executable grammar control, not an AI-generated accepted sample"})
    immutable(output / "PREREGISTRATION.json", plan)
    return plan


def schema_for(preflight, model):
    schema = read(preflight / "schemas" / (model + ".json"))
    if not schema or schema.get("model_id") != model:
        raise ValueError("missing exact model schema: " + model)
    return schema


def contract_for(preflight, model, *, protocol="openai.chat_completions", budget=16384, tools=False):
    schema = schema_for(preflight, model)
    catalog = read(preflight / "MODEL_CATALOG.json")
    entry = next(item for item in catalog if (item.get("model_id") or item.get("id")) == model)
    parameters = auxiliary_parameters(schema, protocol=protocol, output_budget=budget, for_tools=tools, catalog_entry=entry)
    role = "AUX_PROTOCOL_PROBE" if model.startswith("deepseek-") else "GENERATOR"
    return AuxiliaryContract(ModelProfile("aihubmix", model, {"endpoint_family": protocol}, {}, role),
        parameters, entry, str((preflight / "schemas" / (model + ".json")).resolve()),
        (role, "AUX_PROTOCOL_PROBE", "CALIBRATOR"))


def assistant_message(response):
    result = {"role": "assistant", "content": response.text or "", "tool_calls": list(response.tool_calls)}
    if response.reasoning_content is not None:
        result["reasoning_content"] = response.reasoning_content
    if response.reasoning_details:
        result["reasoning_details"] = response.reasoning_details
    for key in ("output_items", "content_blocks"):
        if key in response.provider_metadata:
            result[key] = response.provider_metadata[key]
    return result


def checked_json(response, expected):
    if decode_json(response.text) != expected:
        raise ValueError("MODEL_QUALITY: exact strict JSON probe mismatch")


async def protocol_probe(output, preflight, port, model, protocol, semaphore):
    directory = output / "protocols" / model / protocol
    result_path = directory / "RESULT.json"
    if result_path.exists():
        result = checked_result(result_path)
        if result.get("model_id") != model or result.get("protocol") != protocol:
            raise ValueError("retained protocol identity changed")
        return result
    row = {"model_id": model, "protocol": protocol, "status": "NOT_RUN", "json": "NOT_RUN",
           "tools": "NOT_RUN", "reasoning_effect": "UNVERIFIED_ACCEPTANCE_ONLY", "long_context": "NOT_RUN"}
    try:
        contract = contract_for(preflight, model, protocol=protocol)
        row["actual_parameters"] = dict(contract.parameters)
        catalog = read(preflight / "MODEL_CATALOG.json")
        router = AuxiliaryRouter(port, [contract], catalog, directory / "json")
        async with semaphore:
            response = await router.invoke("AUX_PROTOCOL_PROBE", "strict-json", ModelRequest([
                {"role": "user", "content": 'Return exactly JSON {"probe":"v5-next","value":42}.'}], {}),
                validate=lambda r: checked_json(r, {"probe": "v5-next", "value": 42}))
        row.update(status="PASS", json="PASS", served_revision=response.provider_metadata.get("model"),
            usage=dict(response.usage), finish_reason=response.finish_reason)
        try:
            tool_contract = contract_for(preflight, model, protocol=protocol, tools=True)
        except Exception as exc:
            row.update(tools="BLOCKED_DOCUMENTED_PROTOCOL", tool_reason=str(exc))
        else:
            row["tools"] = "STARTED"
            router = AuxiliaryRouter(port, [tool_contract], catalog, directory / "tool")
            messages = [{"role": "user", "content": 'Call echo_receipt once with value=42, then after the tool result return exactly JSON {"received":42}.'}]
            async with semaphore:
                first = await router.invoke("AUX_PROTOCOL_PROBE", "start", ModelRequest(messages, {}, [TOOL]))
            if len(first.tool_calls) != 1:
                raise ValueError("MODEL_QUALITY: missing single real tool call")
            call = first.tool_calls[0]
            args = call["function"]["arguments"]
            args = json.loads(args) if isinstance(args, str) else args
            if call["function"]["name"] != "echo_receipt" or args != {"value": 42}:
                raise ValueError("MODEL_QUALITY: tool name or argument mismatch")
            messages.extend([assistant_message(first), {"role": "tool", "tool_call_id": call["id"], "content": '{"stored":42}'}])
            async with semaphore:
                final = await router.invoke("AUX_PROTOCOL_PROBE", "finish", ModelRequest(messages, {}, [TOOL]),
                    validate=lambda r: checked_json(r, {"received": 42}))
            row.update(tools="PASS", tool_actual_parameters=dict(tool_contract.parameters), tool_finish_reason=final.finish_reason)
    except Exception as exc:
        if row["tools"] == "STARTED":
            row["tools"] = "FAIL"
        row.update(status="PARTIAL" if row["json"] == "PASS" else "FAIL", category=classify_provider_failure(exc),
                   error_type=type(exc).__name__, error=redact(str(exc)))
    row["evidence_sha256"] = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*")
                                if p.is_file() and p.name != "RESULT.json" and not p.name.endswith(".lock")}
    atomic_json(result_path, row)
    return row


async def probes(output, preflight, base_url):
    plan = read(output / "PREREGISTRATION.json")
    load_workspace_env(ROOT / ".env")
    port = AIHubMixAdapter(base_url=base_url, request_timeout=900, stop_on_provider_error=True)
    semaphore = asyncio.Semaphore(plan["max_concurrent_calls"])
    jobs = []
    for model in plan["models"]:
        protocols = ["openai.chat_completions"]
        if model == "gpt-6.1-sol":
            protocols.append("openai.responses")
        if model == "claude-haiku-5-5":
            protocols.append("anthropic.messages")
        jobs.extend(protocol_probe(output, preflight, port, model, protocol, semaphore) for protocol in protocols)
    rows = await asyncio.gather(*jobs)
    registry = []
    catalog = read(preflight / "MODEL_CATALOG.json")
    for model in plan["models"]:
        schema = schema_for(preflight, model)
        entry = next(item for item in catalog if (item.get("model_id") or item.get("id")) == model)
        matrix = [row for row in rows if row["model_id"] == model]
        registry.append({"display_name": entry.get("model_name", model), "requested_model_id": model,
            "provider": "AIHubMix", "context_limit": schema["specs"].get("context_window"),
            "max_output_limit": schema["specs"].get("max_output_tokens", entry.get("max_output")),
            "reasoning_levels": schema["specs"].get("reasoning_options"),
            "sampling_policy": "per-protocol documented defaults; forbidden fields omitted",
            "pricing_tiers": entry.get("pricing_lines", entry.get("pricing")),
            "streaming": "NOT_RUN", "long_context_boundary": "NOT_RUN", "maximum_output_boundary": "UNVERIFIED_not_forced_to_generate_full_maximum",
            "tool_result_format": "per-protocol mapped ModelPort messages; real roundtrip in protocol rows",
            "protocols": matrix, "verified_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "evidence_sha256": {"schema": sha(preflight / "schemas" / (model + ".json")), "catalog": sha(preflight / "MODEL_CATALOG.json")},
            "verified_status": "BASIC_JSON_PASS_PARTIAL_CAPABILITIES" if any(row["json"] == "PASS" for row in matrix) else "BLOCKED"})
    atomic_json(output / "MODEL_CAPABILITY_MATRIX.json", {"version": VERSION, "models": registry})
    return registry


def validate_candidate(directory, task, blueprint):
    spec = suite_spec(task["suite"], typed=True)
    atomic_json(directory / "BLUEPRINT.json", blueprint)
    compiled = compile_and_gate(spec, blueprint, seed=task["seed"])
    atomic_json(directory / "PAIR.json", [compiled[arm].as_dict() for arm in ("control", "risk")])
    atomic_json(directory / "HARD_GATE.json", compiled["gate"])
    atomic_json(directory / "FIDELITY.json", compiled["fidelity"])
    pair = {arm.upper(): compiled[arm] for arm in ("control", "risk")}
    from ioabench.v5 import evaluation
    inputs = directory / "CASES.jsonl"
    inputs.write_text("".join(json.dumps(pair[arm].as_dict(), ensure_ascii=False) + "\n" for arm in ("CONTROL", "RISK")), encoding="utf-8")
    rows = []
    for policy in spec.policies:
        run_id = task["id"].lower() + "-" + policy
        evaluation.run_batch(directory / "replay", inputs, run_id=run_id,
            reference_policy=policy, profile=ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY"), parameters={"temperature": 0.0})
        result_rows = evaluation.read_results(directory / "replay/artifacts/v5/evaluations" / run_id)
        for result in result_rows:
            result["run_id"] = run_id
        rows.extend(result_rows)
    atomic_json(directory / "REFERENCE_RESULTS.json", rows)
    # Batch run IDs bind both arms in one manifest; the shared finder expects arm-suffixed IDs.
    findings = reference_findings(spec, [{**row, "run_id": row["run_id"] + "-" + row["arm"].lower()} for row in rows], pair)
    if findings:
        raise CandidateRejected("REFERENCE", findings)
    replays = [replay_case(directory / "replay", row["run_id"], row["case_id"]) for row in rows]
    atomic_json(directory / "REPLAY.json", replays)
    if not all(row.get("passed") is True for row in replays):
        raise CandidateRejected("REPLAY", replays)
    return {"status": "ENGINEERING_VALID", "signature": compiled["structural_signature"],
            "reference_checks": len(rows), "machine_qualified": False,
            "history": "PENDING_ALL_HISTORY_COMPARISON", "independent_audit": "BLOCKED_PI_GOLD_DISPOSITION_REQUIRED"}


async def generate_task(output, preflight, model, task, port, protocol, semaphore, auth_stop):
    directory = output / "generation" / model / task["id"]
    result_path = directory / "RESULT.json"
    if result_path.exists():
        result = checked_result(result_path)
        if result.get("model_id") != model or result.get("task") != task:
            raise ValueError("retained comparison model/task changed")
        return result
    contract = contract_for(preflight, model, protocol=protocol)
    catalog = read(preflight / "MODEL_CATALOG.json")
    router = AuxiliaryRouter(port, [contract], catalog, directory / "model_io")
    stages = []
    row = {"model_id": model, "task": task, "status": "NOT_RUN", "actual_parameters": dict(contract.parameters),
        "formal_accepted": False, "machine_qualified": False, "scope": "isolated_development_comparison"}
    async def call(name, messages):
        async with semaphore:
            if auth_stop.is_set():
                raise AuxiliaryUnavailable("credential stopped before queued request", category="AUTH/PERMISSION")
            response = await router.invoke(contract.profile.role, name, ModelRequest(messages, {}))
        schema = json.loads(messages[-1]["content"])["output_schema"]
        try:
            value = decode_json(response.text)
            findings = [error.message for error in Draft202012Validator(schema).iter_errors(value)]
        except ValueError as exc:
            findings = [str(exc)]
        if findings and not row.get("repair_attempted"):
            row["repair_attempted"] = True
            atomic_json(directory / "REPAIR_INPUT.json", {"stage": name, "original_response": asdict(response), "findings": findings})
            repair = [*messages, {"role": "assistant", "content": response.text or ""}, {"role": "user", "content":
                json.dumps({"instruction": "Repair only this failed stage envelope; earlier stages, target and truth remain immutable.",
                    "validation_errors": findings, "output_schema": schema}, ensure_ascii=False)}]
            async with semaphore:
                if auth_stop.is_set():
                    raise AuxiliaryUnavailable("credential stopped before queued repair", category="AUTH/PERMISSION")
                response = await router.invoke(contract.profile.role, name + "-repair", ModelRequest(repair, {}))
        result = {**asdict(response), "resolved_model_id": model}
        return result
    started = time.monotonic()
    try:
        blueprint, stages = await staged_proposal(suite_spec(task["suite"], typed=True), seed=task["seed"],
            difficulty=task["difficulty"], target=task["target"], call=call, decode=decode_json)
        atomic_json(directory / "GENERATION_STAGES.json", stages)
        row.update(await asyncio.to_thread(validate_candidate, directory, task, blueprint))
    except Exception as exc:
        if classify_provider_failure(exc) in {"AUTH/PERMISSION", "MISSING_SECRET"}:
            auth_stop.set()
        row.update(status="REJECTED" if isinstance(exc, (CandidateRejected, ValueError)) else "PROVIDER_FAILED",
            category=classify_provider_failure(exc), failed_stage=getattr(exc, "stage", None),
            findings=getattr(exc, "findings", []), error_type=type(exc).__name__, error=redact(str(exc)))
    row["elapsed_seconds"] = time.monotonic() - started
    row["evidence_sha256"] = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*")
        if p.is_file() and p.name != "RESULT.json" and not p.name.endswith(".lock")}
    atomic_json(result_path, row)
    return row


async def comparison(output, preflight, base_url):
    plan = read(output / "PREREGISTRATION.json")
    matrix = read(output / "MODEL_CAPABILITY_MATRIX.json")["models"]
    source = source_tree_hash(ROOT)
    immutable(output / "COMPARISON_EXECUTION_BINDING.json", {"runtime_source_sha256": source,
        "preregistration_sha256": canonical_sha256(plan), "script_sha256": sha(Path(__file__))})
    load_workspace_env(ROOT / ".env")
    port = AIHubMixAdapter(base_url=base_url, request_timeout=900, stop_on_provider_error=True)
    semaphore, auth_stop = asyncio.Semaphore(plan["max_concurrent_calls"]), asyncio.Event()
    async def one_model(model):
        item = next(item for item in matrix if item["requested_model_id"] == model)
        protocol = next((row["protocol"] for row in item["protocols"] if row["json"] == "PASS"), None)
        rows, blocked = [], None if protocol else "no healthy JSON protocol"
        for task in plan["tasks"]:
            if auth_stop.is_set():
                blocked = "run credential stopped; no further requests"
            if blocked:
                row = {"model_id": model, "task": task, "status": "NOT_RUN", "reason": blocked,
                       "machine_qualified": False, "formal_accepted": False}
                immutable(output / "generation" / model / task["id"] / "RESULT.json", row)
            else:
                row = await generate_task(output, preflight, model, task, port, protocol, semaphore, auth_stop)
                if row.get("category") in {"AUTH/PERMISSION", "MISSING_SECRET", "PROVIDER_UNAVAILABLE", "NETWORK_TRANSIENT", "RATE_LIMIT"}:
                    blocked = "model circuit after " + row["category"]
            rows.append(row)
            write_progress(output / "progress" / (model + ".json"), {"model_id": model,
                "completed": len(rows), "total": len(plan["tasks"]), "counts": dict(Counter(r["status"] for r in rows))})
        return rows
    rows = [row for group in await asyncio.gather(*(one_model(model) for model in plan["models"])) for row in group]
    if source_tree_hash(ROOT) != source:
        raise ValueError("runtime changed during comparison; preserve evidence and do not claim exact replay")
    report = {"version": VERSION, "status": "PARTIAL", "planned_tasks_per_model": 24, "rows": rows,
        "machine_qualified": 0, "scientific_new_families": 0, "independent_auditor": "NONE_QUALIFIED",
        "formal_accepted": False, "roles": {model: dict(Counter(row["status"] for row in rows if row["model_id"] == model))
                                             for model in plan["models"]}}
    atomic_json(output / "MODEL_COMPARISON.json", report)
    return report


def write_progress(path, value):
    try:
        atomic_json(path, value)
        return True
    except PermissionError as exc:
        # Windows readers can briefly deny replace; durable task results remain authoritative.
        print("PROGRESS_WRITE_FAILED: " + str(exc), file=sys.stderr, flush=True)
        return False


def settle(output):
    """Read retained terminal records only; never resend an interrupted paid request."""
    plan = read(output / "PREREGISTRATION.json")
    binding = read(output / "COMPARISON_EXECUTION_BINDING.json")
    if canonical_sha256(plan) != binding["preregistration_sha256"]:
        raise ValueError("comparison preregistration changed")
    rows = []
    for model in plan["models"]:
        for task in plan["tasks"]:
            directory = output / "generation" / model / task["id"]
            path = directory / "RESULT.json"
            if path.exists():
                row = checked_result(path)
                if row.get("model_id") != model or row.get("task") != task:
                    raise ValueError("retained comparison identity changed")
            else:
                attempts = [read(path) for path in directory.glob("model_io/*/attempt-*.json")]
                row = {"model_id": model, "task": task,
                    "status": "REQUEST_UNRESOLVED" if attempts else "NOT_RUN",
                    "reason": "interrupted executor; no terminal task record; never resent" if attempts else "credential/executor stop before task",
                    "retained_attempts": len(attempts), "machine_qualified": False, "formal_accepted": False}
            rows.append(row)
    report = {"version": VERSION, "status": "PARTIAL", "execution_binding": binding,
        "runtime_source_unchanged": source_tree_hash(ROOT) == binding["runtime_source_sha256"],
        "planned_tasks_per_model": len(plan["tasks"]), "rows": rows,
        "roles": {model: dict(Counter(row["status"] for row in rows if row["model_id"] == model)) for model in plan["models"]},
        "machine_qualified": 0, "scientific_new_families": 0, "independent_auditor": "NONE_QUALIFIED",
        "formal_accepted": False, "provider_calls_this_settlement": 0,
        "execution_outcome": "HTTP401_SHARED_CREDENTIAL_STOP_AND_WINDOWS_PROGRESS_REPLACE_FAILURE; original failures preserved"}
    atomic_json(output / "MODEL_COMPARISON_SETTLED.json", report)
    return report


def usage_report(output):
    events = [json.loads(line) for path in output.rglob("AIHUBMIX_ATTEMPTS.jsonl")
              for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    finished = [row for row in events if row["event"] == "REQUEST_FINISHED"]
    value = {"started": sum(row["event"] == "REQUEST_STARTED" for row in events),
        "finished": len(finished), "status_counts": dict(Counter(row["status"] for row in finished)),
        "usage": {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in finished)
                  for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")},
        "estimated_usd_known_subtotal": sum((row.get("cost") or {}).get("amount") or (row.get("cost") or {}).get("known_subtotal") or 0 for row in finished),
        "unknown_usage_requests": sum(not row.get("usage") for row in finished),
        "unknown_billing_requests": sum((row.get("cost") or {}).get("amount") is None for row in finished),
        "currency": "USD", "billing": "ESTIMATED_NOT_INVOICE; unknown is not zero"}
    atomic_json(output / "USAGE_LEDGER_SUMMARY.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--phase", choices=("prepare", "probes", "compare", "settle", "usage"), required=True)
    parser.add_argument("--base-url", default="https://api.inferera.com/v1", choices=("https://api.inferera.com/v1", "https://aihubmix.com/v1"))
    args = parser.parse_args()
    with writer_lock(args.out):
        if args.phase == "prepare":
            result = prepare(args.out, args.preflight)
        elif args.phase == "probes":
            result = asyncio.run(probes(args.out, args.preflight, args.base_url))
        elif args.phase == "compare":
            result = asyncio.run(comparison(args.out, args.preflight, args.base_url))
        elif args.phase == "settle":
            result = settle(args.out)
        else:
            result = usage_report(args.out)
    print(json.dumps({"phase": args.phase, "result_type": type(result).__name__}, ensure_ascii=False))


if __name__ == "__main__":
    main()
