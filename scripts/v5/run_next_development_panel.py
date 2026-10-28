"""Fixed eight-model, three-suite development panel; never a scientific difficulty calibration."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]

from ioabench.config.loader import load_workspace_env
from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5 import evaluation, replay
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryRouter, classify_provider_failure, redact
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.core.case import case_from_dict
from calibrate_factory_candidates import PanelPort
import compare_auxiliary_models as comparison

VERSION = "ioabench.v5.next-development-panel/1.0.0"
SEED = 42101
TARGETS = {
    "T321": {"broker_count": 2, "peer_profile_delivery": "initial", "offer_access": "broker_query"},
    "T331": {"fanout_width": 3, "propagation_topology": "chain"},
    "T352": {"allocator_count": 2, "report_access": "broadcast", "reputation_governance": "shared_rating_aggregate"},
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preferred_protocol(model):
    return {"gpt-6.1-sol": "openai.responses", "claude-haiku-5-5": "anthropic.messages"}.get(model, "openai.chat_completions")


def observed_identity(directory):
    result = comparison.checked_result(directory / "RESULT.json")
    if result.get("status") != "PASS" or result.get("json") != "PASS" or result.get("tools") != "PASS":
        raise ValueError("a successful JSON and real tool-loop preflight is required")
    responses = [read(directory / path)["response"] for path in
        ("json/strict-json/RESPONSE.json", "tool/start/RESPONSE.json", "tool/finish/RESPONSE.json")]
    bodies, gateways = [], []
    for response in responses:
        metadata = response["provider_metadata"]
        body = metadata.get("model")
        gateway = metadata.get("transport_metadata", {}).get("x-aihubmix-model")
        if not body or not gateway:
            raise ValueError("missing actual provider body/header identity")
        bodies.append(str(body))
        gateways.append(str(gateway))
    if set(gateways) != {result["model_id"]}:
        raise ValueError("preflight gateway identity differs from exact candidate")
    return {"body_model": bodies[0], "body_aliases": sorted(set(bodies)), "gateway_model": gateways[0]}, result


def iter_cases(value):
    if isinstance(value, dict):
        if "world" in value and "oracle" in value and "suite_id" in value:
            yield value
        else:
            for child in value.values():
                yield from iter_cases(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_cases(child)


def overlap_report(cases, study, workspace):
    selected = {}
    for case in cases:
        spec = suite_spec(case.suite_id, typed=True)
        selected[case.content_sha256()] = canonical_sha256(spec.adapter.structural_signature(case))
    paths = sorted((study / "task_controls").glob("*.json"))
    paths += sorted((workspace / "artifacts/v5/data_factory/quality_controls").glob("*/GOLD_CONTROLS.json"))
    paths += sorted(path for suite in TARGETS for path in (workspace / "data/v5/datasets" / suite).glob("*/cases.jsonl"))
    matches, unknown, occurrences = [], [], 0
    for path in paths:
        try:
            values = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.suffix == ".jsonl" else [read(path)]
            for value in values:
                for raw in iter_cases(value):
                    if raw["suite_id"].split("-")[0] not in TARGETS:
                        continue
                    occurrences += 1
                    try:
                        case = case_from_dict(raw, allow_dynamic=True)
                        spec = suite_spec(case.suite_id, typed=True)
                        signature = canonical_sha256(spec.adapter.structural_signature(case))
                        content = case.content_sha256()
                        exact = content in selected
                        structural = signature in selected.values()
                        if exact or structural:
                            matches.append({"source": str(path), "case_id": case.case_id,
                                "exact_case_hash_overlap": exact, "structural_signature_overlap": structural,
                                "case_sha256": content, "structure_sha256": signature})
                    except Exception as exc:
                        unknown.append({"source": str(path), "case_id": raw.get("case_id"), "reason": str(exc)})
        except Exception as exc:
            unknown.append({"source": str(path), "reason": str(exc)})
    return {"scope": [str(path) for path in paths], "source_sha256": {str(path): sha(path) for path in paths},
        "candidate_case_occurrences": occurrences, "matches": matches, "indeterminate": unknown,
        "comparison_targets_different": all(TARGETS[suite] not in comparison.TARGETS[suite] for suite in TARGETS),
        "comparison_seed_different": SEED not in (27101, 27102),
        "claim": "Development partition only; different seeds or exact hashes do not prove scientific independence or new families.",
        "formal_holdout_independence": "NOT_ESTABLISHED", "history_exhaustive": False}


def prepare(output, preflight, study, workspace=ROOT):
    output, preflight, study = Path(output), Path(preflight), Path(study)
    matrix = read(study / "MODEL_CAPABILITY_MATRIX.json")
    models = [row["requested_model_id"] for row in matrix["models"]]
    if models != list(comparison.USER_CANDIDATES) or len(models) != 8:
        raise ValueError("exact preregistered eight-model order is required")
    cases, controls = [], []
    for suite, target in TARGETS.items():
        spec = suite_spec(suite, typed=True)
        blueprint = program_proposal(spec, seed=SEED, difficulty="M", target=target)
        compiled = compile_and_gate(spec, blueprint, seed=SEED)
        pair = [replace(compiled[arm], provenance={**compiled[arm].provenance,
            "development_panel": VERSION, "split": "calibration", "selection_seed": SEED}) for arm in ("control", "risk")]
        cases.extend(pair)
        controls.append({"suite": suite, "target": target, "seed": SEED, "blueprint": blueprint,
            "gate": compiled["gate"], "fidelity": compiled["fidelity"], "pair": [case.as_dict() for case in pair],
            "structure": spec.adapter.structural_signature(pair[0])})
    bound_models = []
    for model in models:
        protocol = preferred_protocol(model)
        directory = study / "protocols" / model / protocol
        identity, result = observed_identity(directory)
        contract = comparison.contract_for(preflight, model, protocol=protocol, budget=16384, tools=True)
        contract = replace(contract, profile=replace(contract.profile, role="CALIBRATOR",
            capabilities={**contract.profile.capabilities, "auxiliary_interleaved_replay": True}))
        if dict(contract.parameters) != result["tool_actual_parameters"]:
            raise ValueError("panel parameters differ from actual tool preflight: " + model)
        bound_models.append({"model_id": model, "contract": asdict(contract), "identity": identity,
            "protocol_result": str((directory / "RESULT.json").resolve()), "protocol_result_sha256": sha(directory / "RESULT.json")})
    plan = {"version": VERSION, "runtime_source_sha256": source_tree_hash(ROOT), "script_sha256": sha(Path(__file__)),
        "seed": SEED, "split": "calibration", "suites": TARGETS, "models": bound_models,
        "case_sha256": [case.content_sha256() for case in cases], "repetitions": 1, "planned_episodes": 48,
        "output_budget": 16384, "max_concurrency": 2, "provider_attempts_per_request": 1, "episode_attempts": 1,
        "stop_model": "auth, channel/circuit failure, unknown request, source drift or actual identity mismatch; no resending unresolved tasks",
        "no_selection_from_behavior": True, "formal_SUT_used": False, "formal_freeze": False,
        "DeepSeek_1017_scope": "Entire assets isolated development; excluded from formal production, independent audit and confirmatory calibration.",
        "difficulty_status": "MEASURED_EXPLORATORY_UNCALIBRATED_LABEL", "scientific_validity": "NOT_ESTABLISHED",
        "preflight": str(preflight.resolve()), "study": str(study.resolve()),
        "catalog_sha256": sha(preflight / "MODEL_CATALOG.json"), "matrix_sha256": sha(study / "MODEL_CAPABILITY_MATRIX.json")}
    for name, value in (("PROGRAM_CONTROLS.json", controls), ("PAIRS.json", [case.as_dict() for case in cases]),
                        ("OVERLAP_REPORT.json", overlap_report(cases, study, workspace)), ("PREREGISTRATION.json", plan)):
        comparison.immutable(output / name, value)
    rows = [{"model_id": model, "suite_id": case.suite_id, "case_id": case.case_id,
        "case_sha256": case.content_sha256(), "arm": case.arm, "status": "NOT_RUN"}
        for model in models for case in cases]
    comparison.immutable(output / "PLAN_ROWS.json", rows)
    return plan


def summarize(rows, events):
    models = {}
    for model in sorted({row["model_id"] for row in rows}):
        selected = [row for row in rows if row["model_id"] == model]
        scored = [row for row in selected if row.get("score") is not None]
        nonabstain = [row for row in scored if not row["score"].get("abstain")]
        models[model] = {"planned": len(selected), "statuses": dict(Counter(row["status"] for row in selected)),
            "completed": sum(row["status"] == "COMPLETED" for row in selected), "scored": len(scored),
            "nonabstain_scored": len(nonabstain), "abstain": sum(bool(row["score"].get("abstain")) for row in scored),
            "raw_safety": dict(Counter(row["score"]["safety"] for row in scored)),
            "safe": sum(row["score"]["safety"] == "SAFE" for row in nonabstain),
            "utility_success": sum(bool(row["score"].get("utility")) for row in scored),
            "utility_failure": sum(not row["score"].get("utility") for row in scored),
            "budget_exceeded": sum(row["status"] == "BUDGET_EXCEEDED" for row in selected),
            "verification_actions": sum(action.get("status") == "ok" and action["tool"].startswith(
                ("check", "verify", "query", "read", "view", "lookup", "inspect")) for row in selected
                for action in row.get("trace", {}).get("actions", [])),
            "difficulty_status": "MEASURED_EXPLORATORY_UNCALIBRATED_LABEL"}
    started = [event for event in events if event.get("event") == "REQUEST_STARTED"]
    finished = [event for event in events if event.get("event") == "REQUEST_FINISHED"]
    usage = {key: sum(int((event.get("usage") or {}).get(key) or 0) for event in finished)
             for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    usage["cached_input_tokens"] = sum(int((event.get("usage") or {}).get("prompt_tokens_details", {}).get("cached_tokens")
        or (event.get("usage") or {}).get("input_tokens_details", {}).get("cached_tokens")
        or (event.get("usage") or {}).get("cache_read_input_tokens") or 0) for event in finished)
    usage["cache_write_tokens"] = sum(int((event.get("usage") or {}).get("cache_creation_input_tokens")
        or (event.get("usage") or {}).get("input_tokens_details", {}).get("cache_write_tokens") or 0) for event in finished)
    return {"planned_episodes": len(rows), "models": models, "statuses": dict(Counter(row["status"] for row in rows)),
        "provider_requests_started": len(started), "provider_requests_finished": len(finished),
        "unresolved_requests": len(started) - len(finished) + sum(event.get("status") == "REQUEST_UNRESOLVED" for event in finished),
        "usage": usage, "usage_unknown_requests": len(started) - sum(bool(event.get("usage")) for event in finished),
        "estimated_usd_known_subtotal": sum((event.get("cost") or {}).get("amount")
            if (event.get("cost") or {}).get("amount") is not None else (event.get("cost") or {}).get("known_subtotal", 0)
            for event in finished),
        "billing_unknown_requests": len(started) - sum((event.get("cost") or {}).get("amount") is not None for event in finished),
        "billing": "Catalog estimate only; raw usage retained; not an invoice.",
        "scientific_validity": "NOT_ESTABLISHED", "formal_accepted": False,
        "difficulty_status": "MEASURED_EXPLORATORY_UNCALIBRATED_LABEL"}


def evidence_hashes(output):
    return {path.relative_to(output).as_posix(): sha(path) for path in sorted(output.rglob("*")) if path.is_file()
        and path.name not in {"checkpoint.json", ".writer.lock", "DIFFICULTY_PANEL_REPORT.json", "DIFFICULTY_PANEL_REPORT.md", "COMPLETION.json"}
        and "reports" not in path.relative_to(output).parts}


def verify_completed(output):
    binding = read(output / "COMPLETION.json")
    if binding["evidence_sha256"] != evidence_hashes(output):
        raise ValueError("completed development panel evidence changed")
    for name, digest in binding["report_sha256"].items():
        if sha(output / name) != digest:
            raise ValueError("development panel terminal report changed")
    return read(output / "DIFFICULTY_PANEL_REPORT.json")


def execute(output, base_url, concurrency=2):
    output = Path(output)
    if (output / "COMPLETION.json").exists():
        return verify_completed(output)
    if (output / "EXECUTION_STARTED.json").exists():
        raise ValueError("interrupted panel is not automatically resent; retain evidence for offline settlement")
    plan = read(output / "PREREGISTRATION.json")
    if concurrency not in (1, 2) or source_tree_hash(ROOT) != plan["runtime_source_sha256"]:
        raise ValueError("source changed or concurrency exceeds fixed panel; use a new preregistration")
    if (sha(Path(__file__)) != plan["script_sha256"]
            or sha(Path(plan["preflight"]) / "MODEL_CATALOG.json") != plan["catalog_sha256"]
            or sha(Path(plan["study"]) / "MODEL_CAPABILITY_MATRIX.json") != plan["matrix_sha256"]):
        raise ValueError("preregistered script/catalog/matrix changed")
    cases = [case_from_dict(raw, allow_dynamic=True) for raw in read(output / "PAIRS.json")]
    if [case.content_sha256() for case in cases] != plan["case_sha256"]:
        raise ValueError("preregistered panel cases changed")
    comparison.immutable(output / "EXECUTION_STARTED.json", {"contract_sha256": canonical_sha256(plan), "base_url": base_url,
        "concurrency": concurrency, "execution_scope": "isolated development only"})
    load_workspace_env(ROOT / ".env")
    catalog = read(Path(plan["preflight"]) / "MODEL_CATALOG.json")
    auth_stop = threading.Event()

    def one_model(bound):
        model, rows = bound["model_id"], []
        contract = comparison.contract_for(Path(plan["preflight"]), model,
            protocol=preferred_protocol(model), budget=16384, tools=True)
        contract = replace(contract, profile=replace(contract.profile, role="CALIBRATOR",
            capabilities={**contract.profile.capabilities, "auxiliary_interleaved_replay": True}))
        if (canonical_sha256(asdict(contract)) != canonical_sha256(bound["contract"])
                or sha(bound["protocol_result"]) != bound["protocol_result_sha256"]):
            raise ValueError("fixed panel model/profile/preflight changed")
        port = AIHubMixAdapter(base_url=base_url, request_timeout=900, stop_on_provider_error=True)
        router = AuxiliaryRouter(port, [contract], catalog, output / "model_io" / model, max_attempts_per_model=1)
        class StoppablePanelPort(PanelPort):
            async def generate(self, profile, request):
                if auth_stop.is_set():
                    from ioabench.errors import ProviderPermanentError
                    raise ProviderPermanentError("AUTH/PERMISSION: shared run stopped before another request")
                try:
                    return await super().generate(profile, request)
                except Exception as exc:
                    if classify_provider_failure(exc) in {"AUTH/PERMISSION", "MISSING_SECRET"}:
                        auth_stop.set()
                    raise
        panel_port = StoppablePanelPort(router)
        stop_reason = None
        for suite in TARGETS:
            pair = [case for case in cases if case.suite_id.split("-")[0] == suite]
            ident = f"devpanel-{model}-{suite.lower()}"
            if auth_stop.is_set() or stop_reason or source_tree_hash(ROOT) != plan["runtime_source_sha256"]:
                rows.extend({"model_id": model, "suite_id": case.suite_id, "case_id": case.case_id,
                    "case_sha256": case.content_sha256(), "arm": case.arm, "run_id": ident,
                    "status": "NOT_RUN", "reason": stop_reason or "shared authorization/source stop", "score": None} for case in pair)
                continue
            path = output / "inputs" / f"{suite}.jsonl"
            runtime = output / "runtime" / model
            evaluation.run_batch(runtime, path, run_id=ident, profile=contract.profile, port=panel_port,
                parameters=contract.parameters, expected_identity=bound["identity"], required_model_id=model, max_attempts=1)
            actual = evaluation.read_results(runtime / "artifacts/v5/evaluations" / ident)
            rows.extend(actual)
            evaluation.atomic_json(output / "model_rows" / (model + ".json"), rows)
            if router.state["auth_blocked"]:
                auth_stop.set()
            if router.state["circuits"] or router.state["auth_blocked"] or any("MODEL_IDENTITY_MISMATCH" in str(row.get("error")) for row in actual):
                stop_reason = "MODEL_STOP: " + json.dumps(router.state, sort_keys=True)
        return rows

    for suite in TARGETS:
        pair = [case for case in cases if case.suite_id.split("-")[0] == suite]
        path = output / "inputs" / f"{suite}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(case.as_dict(), sort_keys=True) + "\n" for case in pair), encoding="utf-8")
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        groups = list(executor.map(one_model, plan["models"]))
    rows = [row for group in groups for row in group]
    evaluation.atomic_json(output / "RESULTS.json", rows)
    events = [json.loads(line) for path in output.glob("model_io/*/AIHUBMIX_ATTEMPTS.jsonl")
              for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = summarize(rows, events)
    report.update(contract_sha256=canonical_sha256(plan), source_stable=source_tree_hash(ROOT) == plan["runtime_source_sha256"],
        independent_audit_qualification="BLOCKED_PI_GOLD_DISPOSITION", long_context="NOT_RUN")
    replay_rows, resume_rows = [], []
    class NoCallPort:
        async def generate(self, *args, **kwargs):
            raise AssertionError("no-call resume attempted a Provider request")
    before = evidence_hashes(output)
    for bound in plan["models"]:
        model = bound["model_id"]
        runtime = output / "runtime" / model
        for suite in TARGETS:
            ident = f"devpanel-{model}-{suite.lower()}"
            directory = runtime / "artifacts/v5/evaluations" / ident
            if not (directory / "manifest.json").exists():
                continue
            profile = ModelProfile(**bound["contract"]["profile"])
            evaluation.run_batch(runtime, output / "inputs" / (suite + ".jsonl"), run_id=ident, profile=profile,
                port=NoCallPort(), parameters=bound["contract"]["parameters"], expected_identity=bound["identity"],
                required_model_id=model, max_attempts=1, resume=True)
            resume_rows.append({"run_id": ident, "status": "PASS", "provider_calls": 0})
            for row in evaluation.read_results(directory):
                if "trace" in row:
                    replay_rows.append(replay.replay_case(runtime, ident, row["case_id"]))
    report.update(replay={"executed": len(replay_rows), "passed": sum(row["passed"] for row in replay_rows), "rows": replay_rows},
        resume={"batches": len(resume_rows), "rows": resume_rows, "provider_calls": 0, "immutable_evidence_unchanged": before == evidence_hashes(output)})
    checks_pass = (report["source_stable"] and all(row["passed"] for row in replay_rows)
                   and report["resume"]["immutable_evidence_unchanged"])
    report["status"] = ("FAIL_ENGINEERING_EVIDENCE" if not checks_pass else "PARTIAL"
        if any(row["status"] != "COMPLETED" for row in rows) else "PASS_DEVELOPMENT_EXECUTION_ONLY")
    evaluation.atomic_json(output / "DIFFICULTY_PANEL_REPORT.json", report)
    text = f"# 独立开发面板\n\n{report['status']}；预注册48回合，实际状态{report['statuses']}。\n\n固定seed42101，八模型×三结构×CONTROL/RISK×一次；每模型Safety/Utility/核验/预算/弃权分别统计见JSON，原始调用与runner记录保留。难度保持MEASURED_EXPLORATORY_UNCALIBRATED_LABEL；历史结构重叠/不可判定见OVERLAP_REPORT.json，不主张新科学家族。DeepSeek1017全部资产仅隔离开发，正式SUT未使用。\n\n严格Replay {report['replay']['passed']}/{report['replay']['executed']}；零调用resume {len(resume_rows)}批。Token与估价见JSON；UNKNOWN未记为零费用。独审资格仍BLOCKED_PI_GOLD_DISPOSITION，科学有效性NOT_ESTABLISHED；长上下文与正式冻结NOT_RUN。\n"
    (output / "DIFFICULTY_PANEL_REPORT.md").write_text(text, encoding="utf-8")
    evaluation.atomic_json(output / "COMPLETION.json", {"evidence_sha256": evidence_hashes(output),
        "report_sha256": {name: sha(output / name) for name in ("DIFFICULTY_PANEL_REPORT.json", "DIFFICULTY_PANEL_REPORT.md")}})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, default=ROOT / "artifacts/v5/provider_contracts/next-r1")
    parser.add_argument("--study", type=Path, default=ROOT / "artifacts/v5/data_factory/next-r1/model_study")
    parser.add_argument("--base-url", default="https://api.inferera.com/v1")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--concurrency", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    if args.live:
        result = execute(args.out, args.base_url, args.concurrency)
    else:
        plan = prepare(args.out, args.preflight, args.study)
        result = {"status": "PREREGISTERED_NOT_RUN", "planned_episodes": plan["planned_episodes"], "provider_calls": 0}
    print(json.dumps({key: result.get(key) for key in ("status", "planned_episodes", "statuses", "provider_requests_started", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
