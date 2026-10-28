"""Bounded, preregistered technical controls; no auditor qualification or production data."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]

from compare_auxiliary_models import checked_json, checked_result, contract_for, immutable, read, sha, usage_report
from ioabench.config.loader import load_workspace_env
from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelRequest
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract, AuxiliaryRouter, classify_provider_failure, redact
from ioabench.v5.ai_generation.model_routing import USER_CANDIDATES
from ioabench.v5.evaluation import atomic_json, writer_lock

VERSION = "ioabench.v5.next-model-controls/1.0.0"
DEFAULT_OUT = ROOT / "artifacts/v5/data_factory/next-r1/model_controls"
DEFAULT_PREFLIGHT = ROOT / "artifacts/v5/provider_contracts/next-r1"
DEFAULT_MATRIX = ROOT / "artifacts/v5/data_factory/next-r1/model_study/MODEL_CAPABILITY_MATRIX.json"
EXPECTED = {"probe": "next-controls", "value": 42}


def protocol_for(item):
    healthy = [row["protocol"] for row in item["protocols"] if row.get("json") == "PASS"]
    preferred = {"gpt-6.1-sol": "openai.responses", "claude-haiku-5-5": "anthropic.messages"}.get(item["requested_model_id"])
    if preferred in healthy:
        return preferred
    if not healthy:
        raise ValueError("no previously verified JSON protocol: " + item["requested_model_id"])
    return healthy[0]


def prepare(output, preflight, matrix, base_url):
    registry = read(matrix)["models"]
    selected = {model: protocol_for(next(item for item in registry if item["requested_model_id"] == model)) for model in USER_CANDIDATES}
    jobs = []
    for model in USER_CANDIDATES:
        maximum = contract_for(preflight, model, protocol=selected[model], budget=None)
        small = contract_for(preflight, model, protocol=selected[model], budget=16)
        jobs.extend([
            {"id": model + "-maximum", "kind": "DOCUMENTED_MAXIMUM_ACCEPTANCE", "contracts": [asdict(maximum)],
             "prompt": 'Return exactly the JSON object ' + json.dumps(EXPECTED) + '. Do not add anything.'},
            {"id": model + "-length16", "kind": "TRUNCATION_NEGATIVE", "contracts": [asdict(small)],
             "prompt": 'Return a JSON object with one key "numbers" containing every integer from 1 through 2000. No omissions or ellipses. Output the complete long list.'}])
        if model in {"glm-5.3", "glm-5.3-flash"}:
            parameters = {**maximum.parameters, "thinking": {"type": "disabled"}}
            jobs.append({"id": model + "-disabled", "kind": "THINKING_DISABLED_REJECTION",
                         "contracts": [asdict(replace(maximum, parameters=parameters))],
                         "prompt": 'Return exactly the JSON object ' + json.dumps(EXPECTED) + '.'})
    primary, fallback = "mimo-v2.6-pro", "mimo-v2.6-flash"
    bad = contract_for(preflight, primary, protocol=selected[primary], budget=None)
    limit = next(key for key in bad.parameters if key in {"max_tokens", "max_completion_tokens", "max_output_tokens"})
    bad = replace(bad, parameters={**bad.parameters, limit: "intentional-invalid-integer-control"})
    good = contract_for(preflight, fallback, protocol=selected[fallback], budget=None)
    jobs.append({"id": "real400-healthy-failover", "kind": "PARAMETER400_FAILOVER", "contracts": [asdict(bad), asdict(good)],
                 "prompt": 'Return exactly the JSON object ' + json.dumps(EXPECTED) + '.'})
    sources = [matrix, preflight / "MODEL_CATALOG.json", Path(__file__), ROOT / "scripts/v5/compare_auxiliary_models.py",
               ROOT / "src/ioabench/models/aihubmix.py", ROOT / "src/ioabench/v5/ai_generation/model_routing.py",
               ROOT / "src/ioabench/v5/ai_generation/auxiliary_runtime.py"]
    sources += [preflight / "schemas" / (model + ".json") for model in USER_CANDIDATES]
    plan = {"version": VERSION, "scope": "TECHNICAL_DEVELOPMENT_ONLY_NO_GOLD_OR_PRODUCTION",
            "base_url": base_url, "jobs": jobs, "max_concurrency": 2, "known_transient_attempts_per_model": 2,
            "request_timeout_seconds": 900, "unknown_send": "never resend or failover",
            "auth_failure": "stop shared credential for all queued controls; already in-flight requests may complete",
            "maximum_limit_claim": "Wire limit acceptance only; does not test generating the entire ceiling or long-context boundary.",
            "truncation_claim": "PASS only when a real retained response has finish_reason=length; HTTP400 is separately reported, not called truncation.",
            "disabled_claim": "PASS only on explicit HTTP400/request-schema rejection; acceptance is a negative-control failure, not automatically thinking disabled.",
            "sources_sha256": {str(path.resolve()): sha(path) for path in sources},
            "frozen_SUT_changed": False, "auditor_qualification": "BLOCKED_PI_GOLD_DISPOSITION"}
    assert len(jobs) == 19
    immutable(output / "PREREGISTRATION.json", plan)
    return plan


def verify_plan(plan):
    for name, digest in plan["sources_sha256"].items():
        if sha(Path(name)) != digest:
            raise ValueError("preregistered input changed: " + name)


def hydrate(value):
    from ioabench.models import ModelProfile
    return AuxiliaryContract(ModelProfile(**value["profile"]), value["parameters"], value["entry"],
                             value["preflight_evidence"], value["allowed_roles"], value.get("judge_gold_evidence"))


class SharedCredentialPort:
    """ModelPort decorator only; all actual transport stays in AIHubMixAdapter."""
    stop_on_provider_error = True

    def __init__(self, port):
        self.port, self.auth_stopped, self.adapter_calls = port, False, 0

    async def generate(self, profile, request):
        self.adapter_calls += 1
        try:
            return await self.port.generate(profile, request)
        except Exception as exc:
            if classify_provider_failure(exc) in {"AUTH/PERMISSION", "MISSING_SECRET"}:
                self.auth_stopped = True
            raise


def observed_result(job, attempts, error=None):
    responses = [item["response"] for item in attempts if item.get("response")]
    kind = job["kind"]
    status = "FAIL"
    if kind == "TRUNCATION_NEGATIVE":
        status = "PASS" if len(responses) == 1 and responses[0].get("finish_reason") == "length" else "FAIL"
    elif kind == "THINKING_DISABLED_REJECTION":
        status = "PASS" if any(item.get("category") == "REQUEST_SCHEMA" and "400" in item.get("error", "") for item in attempts) else "FAIL"
    elif kind == "PARAMETER400_FAILOVER":
        status = "PASS" if len(attempts) == 2 and attempts[0].get("category") == "REQUEST_SCHEMA" and "400" in attempts[0].get("error", "") and attempts[1].get("status") == "SUCCEEDED" and attempts[0]["requested_model_id"] != attempts[1].get("served_model_id") else "FAIL"
    elif attempts and attempts[-1].get("status") == "SUCCEEDED":
        status = "PASS"
    return {"control_id": job["id"], "kind": kind, "status": status,
            "observed_finishes": [item.get("finish_reason") for item in responses],
            "actual_models": [item.get("served_model_id") for item in attempts],
            "actual_parameters": [item.get("actual_parameters") for item in attempts],
            "attempts": len(attempts), "unresolved": sum(item.get("status") == "REQUEST_UNRESOLVED" for item in attempts),
            "error_type": type(error).__name__ if error else None, "error": redact(str(error)) if error else None,
            "response_scope": "Persisted ModelPort responses, provider metadata/HTTP diagnostics, reasoning, cache fields and usage; not a packet capture.",
            "scientific_acceptance": False}


async def run_control(output, job, plan_sha, port, catalog, semaphore):
    directory = output / job["id"]
    result_path = directory / "RESULT.json"
    if result_path.exists():
        result = checked_result(result_path)
        if result.get("preregistration_sha256") != plan_sha or result.get("control_id") != job["id"]:
            raise ValueError("retained control binding changed")
        return result
    started = time.monotonic()
    async with semaphore:
        if port.auth_stopped:
            row = {"control_id": job["id"], "kind": job["kind"], "status": "NOT_RUN",
                   "reason": "shared credential stopped after AUTH/PERMISSION or MISSING_SECRET", "attempts": 0}
        else:
            error = None
            router = AuxiliaryRouter(port, [hydrate(value) for value in job["contracts"]], catalog, directory / "model_io", max_attempts_per_model=2)
            try:
                await router.invoke("AUX_PROTOCOL_PROBE", "control", ModelRequest([{"role": "user", "content": job["prompt"]}], {}),
                    validate=(None if job["kind"] in {"TRUNCATION_NEGATIVE", "THINKING_DISABLED_REJECTION"}
                              else lambda response: checked_json(response, EXPECTED)))
            except Exception as exc:
                error = exc
            attempts = [read(path) for path in sorted((directory / "model_io/control").glob("attempt-*.json"))]
            row = observed_result(job, attempts, error)
    row.update(preregistration_sha256=plan_sha, elapsed_seconds=time.monotonic() - started)
    row["evidence_sha256"] = {path.relative_to(directory).as_posix(): sha(path) for path in directory.rglob("*")
                              if path.is_file() and path.name != "RESULT.json" and not path.name.endswith(".lock")}
    atomic_json(result_path, row)
    return row


async def run(output, preflight, *, port=None):
    plan = read(output / "PREREGISTRATION.json")
    verify_plan(plan)
    plan_sha = canonical_sha256(plan)
    # Validate complete durable results before creating a Provider or loading credentials.
    completed = []
    for job in plan["jobs"]:
        path = output / job["id"] / "RESULT.json"
        if path.exists():
            row = checked_result(path)
            if row.get("preregistration_sha256") != plan_sha or row.get("control_id") != job["id"]:
                raise ValueError("retained control binding changed")
            completed.append(row)
    if len(completed) == len(plan["jobs"]):
        return {**checked_result(output / "REPORT.json"), "adapter_calls_this_invocation": 0,
                "resume_no_provider_created": True}
    historical_auth = any(read(path).get("category") in {"AUTH/PERMISSION", "MISSING_SECRET"}
                          for path in output.glob("*/model_io/control/attempt-*.json"))
    if port is None and not historical_auth:
        load_workspace_env(ROOT / ".env")
        port = AIHubMixAdapter(base_url=plan["base_url"], request_timeout=900, stop_on_provider_error=True)
    guarded = SharedCredentialPort(port)
    guarded.auth_stopped = historical_auth
    semaphore = asyncio.Semaphore(plan["max_concurrency"])
    catalog = read(preflight / "MODEL_CATALOG.json")
    rows = await asyncio.gather(*(run_control(output, job, plan_sha, guarded, catalog, semaphore) for job in plan["jobs"]))
    verify_plan(plan)
    usage = usage_report(output)
    report = {"version": VERSION, "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "PARTIAL",
              "counts": dict(Counter(row["status"] for row in rows)), "rows": rows,
              "preregistration_sha256": plan_sha, "adapter_calls_this_invocation": guarded.adapter_calls,
              "auth_stopped": guarded.auth_stopped, "usage": usage,
              "long_context_boundary": "NOT_RUN", "full_maximum_generation": "NOT_RUN",
              "independent_auditor_qualification": "BLOCKED_PI_GOLD_DISPOSITION", "scientific_validity": "NOT_ESTABLISHED"}
    report["evidence_sha256"] = {path.relative_to(output).as_posix(): sha(path) for path in output.rglob("*")
                                 if path.is_file() and path.name != "REPORT.json" and not path.name.endswith(".lock")}
    atomic_json(output / "REPORT.json", report)
    return report


def verify_retained(output):
    """Verify old evidence without importing credentials or replaying a paid request."""
    plan = read(output / "PREREGISTRATION.json")
    plan_sha = canonical_sha256(plan)
    report = checked_result(output / "REPORT.json")
    rows, attempts, events = [], [], []
    for job in plan["jobs"]:
        directory = output / job["id"]
        row = checked_result(directory / "RESULT.json")
        if row.get("preregistration_sha256") != plan_sha or row.get("control_id") != job["id"]:
            raise ValueError("retained control binding changed")
        rows.append(row)
        model_io = directory / "model_io"
        if model_io.is_dir():
            AuxiliaryRouter(None, [], [], model_io).verify_ledger()
            ledger = [json.loads(line) for line in (model_io / "AIHUBMIX_ATTEMPTS.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            events.extend(ledger)
            for path in sorted((model_io / "control").glob("attempt-*.json")):
                attempt = read(path)
                finished = [event for event in ledger if event.get("event") == "REQUEST_FINISHED" and event.get("attempt_id") == attempt["attempt_id"]]
                if len(finished) != 1 or any(finished[0].get(key) != value for key, value in attempt.items()):
                    raise ValueError("retained attempt/ledger mismatch: " + str(path))
                attempts.append((path.relative_to(output).as_posix(), attempt))
            binding = read(model_io / "control/REQUEST_BINDING.json")
            if canonical_sha256(binding["binding"]) != binding["sha256"]:
                raise ValueError("retained request binding changed")
            response_path = model_io / "control/RESPONSE.json"
            if response_path.is_file():
                response = read(response_path)
                if response["binding_sha256"] != binding["sha256"] or canonical_sha256(response["response"]) != response["response_sha256"]:
                    raise ValueError("retained response binding changed")
    if report.get("preregistration_sha256") != plan_sha or report.get("rows") != rows or report.get("counts") != dict(Counter(row["status"] for row in rows)):
        raise ValueError("retained aggregate/control mismatch")
    finished = [event for event in events if event.get("event") == "REQUEST_FINISHED"]
    if len(finished) != len(attempts) or sum(event.get("event") == "REQUEST_STARTED" for event in events) != len(attempts):
        raise ValueError("retained ledger contains incomplete requests")
    usage = {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in finished)
             for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    summary = read(output / "USAGE_LEDGER_SUMMARY.json")
    if (summary["usage"] != usage or summary["started"] != len(attempts) or summary["finished"] != len(attempts)
            or summary["status_counts"] != dict(Counter(event["status"] for event in finished))
            or summary["unknown_usage_requests"] != sum(not event.get("usage") for event in finished)
            or summary["unknown_billing_requests"] != sum((event.get("cost") or {}).get("amount") is None for event in finished)
            or not math.isclose(summary["estimated_usd_known_subtotal"], sum((event.get("cost") or {}).get("amount") or 0 for event in finished), rel_tol=0, abs_tol=1e-12)):
        raise ValueError("retained usage/ledger mismatch")
    limit_failures, usage_failures = [], []
    for name, attempt in attempts:
        parameters, tokens = attempt.get("actual_parameters") or {}, attempt.get("usage") or {}
        limit = next((parameters[key] for key in ("max_tokens", "max_completion_tokens", "max_output_tokens") if key in parameters), None)
        completion = tokens.get("completion_tokens")
        details = tokens.get("completion_tokens_details") or tokens.get("output_tokens_details") or {}
        reasoning = details.get("reasoning_tokens", details.get("thinking_tokens"))
        if isinstance(limit, int) and completion is not None and completion > limit:
            limit_failures.append(name)
        if reasoning is not None and completion is not None and reasoning > completion:
            usage_failures.append(name)
    drift = {name: {"preregistered_sha256": expected, "current_sha256": sha(Path(name)) if Path(name).is_file() else None}
             for name, expected in plan["sources_sha256"].items() if not Path(name).is_file() or sha(Path(name)) != expected}
    return {"version": VERSION, "verification_status": "PASS", "original_control_status": report["status"],
            "original_control_counts": report["counts"], "original_results_rejudged": False,
            "source_binding_status": "PARTIAL" if drift else "PASS", "source_binding_reason": "SOURCE_DRIFT" if drift else None, "source_drift": drift,
            "numeric_limit_enforcement": "FAIL" if limit_failures else "PASS_OBSERVED_ONLY", "numeric_limit_failures": limit_failures,
            "reported_usage_consistency": "FAIL" if usage_failures else "PASS_OBSERVED_ONLY", "reported_usage_failures": usage_failures,
            "verified_requests": len(attempts), "verified_ledgers": len(list(output.glob("*/model_io/AIHUBMIX_ATTEMPTS.jsonl"))),
            "usage": summary, "provider_calls_this_verification": 0, "provider_created": False,
            "independent_auditor_qualification": "BLOCKED_PI_GOLD_DISPOSITION", "scientific_validity": "NOT_ESTABLISHED",
            "long_context_boundary": "NOT_RUN", "full_maximum_generation": "NOT_RUN",
            "verification_code_sha256": sha(Path(__file__)),
            "evidence_sha256": {path.relative_to(output).as_posix(): sha(path) for path in output.rglob("*")
                                if path.is_file() and not path.name.endswith(".lock") and not path.name.startswith("FINAL_VERIFICATION")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "run", "verify"), required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--base-url", choices=("https://api.inferera.com/v1", "https://aihubmix.com/v1"), default="https://api.inferera.com/v1")
    args = parser.parse_args()
    if args.phase == "verify":
        print(json.dumps(verify_retained(args.out), ensure_ascii=False, indent=2))
        return
    with writer_lock(args.out):
        result = prepare(args.out, args.preflight, args.matrix, args.base_url) if args.phase == "prepare" else asyncio.run(run(args.out, args.preflight))
    print(json.dumps({key: result.get(key) for key in ("version", "status", "counts", "adapter_calls_this_invocation", "auth_stopped", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
