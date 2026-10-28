"""Evidence-driven C0-C7 closure; no historical receipt is rewritten.

`checks` executes fresh final-source reference runs and Strict Replay without
network. `report` retains every first opportunity and repair. `package` exports
the actual dirty workspace, not a git archive falsely presented as that source.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts/v5")]
RUN = ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1"
OUT = RUN / "closure"
EXPORT = ROOT / "exports/codex-r3-closure-20261025"

from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.evaluation import atomic_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def identity():
    return {"git_head": git("rev-parse", "HEAD").decode().strip(),
            "working_tree_diff_sha256": hashlib.sha256(git("diff", "--binary")).hexdigest(),
            "runtime_source_sha256": source_tree_hash(ROOT)}


def attempts():
    result, seen = [], set()
    for path in sorted(RUN.glob("**/candidates/*/RESULT.json")):
        value = read(path)
        candidate = path.parent.name
        if candidate in seen:
            continue
        seen.add(candidate)
        admission = path.parent.parent.parent / "reviews" / candidate / "ADMISSION.json"
        result.append({"candidate": candidate, "directory": path.parent,
                       "result": value, "admission": read(admission) if admission.exists() else {}})
    return result


def ledger_inventory():
    receipts, requests, errors = [], [], []
    for path in sorted(RUN.rglob("REQUEST_LEDGER.jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        previous = ""
        for row in rows:
            if row.get("previous_event_sha256") != previous or row.get("event_sha256") != canonical_sha256(
                    {key: value for key, value in row.items() if key != "event_sha256"}):
                errors.append(path.relative_to(ROOT).as_posix())
            previous = row.get("event_sha256")
        for intent in (row for row in rows if row["event"] == "REQUEST_INTENT"):
            terminal = [row for row in rows if row["event"] in {"REQUEST_FINISHED", "REQUEST_FAILED"}
                        and row.get("request_id") == intent["request_id"]
                        and row.get("directory") == intent["directory"]]
            end = terminal[-1] if terminal else {}
            response_path = path.parent / intent["directory"] / intent["request_id"] / "RESPONSE.json"
            saved = read(response_path) if response_path.exists() else {}
            response = saved.get("response", saved)
            elapsed = ((datetime.fromisoformat(end["at_utc"]) - datetime.fromisoformat(intent["at_utc"])).total_seconds()
                       if end else None)
            requests.append({"ledger": path.relative_to(ROOT).as_posix(),
                             "directory": intent["directory"], "request_id": intent["request_id"],
                             "parameters": intent["parameters"], "started": intent["at_utc"],
                             "terminal": end.get("event", "INTENT_WITHOUT_TERMINAL"),
                             "category": end.get("category"), "usage": end.get("usage", {}),
                             "finish_reason": response.get("finish_reason"),
                             "requested_model": intent.get("model"),
                             "served_model_id": end.get("served_model_id"),
                             "gateway_header_model": end.get("gateway_header_model"),
                             "elapsed_seconds": elapsed, "transport": end.get("transport", {})})
        receipts.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "events": len(rows)})
    inventory = {"ledgers": receipts, "requests": requests, "chain_errors": errors,
                 "intents": len(requests), "terminal_counts": dict(Counter(r["terminal"] for r in requests)),
                 "unknown": [r for r in requests if r["terminal"] == "INTENT_WITHOUT_TERMINAL"
                             or r["category"] in {"UNKNOWN", "REQUEST_UNRESOLVED"}],
                 "old_unknown_resend_allowed": False}
    atomic_json(OUT / "REQUEST_INVENTORY.json", inventory)
    return inventory


def ab_results(inventory):
    from ioabench.v5.ai_generation.workflow_novelty import canonical_graph, workflow_graph
    frozen = read(RUN / "TASK_SET_FROZEN_R3.json")
    known = attempts()
    fields = ["frozen_task_id", "suite", "route", "candidate", "cohort", "first_attempt_id",
              "status", "failed_stage", "admission", "request_intents", "elapsed_seconds",
              "bounded_request_repairs", "first_request_engineering_pass",
              "source_sha256", "base_url", "protocol_stratum", "workflow_family_id", "evidence"]
    rows, violations = [], []
    for task in frozen["tasks"]:
        for route, suffix in (("compositional_r3", "-C"), ("tree_ir_runtime_v2", "-R")):
            original = task["id"] + suffix
            group = [entry for entry in known if entry["result"].get("route") == route
                     and entry["candidate"].startswith(task["id"])
                     and not any(entry["candidate"].startswith(other["id"])
                                 for other in frozen["tasks"] if len(other["id"]) > len(task["id"]))]
            if not any(entry["candidate"] == original for entry in group):
                rows.append({"frozen_task_id": task["id"], "suite": task["suite"], "route": route,
                             "candidate": original, "first_attempt_id": original,
                             "cohort": "first_opportunity", "status": "NOT_RUN", "request_intents": 0})
            for entry in group:
                result, directory = entry["result"], entry["directory"]
                manifest = read(directory / "MANIFEST.json")
                for key in ("suite", "seed", "difficulty", "target", "industry", "assertions", "plan_focus", "effort"):
                    if manifest["task"].get(key) != task.get(key):
                        violations.append({"candidate": entry["candidate"], "field": key})
                calls = [r for r in inventory["requests"] if entry["candidate"] in r["directory"].split("/")]
                repair_calls = sum(r["request_id"].endswith(("-repair-1", "-format-fix-1")) for r in calls)
                binding_path = directory / "BUSINESS_BINDING.json"
                family = canonical_graph(workflow_graph(read(binding_path)))["family_id"] if binding_path.exists() else None
                stratum = canonical_sha256({"source": manifest["source_sha256"],
                                           "policy": manifest["development_policy"],
                                           "factory": manifest["version"]})
                rows.append({"frozen_task_id": task["id"], "suite": task["suite"], "route": route,
                             "candidate": entry["candidate"], "first_attempt_id": original,
                             "cohort": "first_opportunity" if entry["candidate"] == original else "post_fix_or_repair",
                             "status": result["status"], "failed_stage": result.get("failed_stage"),
                             "admission": entry["admission"].get("status"), "request_intents": len(calls),
                             "elapsed_seconds": sum(r["elapsed_seconds"] or 0 for r in calls),
                             "bounded_request_repairs": repair_calls,
                             "first_request_engineering_pass": result["status"] == "PASS" and repair_calls == 0,
                             "source_sha256": manifest["source_sha256"],
                             "base_url": manifest["development_policy"]["base_url"],
                             "protocol_stratum": stratum, "workflow_family_id": family,
                             "evidence": directory.relative_to(ROOT).as_posix()})
    with (OUT / "R3_AB_RESULTS.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)
    funnel_fields = ["cohort", "route", "status", "failed_stage", "admission"]
    funnel = Counter(tuple(row.get(key) or "" for key in funnel_fields) for row in rows)
    with (OUT / "FAILURE_FUNNEL_ALL.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([*funnel_fields, "count"])
        writer.writerows([*key, count] for key, count in sorted(funnel.items()))
    first = [r for r in rows if r["cohort"] == "first_opportunity"]
    assert len(first) == 36
    stats = {"matched_opportunities": 18, "route_opportunities": 36,
             "first_outcomes": dict(Counter(r["status"] for r in first)),
             "repairs": len(rows) - 36, "per_suite_route": {}, "contract_violations": violations,
             "task_set_file_sha256": sha(RUN / "TASK_SET_FROZEN_R3.json"),
             "protocol_strata": {stratum: {"first_opportunities": sum(r.get("protocol_stratum") == stratum for r in first),
                                "routes": sorted({r["route"] for r in first if r.get("protocol_stratum") == stratum})}
                                  for stratum in sorted({r["protocol_stratum"] for r in first if r.get("protocol_stratum")})},
             "coverage_complete": not violations and all(r["status"] != "NOT_RUN" for r in first),
             "causal_superiority_claim": False}
    lines = ["# R3 A/B: frozen opportunities, not a causal superiority claim", "",
             "The original treatment and closure baseline use different source/endpoint checkpoints.",
             "This protocol drift is explicit: original first outcomes and post-fix repairs are NEVER pooled.",
             "NOT_RUN, static rejection, provider failure and UNKNOWN stay in their denominators.", "",
             "| Suite | Route | Opportunities | Engineering PASS | DEV_ACCEPTED | NOT_RUN |", "|---|---|---:|---:|---:|---:|"]
    for suite in ("T321", "T331", "T362"):
        for route in ("compositional_r3", "tree_ir_runtime_v2"):
            group = [r for r in first if r["suite"] == suite and r["route"] == route]
            stat = {"opportunities": len(group), "engineering_pass": sum(r["status"] == "PASS" for r in group),
                    "dev_accepted": sum(r.get("admission") == "DEV_ACCEPTED" for r in group),
                    "not_run": sum(r["status"] == "NOT_RUN" for r in group),
                    "request_intents": sum(r["request_intents"] for r in group)}
            stat["first_request_engineering_pass"] = sum(bool(r.get("first_request_engineering_pass")) for r in group)
            stat["bounded_repair_requests"] = sum(r.get("bounded_request_repairs", 0) for r in group)
            stat["mean_requests_per_opportunity"] = stat["request_intents"] / len(group)
            stat["sent_opportunities"] = sum(r["request_intents"] > 0 for r in group)
            valid = [r for r in group if r["status"] == "PASS"]
            stat["workflow_graph_families"] = len({r["workflow_family_id"] for r in valid if r.get("workflow_family_id")})
            stat["graph_families_per_valid_candidate"] = stat["workflow_graph_families"] / len(valid) if valid else None
            stat["engineering_rate_all_opportunities"] = stat["engineering_pass"] / len(group)
            stat["admission_rate_all_opportunities"] = stat["dev_accepted"] / len(group)
            stat["elapsed_request_seconds"] = sum(r.get("elapsed_seconds", 0) for r in group)
            stat["mean_requests_per_valid_candidate"] = stat["request_intents"] / len(valid) if valid else None
            candidates = {r["candidate"] for r in group}
            calls = [r for r in inventory["requests"] if candidates.intersection(r["directory"].split("/"))]
            stat["request_outcomes"] = dict(Counter("UNKNOWN" if r.get("category") in {"UNKNOWN", "REQUEST_UNRESOLVED"}
                or r["terminal"] == "INTENT_WITHOUT_TERMINAL" else r["terminal"] for r in calls))
            stat["length_finishes"] = sum(r.get("finish_reason") == "length" for r in calls)
            stats["per_suite_route"][suite + "/" + route] = stat
            lines.append(f"| {suite} | {route} | {len(group)} | {stat['engineering_pass']} | {stat['dev_accepted']} | {stat['not_run']} |")
    lines += ["", "Engineering PASS counts completed candidate lifecycles; request-level bounded repairs are separately recorded in CSV and AB_SUMMARY.json, not called first-request success.",
              "Full failures, request usage/latency and unresolved IDs: REQUEST_INVENTORY.json.",
              "Workflow graph richness/closure eligibility: WORKFLOW_NOVELTY_AUDIT.json, separately from mechanism signatures.",
              "AB_SUMMARY.json reports source/policy/factory strata, graph families per valid candidate, actual request time, truncation and failure denominators. Source strata are not pooled into a causal effect.",
              "Same-model high/max review is development review only. No significance or independent-science claim."]
    (OUT / "R3_AB_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    atomic_json(OUT / "AB_SUMMARY.json", stats)
    return stats


def checks():
    from ioabench.v5.ai_generation.direct_deepseek import strict_checks
    from ioabench.v5.ai_generation.pipeline import suite_spec
    from ioabench.v5.core.case import case_from_dict
    from tf_r3_pool_index import main as pool_index
    binding = identity()
    reference_scope = binding["git_head"] + "-" + canonical_sha256(binding)[:16]
    pool_index()
    pool = {row["candidate"]: row for row in read(RUN / "WORKFLOW_NOVELTY_AUDIT.json")["rows"]}
    records = []
    for entry in attempts():
        if entry["result"]["status"] != "PASS" or not entry["candidate"].startswith("R3-"):
            continue
        source = entry["directory"]
        result = read(source / "RESULT.json")
        pair = [case_from_dict(case, allow_dynamic=True) for case in read(source / "PAIR.json")]
        compiled = {case.arm.lower(): case for case in pair}
        compiled["seed"] = result["task"]["seed"]
        directory = OUT / "final_reference" / reference_scope / entry["candidate"]
        directory.mkdir(parents=True, exist_ok=True)
        spec = suite_spec(result["task"]["suite"], typed=True)
        resumed = [policy for policy in spec.policies if (directory / "strict/artifacts/v5/evaluations" /
                   f"strict-{compiled['seed']}-{policy}" / "manifest.json").exists()]
        count = strict_checks(directory, spec, compiled)
        records.append({"candidate": entry["candidate"], "strict_replays": count, "passed": count >= 6,
                        "closure_pool_eligible": pool.get(entry["candidate"], {}).get("closure_eligible", False),
                        "mode": ("FINAL_SOURCE_BOUND_REFERENCE_RESUME_THEN_STRICT_REPLAY" if resumed else
                                 "FINAL_SOURCE_REFERENCE_REEXECUTION_THEN_STRICT_REPLAY"),
                        "resumed_reference_policies": resumed,
                        "fresh_reference_policies": [policy for policy in spec.policies if policy not in resumed],
                        "historical_receipts_unchanged": True, "provider_calls": 0,
                        "evidence": directory.relative_to(ROOT).as_posix()})
    assert identity() == binding, "source changed during final reference checks"
    atomic_json(OUT / "FINAL_STRICT_REPLAY.json", {
        **binding, "status": "PASS" if records and all(r["passed"] for r in records) else "PARTIAL",
        "records": records, "strict_replays": sum(r["strict_replays"] for r in records), "provider_calls": 0})
    novelty_counterexamples()


def novelty_counterexamples():
    from copy import deepcopy
    from ioabench.v5.ai_generation.workflow_novelty import workflow_graph, isomorphism
    from tests.v5.test_workflow_composition_r3 import (
        MEDICINE_LINEAR3, FINANCE_LINEAR3, MEDICINE_LINEAR4, MEDICINE_FORK_JOIN, _compile)
    graphs = {}
    for key, plan in (("medicine", MEDICINE_LINEAR3), ("finance", FINANCE_LINEAR3),
                      ("extended", MEDICINE_LINEAR4), ("fork", MEDICINE_FORK_JOIN)):
        binding, errors = _compile(plan, "T321", ("integration_agent",))
        assert not errors
        graphs[key] = workflow_graph(binding)
    original = graphs["medicine"]
    renamed = {"nodes": {"x" + sid: label for sid, label in reversed(list(original["nodes"].items()))},
               "edges": [("x" + a, "x" + b, kind) for a, b, kind in reversed(original["edges"])]}
    causal = deepcopy(original)
    causal["edges"] = [edge for edge in causal["edges"] if edge[2] != "receipt"]
    tests = []
    for label, other, expected in (("renamed_and_reordered", renamed, True),
                                   ("equivalent_industry_tools", graphs["finance"], True),
                                   ("causal_receipt_removed", causal, False),
                                   ("extra_real_action", graphs["extended"], False),
                                   ("fork_join", graphs["fork"], False)):
        mapping = isomorphism(original, other)
        tests.append({"case": label, "expected_isomorphic": expected,
                      "observed_isomorphic": mapping is not None, "node_mapping": mapping,
                      "passed": (mapping is not None) == expected})
    ablation = read(OUT / "ablation/R3_ABLATION.json")
    branches = ablation["structure_changes"]["conditional_branch_execution"]
    tests.append({"case": "conditional_untaken_not_claimed_as_executed", "passed":
                  all(({"s3", "s4"} <= set(row["executed_stages"])) == row["taken"] for row in branches),
                  "real_trace_observations": branches})
    atomic_json(OUT / "NOVELTY_COUNTEREXAMPLES.json", {
        **identity(), "status": "PASS" if all(row["passed"] for row in tests) else "FAIL",
        "tests": tests, "mode": "metamorphic_graph_checks_plus_actual_ablation_episodes",
        "real_execution_trace_refs": [p.relative_to(ROOT).as_posix() for p in (OUT / "ablation").glob("*TRACE.json")]})


def zero_call_resume():
    import tf_r3_pilot as pilot
    from ioabench.models.aihubmix import AIHubMixAdapter
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in RUN.rglob("REQUEST_LEDGER.jsonl")}
    blocked = []

    async def forbidden(*args, **kwargs):
        blocked.append("provider invocation attempted")
        raise AssertionError("provider forbidden during terminal resume")

    original = AIHubMixAdapter.generate, AIHubMixAdapter.discover_models
    AIHubMixAdapter.generate = AIHubMixAdapter.discover_models = forbidden
    try:
        asyncio.run(pilot.phase_closure())
        pilot.TASKS = read(RUN / "TASK_SET_FROZEN_R3.json")["tasks"]
        try:
            asyncio.run(pilot.phase_run(RUN / "closure/baseline_online", "ab", (pilot.BASELINE,), limit=0))
        except ValueError as exc:
            if "study stopped; no new paid requests" not in str(exc):
                raise
    finally:
        AIHubMixAdapter.generate, AIHubMixAdapter.discover_models = original
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in RUN.rglob("REQUEST_LEDGER.jsonl")}
    proof = {"status": "PASS" if before == after and not blocked else "FAIL", **identity(),
             "ledger_sha256_before": before, "ledger_sha256_after": after,
             "provider_calls": 0, "provider_attempts_blocked": len(blocked),
             "global_stop_guards_preserved": [p.relative_to(ROOT).as_posix() for p in RUN.rglob("STOP.json")],
             "actual_cached_runner_functions_executed": ["phase_closure", "phase_run baseline limit=0"]}
    atomic_json(OUT / "ZERO_NETWORK_RESUME.json", proof)
    if proof["status"] != "PASS":
        raise ValueError("terminal resume was not zero-call/ledger-stable")


def report():
    from ioabench.v5.ai_generation.aihubmix_study import BUDGET_GATE_ENABLED
    inventory = ledger_inventory()
    ab = ab_results(inventory)
    novelty = read(RUN / "WORKFLOW_NOVELTY_AUDIT.json")
    protection = read(OUT / "HISTORY_PROTECTION_FINAL.json")
    replay = read(OUT / "FINAL_STRICT_REPLAY.json") if (OUT / "FINAL_STRICT_REPLAY.json").exists() else {}
    junit_path = OUT / "FULL_REGRESSION_FINAL.xml"
    junit = ElementTree.parse(junit_path).getroot() if junit_path.exists() else None
    suites = list(junit.iter("testsuite")) if junit is not None else []
    test_status = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    binding_path = OUT / "FULL_REGRESSION_FINAL_BINDING.json"
    test_binding = read(binding_path) if binding_path.exists() else {}
    tests_pass = (bool(test_status["tests"]) and not (test_status["failures"] or test_status["errors"])
                  and all(test_binding.get(key) == value for key, value in identity().items())
                  and test_binding.get("junit_sha256") == sha(junit_path))
    contract = read(OUT / "online/PROVIDER_CONTRACT_CLOSURE_V2.json")
    counterexamples = read(OUT / "NOVELTY_COUNTEREXAMPLES.json") if (OUT / "NOVELTY_COUNTEREXAMPLES.json").exists() else {}
    resume = read(OUT / "ZERO_NETWORK_RESUME.json") if (OUT / "ZERO_NETWORK_RESUME.json").exists() else {}
    ablation_path = OUT / "ablation/R3_ABLATION.json"
    ablation = read(ablation_path) if ablation_path.exists() else {}
    red_path = OUT / "WITNESS_RED.xml"
    red_cases = list(ElementTree.parse(red_path).getroot().iter("testcase")) if red_path.exists() else []
    red_verified = len(red_cases) == 2 and all(
        row.get("name", "").startswith("test_empty_assertions_still_enforce_real_business_witnesses")
        and row.find("failure") is not None for row in red_cases)
    closure_requests = [r for r in inventory["requests"] if "/closure/" in r["ledger"]]
    completed_requests = [r for r in closure_requests if r["terminal"] == "REQUEST_FINISHED"]
    unknown_candidates_admitted = [entry["candidate"] for entry in attempts()
        if entry["admission"].get("status") == "DEV_ACCEPTED" and any(
            entry["candidate"] in row["directory"].split("/") for row in inventory["unknown"])]
    intent_counts = Counter(r["request_id"] for r in inventory["requests"])
    quality = {"request_intents": len(closure_requests), "complete_responses": len(completed_requests),
               "complete_response_rate": len(completed_requests) / len(closure_requests) if closure_requests else None,
               "terminal_counts": dict(Counter(r["terminal"] for r in closure_requests)),
               "usage": {key: sum(r["usage"].get(key, 0) for r in completed_requests)
                         for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
               "length_finishes": sum(r.get("finish_reason") == "length" for r in closure_requests),
               "parameters_valid": bool(closure_requests) and all(
                   r["parameters"].get("max_tokens") in {131072, 262144, 393216}
                   and r["parameters"].get("reasoning_effort") in {"high", "max"}
                   and r["parameters"].get("stream") is True for r in closure_requests),
               "successful_terminal_identity_usage_valid": bool(completed_requests) and all(
                   r["transport"].get("sse_terminal_complete") is True and r["usage"]
                   and (r["served_model_id"] == "deepseek-v4.1-flash-1017" or
                        r["gateway_header_model"] == "deepseek-v4.1-flash-1017") for r in completed_requests),
               "unknowns_remain_quarantined": not unknown_candidates_admitted,
               "unknown_candidates_admitted": unknown_candidates_admitted,
               "unresolved_ids_with_multiple_intents": sorted({r["request_id"] for r in inventory["unknown"]
                                                              if intent_counts[r["request_id"]] > 1}),
               "budget_gate_enabled": BUDGET_GATE_ENABLED,
               "long_context_boundary_tested": False}
    atomic_json(OUT / "MODEL_QUALITY_AUDIT.json", quality)
    package_path = EXPORT / "PACKAGE_VERIFICATION.json"
    package_receipt = read(package_path) if package_path.exists() else {}
    packaged = package_receipt.get("status") == "PASS" and all(
        package_receipt.get(key) == value for key, value in identity().items()) and bool(package_receipt.get("packages"))
    if packaged:
        packaged = all((EXPORT / value["file"]).is_file() and sha(EXPORT / value["file"]) == value["sha256"]
                       for value in package_receipt["packages"].values())
    gates = {"C0": "PASS" if (OUT / "R3_RESUME_STATE.json").exists() else "FAIL",
             "C1": "PASS" if tests_pass and red_verified else "PARTIAL",
             "C2": "PASS" if len(novelty["historical_compatibility"]) == 17 and counterexamples.get("status") == "PASS" else "PARTIAL",
             "C3": "PASS" if all(novelty["per_suite"][s]["meets_goal"] for s in ("T321", "T331", "T362")) else "PARTIAL",
             "C4": "PASS" if contract["status"] == "PASS" and not inventory["chain_errors"] and
                   quality["parameters_valid"] and quality["successful_terminal_identity_usage_valid"] and
                   quality["unknowns_remain_quarantined"] and not quality["budget_gate_enabled"] and
                   not quality["unresolved_ids_with_multiple_intents"] else "PARTIAL",
             "C5": "PASS" if ab["coverage_complete"] and ablation.get("status") == "PASS" and
                   ablation.get("runtime_source_sha256") == source_tree_hash(ROOT) else "PARTIAL",
             "C6": "PASS" if tests_pass and replay.get("status") == "PASS" and
                   all(replay.get(key) == value for key, value in identity().items()) and
                   protection["files_checked"] > 0 and not protection["mismatches"] and
                   resume.get("status") == "PASS" and
                   all(resume.get(key) == value for key, value in identity().items()) else "PARTIAL",
             "C7": "PASS" if packaged else "PARTIAL"}
    status = {"contract": "docs/plans/codex_r3_closure_20261025/GOAL.md#C0-C7", **identity(),
              "status": "COMPLETED" if all(v == "PASS" for v in gates.values()) else "PARTIAL",
              "gates": gates, "tests": test_status, "novelty": novelty["per_suite"], "ab": ab,
              "requests": {k: inventory[k] for k in ("intents", "terminal_counts", "unknown", "chain_errors")},
              "strict_replays": replay.get("strict_replays", 0), "protected_files": protection["files_checked"],
              "formal_accepted": False, "same_model_audit_independent_science": False,
              "simulation_only": ["T361", "T362", "T363"],
              "limits": (["C3 is short of two accepted pairs and two executed families in at least one suite."] if gates["C3"] != "PASS" else []) +
                        (["C5 has missing first-opportunity outcomes or frozen-task field violations."] if gates["C5"] != "PASS" else []) +
                        [f"{len(inventory['unknown'])} historical/current POST terminals remain unknown and are never resent.",
                         "Original first treatment and closure baseline span source/prompt checkpoints; strata are explicit and no causal superiority or significance is claimed.",
                         "Legacy admissions with unconsumed plan edges are retained but excluded from closure eligibility.",
                         "Final-source reference reexecution is not a false claim of restoring unavailable historical source snapshots."]}
    atomic_json(OUT / "R3_GOAL_STATUS.json", status)
    lines = ["# R3 closure - actual results", "", f"Status: {status['status']}",
             f"HEAD: {status['git_head']}", f"Runtime: {status['runtime_source_sha256']}", "",
             "## Gates", *[f"- {key}: {value}" for key, value in gates.items()], "",
             "## Repairs and evidence",
             "- Empty assertions no longer bypass business witnesses; real end-to-end RED and GREEN JUnit are retained.",
             "- Declared workflow edges now constrain runtime order, handoffs and reference-policy readiness.",
             "- Exact typed graph canonicalization verifies mappings, not hash inequality; seed truth is not a family.",
             "- Original paid proposals are reused with fresh candidate IDs and explicit provenance, never regenerated silently.",
             "- SSE needs observed DONE, finish, identity and usage; orphan request intents cannot be resent.",
             "- Mainland endpoint works over ordinary HTTPS; no service on a guessed proxy port is selected.", "",
             "## Scope and limits", *["- " + item for item in status["limits"]],
             "- Same DeepSeek high/max audit is DEVELOPMENT_AUTO_AUDITED, not independent scientific validation.",
             "- The 18 mechanisms, Oracle, scorer truth and SIMULATION_ONLY boundaries are not relaxed.", "",
             "## Live call results and review limits",
             f"- Closure: {quality['complete_responses']}/{quality['request_intents']} complete responses; "
             f"terminal counts {json.dumps(quality['terminal_counts'], sort_keys=True)}; "
             f"length finishes {quality['length_finishes']}.",
             f"- Reported completed-response usage: {json.dumps(quality['usage'], sort_keys=True)}. "
             "Unknown-response usage and actual invoice remain unknown.",
             "- Exact model deepseek-v4.1-flash-1017, https://api.inferera.com/v1, high/max, stream=true, "
             "131072 output ceiling used. Neither a 1M-context boundary nor maximum-length generation was tested.",
             "- Network abrupt closes occurred. The endpoint worked for these calls; long-term reliability is unproven.",
             "- Quarantined factual omissions and high/max disagreements remain in ADMISSION/AUDIT_RESULT files; "
             "UNKNOWN is never promoted to accepted. See FAILURE_FUNNEL_ALL.csv and TRANSPORT_FAILURES.json.", "",
             "## Admitted pair and executed graph index",
             "Original admissions remain historical records; closure eligibility requires consumed edges and strict witnesses.",
             "Legacy text-near classifications are retained; exact duplicates and isomorphic text-near instances fail. "
             "The old feature projection omits DAG dependencies; corrected consumed graphs are compared separately.",
             "Historical non-isomorphism scope is the 17 sealed R1/R2 observed executions. Missing DAGs do not prove "
             "anything about unobserved historical grammar.",
             "| Candidate | Suite | Closure eligible | Typed graph family | Evidence directory |",
             "|---|---|---|---|---|",
             *[f"| {row['candidate']} | {row['suite']} | {row['closure_eligible']} | {row['workflow_family_id']} | {row['evidence']} |"
               for row in novelty["rows"]], "",
             "## Frozen comparison and final execution",
             f"- {ab['matched_opportunities']} matched tasks / {ab['route_opportunities']} route opportunities: "
             f"{json.dumps(ab['first_outcomes'], sort_keys=True)}; {ab['repairs']} separate repair candidates; "
             f"{len(ab['contract_violations'])} frozen-field violations.",
             "- First-opportunity route metrics and source/policy strata: R3_AB_REPORT.md and AB_SUMMARY.json. "
             "Bounded request repairs are also separate from first-request engineering success.",
             f"- Final tests: {test_status['tests']} tests, {test_status['failures']} failures, {test_status['errors']} errors, "
             f"{test_status['skipped']} skipped; {status['strict_replays']} Strict Replays across "
             f"{len(replay.get('records', []))} valid candidate pairs; {status['protected_files']} historical files checked.",
             "- FINAL_STRICT_REPLAY.json records fresh/resumed reference policies under the final source identity. "
             "ZERO_NETWORK_RESUME.json records actual stopped-run entry with provider calls forbidden.",
             "- Tree/Composition/Witness ablation results and actual event differences: ablation/R3_ABLATION.json.", "",
             "## Next scope",
             "- If C0-C7 all pass, proceed with staged capability integration in NEXT_15_PRIORITY.md and "
             "SUITE18_CAPABILITY_READINESS.csv. The other 15 suites were not rewritten in this task.",
             "- Scientific independence, difficulty calibration, real human validation, formal dataset freeze and campaign "
             "remain outside this development closure; T361-T363 remain SIMULATION_ONLY.", "",
             "## Navigation", "- ../WORKFLOW_NOVELTY_AUDIT.json and ../R3_DEV_POOL_INDEX.jsonl: pair-level eligibility and graph mappings.",
             "- R3_AB_RESULTS.csv / R3_AB_REPORT.md: all 36 original opportunities plus separate repairs.",
             "- REQUEST_INVENTORY.json: every ledger, unknown terminal, usage and elapsed time.",
             "- FINAL_STRICT_REPLAY.json / HISTORY_PROTECTION_FINAL.json / FULL_REGRESSION_FINAL.xml: executable final checks.",
             "- ablation/R3_ABLATION.json and *TRACE.json: real module/edge ablations; WITNESS_CALIBRATION.json is a synthetic control panel.",
             "- docs/plans/codex_r3_closure_20261025/07_NEXT_15_SUITES.md: staged expansion; no blind 15-suite implementation.", "",
             "Packaging uses current workspace bytes and an external authoritative PACKAGE_VERIFICATION receipt.",
             "Package-contained pre-pack status is superseded only for packaging metadata by the external receipt."]
    (OUT / "R3_CLOSURE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    EXPORT.mkdir(parents=True, exist_ok=True)
    for name in ("R3_GOAL_STATUS.json", "R3_CLOSURE_REPORT.md", "R3_AB_RESULTS.csv", "R3_AB_REPORT.md"):
        (EXPORT / name).write_bytes((OUT / name).read_bytes())
    print(json.dumps({"status": status["status"], "gates": gates, "tests": test_status}, indent=2))


def package():
    from package_development_factory import CODE_FOLDERS, ROOT_FILES, known_secrets, safe_path, scan_blob, selected_file
    secrets = known_secrets()
    tracked = [ROOT / p for p in git("ls-files", "-z").decode("utf-8").split("\0") if p]
    atomic_json(OUT / "SOURCE_BINDING.json", {**identity(),
                "scope": "final_local_commit_plus_preserved_preexisting_dirty_overlay",
                "runtime_tree": "src+contracts+config exact bytes; historical R2 script credential export-only redaction"})
    (OUT / "FINAL_WORKTREE.patch").write_bytes(git("diff", "--binary"))
    sources = {p for p in tracked if p.relative_to(ROOT).parts[0] in CODE_FOLDERS or p.name in ROOT_FILES}
    sources.update(OUT / name for name in ("SOURCE_BINDING.json", "FINAL_WORKTREE.patch", "USER_WORKTREE_START.patch"))
    for directory in ("src", "contracts", "config", "tests", "scripts/v5", "docs/plans/codex_r3_closure_20261025"):
        sources.update(p for p in (ROOT / directory).rglob("*") if p.is_file())
    evidence = {p for p in RUN.rglob("*") if p.is_file()}
    # Include the small, actually verified historical scope, not 200,000 unrelated files.
    protection = read(OUT / "HISTORY_PROTECTION_FINAL.json")
    for group in protection["groups"].values():
        evidence.update(ROOT / p for p in group["sha256_by_file"])
    manifests, zips, redactions = {}, {}, {}
    for kind, files in (("SOURCE", sources), ("EVIDENCE", evidence)):
        path = EXPORT / f"IoA-Bench-v5-Codex-R3-{kind}-REVIEW.zip"
        inventory = {}
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(files):
                if not selected_file(file):
                    continue
                name = file.relative_to(ROOT).as_posix()
                safe_path(name)
                data = file.read_bytes()
                if name == "scripts/v5/tf_r2_finalize.py":
                    from package_workspace_snapshot import KEY_TOKEN
                    original_sha = hashlib.sha256(data).hexdigest()
                    for secret in secrets:
                        data = data.replace(secret, b"[REDACTED_SECRET]")
                    data = KEY_TOKEN.sub(b"[REDACTED_SECRET]", data)
                    if hashlib.sha256(data).hexdigest() != original_sha:
                        redactions[name] = {"local_original_sha256": original_sha,
                                            "export_copy_sha256": hashlib.sha256(data).hexdigest(),
                                            "reason": "historical credential literal; local original and Git history untouched"}
                scan_blob(data, name, secrets)
                inventory[name] = hashlib.sha256(data).hexdigest()
                archive.writestr(name, data)
            redaction_data = json.dumps(redactions, sort_keys=True, indent=2).encode("utf-8")
            archive.writestr("PACKAGE_REDACTIONS.json", redaction_data)
            inventory["PACKAGE_REDACTIONS.json"] = hashlib.sha256(redaction_data).hexdigest()
            archive.writestr("PACKAGE_FILE_SHA256.json", json.dumps(inventory, sort_keys=True, indent=2))
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(inventory) | {"PACKAGE_FILE_SHA256.json"}
            for name, expected in inventory.items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == expected
        manifests[kind] = inventory
        zips[kind] = {"file": path.name, "files": len(inventory), "bytes": path.stat().st_size, "sha256": sha(path)}
    atomic_json(EXPORT / "FILE_SHA256.json", manifests)
    atomic_json(EXPORT / "REDACTIONS.json", redactions)
    with tempfile.TemporaryDirectory(prefix="r3-extracted-", dir=EXPORT) as temporary:
        extracted = Path(temporary).resolve()
        assert extracted.is_relative_to(EXPORT.resolve())
        for meta in zips.values():
            with zipfile.ZipFile(EXPORT / meta["file"]) as archive:
                archive.extractall(extracted)
        assert source_tree_hash(extracted) == source_tree_hash(ROOT)
        proof_path = EXPORT / "EXTRACTED_VERIFICATION.json"
        program = '''
import json, socket, sys
from pathlib import Path
root, proof = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(root / "src"))
from ioabench.models.aihubmix import AIHubMixAdapter
from ioabench.v5.replay import replay_case
def forbidden(*args, **kwargs):
    raise AssertionError("network or provider call during extracted verification")
AIHubMixAdapter.generate = forbidden
AIHubMixAdapter.discover_models = forbidden
AIHubMixAdapter._request_sse = forbidden
AIHubMixAdapter._request_json = forbidden
socket.create_connection = forbidden
result = json.loads((root / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1/closure/FINAL_STRICT_REPLAY.json").read_text())
count = 0
for record in result["records"]:
    base = root / record["evidence"]
    for row in json.loads((base / "STRICT_REFERENCE_RESULTS.json").read_text()):
        check = replay_case(base / "strict", row["run_id"], row["case_id"])
        assert check["passed"], check
        count += 1
assert count > 0
proof.write_text(json.dumps({"status":"PASS","strict_replays":count,"provider_calls":0,"network_disabled":True}, indent=2), encoding="utf-8")
'''
        completed = subprocess.run([sys.executable, "-B", "-c", program, str(extracted), str(proof_path)],
                                   cwd=extracted, capture_output=True, text=True, encoding="utf-8")
        (EXPORT / "EXTRACTED_VERIFICATION.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise ValueError("extracted strict verification failed; see EXTRACTED_VERIFICATION.log")
    atomic_json(EXPORT / "PACKAGE_VERIFICATION.json", {"status": "PASS", **identity(), "packages": zips,
                "checks": ["safe_unique_member_paths", "ZIP_CRC", "every_member_SHA256", "manifest_set_equality",
                           "known_secret_and_token_patterns", "current_workspace_not_git_archive"],
                "extraction_execution": read(proof_path),
                "scientific_acceptance": False})
    atomic_json(EXPORT / "REVIEW_FILE_INDEX.json", {
        "extract_together": [meta["file"] for meta in zips.values()],
        "authoritative_external_status": "R3_GOAL_STATUS.json",
        "archive_report": (OUT / "R3_CLOSURE_REPORT.md").relative_to(ROOT).as_posix(),
        "novelty": (RUN / "WORKFLOW_NOVELTY_AUDIT.json").relative_to(ROOT).as_posix(),
        "pool": (RUN / "R3_DEV_POOL_INDEX.jsonl").relative_to(ROOT).as_posix(),
        "next_15": (OUT / "NEXT_15_PRIORITY.md").relative_to(ROOT).as_posix(),
        "all_members": "FILE_SHA256.json", "redactions": "REDACTIONS.json"})
    report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["checks", "resume", "report", "package"])
    phase = parser.parse_args().phase
    {"checks": checks, "resume": zero_call_resume, "report": report, "package": package}[phase]()
