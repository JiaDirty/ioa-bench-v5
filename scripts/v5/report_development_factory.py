"""Recompute development-pool reports from local evidence; never invokes a provider."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.development import structure_vector
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.evaluation import atomic_json, writer_lock
from package_development_factory import generation_evidence
from verify_round01_readiness import NAMES

VERSION = "ioabench.v5.development-report/1.6.1"


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ledger(path):
    """Verify the chain and retain one denominator per unique submission intent."""
    previous, requests, events = "", {}, []
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        row = json.loads(line)
        unsigned = {key: value for key, value in row.items() if key != "event_sha256"}
        if row["previous_event_sha256"] != previous or canonical_sha256(unsigned) != row["event_sha256"]:
            raise ValueError("request ledger chain changed")
        if row.get("receipt_path"):
            receipt = (path.parent / row["receipt_path"]).resolve()
            if not receipt.is_relative_to(path.parent.resolve()) or not receipt.is_file() or sha(receipt) != row.get("receipt_sha256"):
                raise ValueError("bound response accounting receipt changed")
        previous = row["event_sha256"]
        events.append(row)
        if row["event"] == "REQUEST_INTENT":
            key = (row["directory"], row["request_id"])
            if key in requests:
                raise ValueError("duplicate request intent; inspect no-resend evidence")
            requests[key] = {"intent": row, "finished": None, "failure": None}
        elif row["event"] == "REQUEST_FINISHED":
            key = (row["directory"], row["request_id"])
            if key not in requests or requests[key]["finished"]:
                raise ValueError("completion has no unique bound request intent")
            requests[key]["finished"] = row
        elif row["event"] == "REQUEST_FAILED":
            candidates = [value for (directory, request_id), value in requests.items()
                          if request_id == row["request_id"] and (not row.get("directory") or directory == row["directory"])
                          and (value["finished"] is None or value["finished"].get("status") == "FAILED_WITH_RESPONSE")]
            if not candidates:
                raise ValueError("failure has no bound request intent")
            candidates[-1]["failure"] = row
    return list(requests.values()), events


def category(row):
    directory = row["intent"]["directory"]
    return next((label for prefix, label in (("candidates/", "generation"), ("reviews/", "audit"),
                ("calibration/", "calibration")) if directory.startswith(prefix)), "other")


def cost(rows):
    complete = [row["finished"] for row in rows if row["finished"] is not None and row["finished"].get("status") == "PASS"]
    receipts = [row["finished"] or row["failure"] for row in rows if row["finished"] or row["failure"]]
    costs = [row.get("cost") or {} for row in receipts]
    unknown = len(rows) - len(receipts) + sum(row.get("upper_cny") is None for row in costs)
    lower = sum(row.get("lower_cny") or 0 for row in costs)
    known_upper = sum(row.get("upper_cny") or 0 for row in costs)
    usage_fields = ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
    elapsed = [(row.get("transport") or {}).get("elapsed_seconds") for row in receipts]
    elapsed = [value for value in elapsed if value is not None]
    return {"status": "NOT_RUN" if not rows else "ESTIMATE_WITH_UNKNOWN_BILLING" if unknown else "COMPLETION_USAGE_BOUND",
        "lower_cny": lower, "upper_cny": None if unknown else known_upper,
        "known_completion_upper_cny": known_upper, "requests_without_cost_bound": unknown,
        "request_intents": len(rows), "complete_responses": len(complete), "usage_receipts": len(receipts), "currency": "CNY",
        "usage": {name: sum((row.get("usage") or {}).get(name) or 0 for row in receipts) for name in usage_fields},
        "usage_missing_responses": {name: len(rows) - len(receipts) + sum((row.get("usage") or {}).get(name) is None for row in receipts) for name in usage_fields},
        "reported_reasoning_tokens": sum(((row.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens") or 0 for row in receipts),
        "reasoning_usage_missing_responses": len(rows) - len(receipts) + sum(((row.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens") is None for row in receipts),
        "latency": {"recorded_requests": len(elapsed), "mean_seconds": statistics.mean(elapsed) if elapsed else None,
                    "max_seconds": max(elapsed) if elapsed else None},
        "recorded_budget_reserve_cny": sum(row.get("budget_reserve_cny") or 0 for row in receipts),
        "budget_reserve_is_billed_cost": False,
        "actual_invoice": "UNKNOWN", "basis": "Real completion usage and retained official peak/off-peak cache-aware bounds"}


def add_cost(*values):
    return {"lower_cny": sum(value["lower_cny"] for value in values),
            "upper_cny": None if any(value["upper_cny"] is None for value in values)
            else sum(value["upper_cny"] for value in values)}


def unit(value, denominator):
    return {"denominator": denominator, "lower_cny": value["lower_cny"] / denominator if denominator else None,
        "upper_cny": value["upper_cny"] / denominator if denominator and value["upper_cny"] is not None else None,
        "status": "NO_ACCEPTED_PAIRS" if not denominator else "UNKNOWN_UPPER" if value["upper_cny"] is None else "ESTIMATE_BOUND"}


def source_path(name, out, original_root=None):
    path = Path(name)
    if original_root is not None:
        original = Path(original_root)
        if not original.is_absolute():
            raise ValueError("original-root must be an explicit absolute prefix")
        if path.is_absolute() and not path.is_relative_to(ROOT):
            if not path.is_relative_to(original):
                raise ValueError("source evidence is outside the explicit original-root prefix")
            path = ROOT / path.relative_to(original)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if not (path.is_relative_to(ROOT) or path.is_relative_to(out.resolve())):
        raise ValueError("source evidence escapes the workspace")
    return path


def generation_binding(source, root, out, original_root=None):
    if original_root is None:
        return generation_evidence(source, root)
    # Resolve declared reuse links in memory; never edit packaged provenance or
    # reopen a path in the original checkout. The paid-source receipt logic is shared.
    current, chain, files, seen = source, [], {}, set()
    while (current / "GENERATION_REUSE.json").is_file():
        if current in seen:
            raise ValueError("generation reuse cycle detected")
        seen.add(current)
        chain.append(current.relative_to(root).as_posix())
        for name in ("RESULT.json", "TERMINAL.json", "MANIFEST.json", "GENERATION_STAGES.json", "GENERATION_REUSE.json"):
            if (current / name).is_file():
                files[(current / name).relative_to(root).as_posix()] = sha(current / name)
        reuse = read(current / "GENERATION_REUSE.json")
        if not reuse.get("source_candidate"):
            raise ValueError("generation reuse has no source candidate")
        current = source_path(reuse["source_candidate"], out, original_root)
        if not current.is_relative_to(root):
            raise ValueError("generation reuse source escapes workspace")
        for filename, field in (("RESULT.json", "source_result_sha256"), ("MANIFEST.json", "source_manifest_sha256"),
                                ("GENERATION_STAGES.json", "source_stages_sha256")):
            if reuse.get(field) is not None and (not (current / filename).is_file() or sha(current / filename) != reuse[field]):
                raise ValueError("generation reuse source binding changed: " + filename)
    binding = generation_evidence(current, root)
    return {**binding, "chain_directories": chain + binding["chain_directories"],
            "files": {**files, **binding["files"]}}


def csv_write(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: json.dumps(row[key], ensure_ascii=False, sort_keys=True) if isinstance(row.get(key), (dict, list))
                         else row.get(key, "NOT_RUN") for key in fields} for row in rows)


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def stability(requests):
    windows = {}
    for row in requests:
        stamp = utc(row["intent"]["at_utc"])
        key = stamp.replace(minute=30 * (stamp.minute // 30), second=0, microsecond=0).isoformat()
        windows.setdefault(key, []).append(row)
    rows = []
    for start, values in sorted(windows.items()):
        completed = [row["finished"] for row in values if row["finished"] and row["finished"].get("status") == "PASS"]
        receipts = [row["finished"] or row["failure"] for row in values if row["finished"] or row["failure"]]
        elapsed = [row["transport"]["elapsed_seconds"] for row in receipts
                   if (row.get("transport") or {}).get("elapsed_seconds") is not None]
        rows.append({"window_start_utc": start, "window_minutes": 30, "request_intents": len(values),
            "complete_responses": len(completed), "http_200": sum((row.get("transport") or {}).get("http_status") == 200
                                                                       for row in receipts),
            "failure_categories": dict(Counter(row["failure"]["category"] for row in values if row["failure"])),
            "mean_seconds": statistics.mean(elapsed) if elapsed else None,
            "max_seconds": max(elapsed) if elapsed else None})
    return {"status": "NOT_RUN" if not rows else "OBSERVED_SHORT_WINDOWS", "windows": rows,
        "long_term_stability_established": False, "limitation": "Actual UTC half-hour submission windows only; short runs do not establish long-term reliability."}


def valid_review(review):
    return review.get("validation_errors") == [] and review.get("review", {}).get("verdict") in {"ACCEPT", "REJECT", "UNCERTAIN"}


def invalid_reference(review):
    return any(error.startswith("EVIDENCE_REF") or error == "ACCEPT_EVIDENCE_COVERAGE_INCOMPLETE"
               for error in review.get("validation_errors", []) or [])


def calibration_summary(out):
    calibration = read(out / "AUDIT_CALIBRATION.json", {})
    cases, missing = [], []
    for ordinal, row in enumerate(calibration.get("rows", []), 1):
        path = out / f"calibration/case-{ordinal}/AUDIT_RESULT.json"
        raw = read(path, {})
        reviews = raw.get("reviews", [])
        verdicts = [review.get("review", {}).get("verdict") for review in reviews]
        decisions = len(verdicts) == 2 and verdicts == ["REJECT", "REJECT"]
        contract_valid = len(reviews) == 2 and all(valid_review(review) for review in reviews)
        if not raw:
            missing.append(ordinal)
        cases.append({"ordinal": ordinal, "private_mutation": row.get("private_mutation"),
            "evidence_file": path.relative_to(out).as_posix(), "evidence_sha256": sha(path) if raw else None,
            "verdicts": verdicts, "decision_rejection": decisions,
            "model_rejection_pass": row.get("model_rejection_pass") is True and decisions and contract_valid,
            "hard_gate_rejection_pass": row.get("hard_gate_enforced") is True and bool(raw)
                and raw.get("status") != "DEV_AUTO_AUDITED",
            "verdict_disagreement": len(verdicts) == 2 and None not in verdicts and len(set(verdicts)) > 1,
            "contract_valid_verdict_disagreement": contract_valid and len(set(verdicts)) > 1,
            "contract_failure_responses": sum(not valid_review(review) for review in reviews),
            "invalid_evidence_reference_responses": sum(invalid_reference(review) for review in reviews),
            "validation_error_counts": dict(Counter(error for review in reviews for error in review.get("validation_errors", []) or []))})
    planned, executed = calibration.get("planned", 6), calibration.get("executed", 0)
    model_passes = sum(row["model_rejection_pass"] for row in cases)
    hard_passes = sum(row["hard_gate_rejection_pass"] for row in cases)
    status = "NOT_RUN" if not executed else "PASS" if (
        executed == planned and planned > 0 and len(cases) == executed and not missing
        and model_passes == planned and hard_passes == planned) else "FAIL"
    return {"status": status, "planned": planned, "executed": executed,
        "decision_rejection_passes": sum(row["decision_rejection"] for row in cases),
        "model_rejection_passes": model_passes, "hard_gate_rejection_passes": hard_passes,
        "verdict_disagreements": sum(row["verdict_disagreement"] for row in cases),
        "contract_valid_verdict_disagreements": sum(row["contract_valid_verdict_disagreement"] for row in cases),
        "invalid_evidence_reference_responses": sum(row["invalid_evidence_reference_responses"] for row in cases),
        "contract_failure_responses": sum(row["contract_failure_responses"] for row in cases),
        "decision_rejections_with_invalid_contract": sum(row["decision_rejection"] and row["contract_failure_responses"] > 0 for row in cases),
        "reported_model_rejection_passes": calibration.get("model_rejection_passes"),
        "reported_decision_rejection_passes": calibration.get("decision_rejection_passes"),
        "missing_case_evidence": missing, "cases": cases,
        "definition": "A model rejection pass requires two REJECT reviews with explicit empty validation_errors and a true per-case model_rejection_pass. Decision-only rejection and invalid references never pass calibration."}


def forensic_summary(out, census):
    path = out / "FORENSIC_TRACE_ALIASING.json"
    value = read(path, {})
    if not value:
        return {"status": "NOT_RUN", "affected_pair_ids": [], "pairs": {}}, {}
    if value.get("baseline_sha256") != sha(out / "BASELINE_CENSUS.json"):
        raise ValueError("trace forensic report is bound to a different baseline")
    grouped = {}
    for row in value.get("rows", []):
        grouped.setdefault(row["pair_id"], []).append(row)
    if set(grouped) != {row["id"] for row in census["pairs"]}:
        raise ValueError("trace forensic coverage differs from retained baseline")
    pairs = {}
    for identifier, rows in grouped.items():
        observations = [row["historical_observations"] for row in rows]
        mismatches = sum(len(row["mismatches"]) for row in observations)
        alignment_errors = sum(len(row["alignment_errors"]) for row in observations)
        unobserved = sum(row["not_observed_in_a_later_request"] for row in observations)
        pairs[identifier] = {"status": "CONFIRMED_INCONSISTENCY" if mismatches or alignment_errors else "NO_OBSERVED_CONTRADICTION",
            "reference_rows": len(rows), "mismatched_reference_rows": sum(bool(row["mismatches"]) for row in observations),
            "result_mismatches": mismatches, "alignment_errors": alignment_errors,
            "observed_results_compared": sum(row["compared"] for row in observations),
            "terminal_results_unobserved": unobserved,
            "unobserved_status": "UNKNOWN" if unobserved else "NONE_IN_THIS_RETAINED_SCOPE",
            "affected_tools": dict(Counter(item["tool"] for row in observations for item in row["mismatches"])),
            "current_engine_reanalysis_pass": sum(bool(row.get("current_engine_reanalysis", {}).get("checks"))
                and all(row["current_engine_reanalysis"]["checks"].values()) for row in rows),
            "strict_historical_replay_replaced": False}
    affected = sorted(identifier for identifier, row in pairs.items() if row["status"] == "CONFIRMED_INCONSISTENCY")
    if affected != value.get("affected_pair_ids"):
        raise ValueError("trace forensic affected-pair summary contradicts its rows")
    summary = {"status": "EXECUTED", "file": path.name, "sha256": sha(path),
        "retained_pairs": len(pairs), "reference_rows": sum(row["reference_rows"] for row in pairs.values()),
        "affected_pair_ids": affected, "affected_pairs": len(affected),
        "pairs_without_observed_contradiction": len(pairs) - len(affected),
        "mismatched_reference_rows": sum(row["mismatched_reference_rows"] for row in pairs.values()),
        "result_mismatches": sum(row["result_mismatches"] for row in pairs.values()),
        "terminal_results_unobserved": sum(row["terminal_results_unobserved"] for row in pairs.values()),
        "engine_version": value.get("engine_version"),
        "current_engine_reanalysis_pass": sum(row["current_engine_reanalysis_pass"] for row in pairs.values()),
        "strict_historical_replay_replaced": False, "old_evidence_modified": False,
        "limitation": "Retained-response reanalysis under engine 1.4.4 is not strict replay under the original source and cannot replace fresh versioned execution and review. Any unobserved terminal tool result remains UNKNOWN."}
    return summary, pairs


def t321_design_fidelity(out, original_root=None):
    path = out / "T321_DESIGN_FIDELITY_LIMITATION.json"
    if not path.exists():
        return {"status": "NOT_RUN"}
    value = read(path)
    bindings = value.get("source_bindings")
    if (value.get("version") != "ioabench.v5.t321-design-fidelity-limitation/1.0.0"
            or value.get("verification_status") != "PASS_READ_ONLY_FACT_BINDING"
            or not isinstance(bindings, list) or not bindings):
        raise ValueError("T321 design limitation has no verified source bindings")
    for binding in bindings:
        source = source_path(binding["path"], out, original_root)
        if (not source.is_file() or sha(source) != binding.get("sha256")
                or (binding.get("bytes") is not None and source.stat().st_size != binding["bytes"])):
            raise ValueError("T321 design limitation source binding changed: " + binding["path"])
    return {"status": value["verification_status"], "file": path.name, "sha256": sha(path),
        "candidate_id": value["candidate_id"], "source_bindings_verified": len(bindings),
        "source_bindings": bindings, "findings": value["findings"],
        "original_reviews": value["original_reviews"], "retained_admission_status": value["retained_admission_status"],
        "disposition": value["disposition"], "original_evidence_modified": value["original_evidence_modified"],
        "original_audit_rewritten": value["original_audit_rewritten"],
        "independent_scientific_review": value["independent_scientific_review"]}


def t321_design_note(facts):
    return (f"T321协商污染设计限制（{facts['candidate_id']}）：已核验{facts['source_bindings_verified']}个绑定文件的SHA-256。"
        "三broker、gamma依赖与延迟peer能力释放的声明未落实到实际两broker/initial payload；task_graph仅为声明元数据，不计为执行结构创新。"
        "clean close只进入业务文字，六条原轨迹的最终session均未关闭，不能作为clean-close合规测评证据；旧scorer和分数保留。"
        "deliveries_done是broker消息发布调度计数，与零业务传输并不构成Replay矛盾；原high REJECT、max ACCEPT、分歧和QUARANTINED全部保留。"
        "后续t321-dyna-naive-v2仅修复当前参考策略，不替换原候选、原运行源码、轨迹或审核。详见" + facts["file"] + "。")


def structure_capacity(out):
    """Keep grammar enumeration and planned preflight separate from generated data."""
    capacity = read(out / "STRUCTURE_CAPACITY.json", {})
    allocation = read(out / "COVERAGE_ALLOCATION.json", {})
    allocated = {row["suite"]: row for row in allocation.get("suites", [])}
    rows = {}
    for row in capacity.get("suites", []):
        suite, plan = row["suite"], allocated.get(row["suite"], {})
        bound = row.get("compiled_cell_upper_bound", "NOT_RUN")
        if plan.get("compiled_cell_upper_bound", bound) != bound:
            raise ValueError("structure capacity and allocation disagree: " + suite)
        goal = plan.get("requested_goal", 3)
        below_goal = bound < goal if isinstance(bound, int) else "NOT_RUN"
        if plan.get("goal_unreachable_in_current_finite_grammar", below_goal) != below_goal:
            raise ValueError("structure capacity goal claim disagrees: " + suite)
        rows[suite] = {"capacity_status": "RECORDED_FINITE_GRAMMAR_BOUND",
            "compiled_cell_upper_bound": bound, "requested_structure_goal": goal,
            "goal_unreachable_in_current_finite_grammar": below_goal,
            "finite_axes": row.get("finite_axes", "NOT_RUN"),
            "capacity_basis": row.get("capacity_basis", "NOT_RUN"),
            "capacity_limits": row.get("limits", "NOT_RUN"),
            "reference_verified_planned_cells": row.get("reference_verified_planned_cells", "NOT_RUN"),
            "planned_fresh_cells": plan.get("planned_fresh_cells", "NOT_RUN"),
            "allocation_status": plan.get("status", "NOT_RUN"),
            "allocation_history_scope": plan.get("history_scope", "NOT_RUN")}
    evidence = {name: sha(out / name) for name in ("STRUCTURE_CAPACITY.json", "COVERAGE_ALLOCATION.json")
                if (out / name).exists()}
    return {"status": "RECORDED" if rows else "NOT_RUN", "evidence_sha256": evidence,
        "model_generated_pairs_from_capacity": 0, "accepted_pairs_from_capacity": 0}, rows


def t362_preflight(out):
    path = out / "T362_STRUCTURE_PREFLIGHT.json"
    value = read(path, {})
    fields = ("status", "scope", "provider_calls", "cases_entered_pool", "pairs", "reference_runs",
              "strict_recorded_response_replays", "distinct_structure_cells", "capability_limit")
    return {**{name: value.get(name, "NOT_RUN") for name in fields},
        "file": path.name, "sha256": sha(path) if value else None,
        "model_generated_pairs_inferred": 0, "accepted_pairs_inferred": 0,
        "simulation_only": True,
        "denominator_note": "Offline program-built preflight only; excluded from model generation, audit and pool denominators."}


def audit_conditions(out, requests):
    """Compare actual requests; only exact input/protocol/budget matches are paired."""
    conditions, matched, missing = {}, {}, 0
    for row in requests:
        if category(row) != "audit":
            continue
        intent = row["intent"]
        directory = (out / intent["directory"]).parent.resolve()
        if not directory.is_relative_to(out):
            raise ValueError("audit evidence directory escapes report root")
        params = intent.get("parameters", {})
        effort = params.get("reasoning_effort")
        protocol = read(directory / "AUDIT_PACKET.json", {}).get("version", "UNKNOWN")
        reviews = read(directory / "AUDIT_RESULT.json", {}).get("reviews", [])
        review = next((item for item in reviews if item.get("request_id") == intent["request_id"]), None)
        if review is None and effort in {"high", "max"}:
            raw = read(directory / f"AUDIT_{effort}.json", {})
            review = raw if raw.get("request_id") == intent["request_id"] else None
        valid = review is not None and valid_review(review)
        condition = {"protocol": protocol, "parameters": params, "provider": intent.get("provider", "UNKNOWN")}
        key = json.dumps(condition, sort_keys=True)
        conditions.setdefault(key, []).append((row, review, valid))
        comparable = {"protocol": protocol, "parameters_except_effort": {key: value for key, value in params.items()
                      if key != "reasoning_effort"}, "provider": intent.get("provider", "UNKNOWN"),
                      "messages_sha256": intent.get("messages_sha256"), "tools_sha256": intent.get("tools_sha256")}
        if protocol == "UNKNOWN" or not comparable["messages_sha256"] or not comparable["tools_sha256"]:
            missing += 1
            continue
        key = json.dumps(comparable, sort_keys=True)
        matched.setdefault(key, {}).setdefault(effort, []).append((row, review, valid))

    def metrics(values):
        spend, valid = cost([row for row, _, _ in values]), sum(valid for _, _, valid in values)
        per_valid = unit(spend, valid)
        if not valid:
            per_valid["status"] = "NO_CONTRACT_VALID_REVIEWS"
        return {"request_intents": len(values), "bound_review_results": sum(review is not None for _, review, _ in values),
            "contract_valid": valid, "contract_valid_rate": valid / len(values) if values else None,
            "contract_valid_verdicts": dict(Counter(review["review"]["verdict"] for _, review, valid in values if valid)),
            "invalid_evidence_reference_responses": sum(invalid_reference(review) for _, review, _ in values if review),
            "cost_and_usage": spend, "cost_per_contract_valid_review": per_valid}

    strata = [{**json.loads(key), **metrics(values)} for key, values in sorted(conditions.items())]
    pairs = []
    paired_values = {effort: [] for effort in ("high", "max")}
    for key, efforts in sorted(matched.items()):
        if any(len(efforts.get(effort, [])) != 1 for effort in paired_values):
            continue
        selected = {effort: efforts[effort][0] for effort in paired_values}
        pairs.append({"condition": json.loads(key), "efforts": {effort: metrics([value]) for effort, value in selected.items()},
            "both_contract_valid": all(value[2] for value in selected.values()),
            "contract_valid_verdict_disagreement": all(value[2] for value in selected.values()) and
                len({value[1]["review"]["verdict"] for value in selected.values()}) > 1})
        for effort, value in selected.items():
            paired_values[effort].append(value)
    return strata, {"status": "OBSERVED_SAME_INPUT_PAIRS" if pairs else "NOT_RUN",
        "paired_inputs": len(pairs), "requests_without_comparison_binding": missing,
        "unpaired_or_repeated_condition_groups": len(matched) - len(pairs),
        "by_effort": {effort: metrics(values) for effort, values in paired_values.items()}, "pairs": pairs,
        "limitation": "Exact messages/tools hashes, protocol, provider and all parameters except effort must match. Contract validity and verdict are observations, not independently established semantic accuracy or long-term superiority."}


def build(out, *, original_root=None):
    out = Path(out).resolve()
    if original_root is not None and not Path(original_root).is_absolute():
        raise ValueError("original-root must be an explicit absolute prefix")
    out.mkdir(parents=True, exist_ok=True)
    census = read(out / "BASELINE_CENSUS.json", {"pairs": [], "pair_count": 0})
    baseline = {row["id"]: row for row in census["pairs"]}
    forensic, forensic_pairs = forensic_summary(out, census)
    t321_fidelity = t321_design_fidelity(out, original_root)
    capacity, capacity_rows = structure_capacity(out)
    preflight = t362_preflight(out)
    ledger_before = sha(out / "REQUEST_LEDGER.jsonl") if (out / "REQUEST_LEDGER.jsonl").exists() else None
    requests, events = ledger(out / "REQUEST_LEDGER.jsonl")
    planned_generation, planned_audit, plans = {}, set(), []
    for path in sorted((out / "plans").glob("*.json")):
        value = read(path)
        for task in value.get("tasks", []):
            old = planned_generation.get(task["id"])
            if old is not None and old != task:
                raise ValueError("planned candidate ID was reused with different parameters")
            planned_generation[task["id"]] = task
        planned_audit.update(value.get("ids", []))
        plans.append({"file": path.relative_to(out).as_posix(), "sha256": sha(path),
                      "generation_ids": [row["id"] for row in value.get("tasks", [])], "audit_ids": value.get("ids", [])})
    ids = set(baseline) | set(planned_generation) | planned_audit
    for name in ("candidates", "reviews"):
        if (out / name).exists():
            ids.update(path.name for path in (out / name).iterdir() if path.is_dir())
    prior_ledgers, sunk_sources, prior_bindings, rows, accepted, quarantine = {}, {}, {}, [], [], []
    effort_reviews = {"high": [], "max": []}
    for identifier in sorted(ids):
        retained = baseline.get(identifier, {})
        source = source_path(retained["source_directory"], out, original_root) if retained else out / "candidates" / identifier
        review_dir = out / "reviews" / identifier
        admission = read(review_dir / "ADMISSION.json", {})
        if admission:
            source = source_path(admission["source_directory"], out, original_root)
        audit = read(review_dir / "audit/AUDIT_RESULT.json", {})
        result = read(source / "RESULT.json", {})
        task = result.get("task", planned_generation.get(identifier, {}))
        suite = admission.get("suite", retained.get("suite", task.get("suite", "UNKNOWN")))[:4]
        vector = admission.get("structural_vector", retained.get("vector", {}))
        if not vector and result.get("status") == "PASS" and (source / "PAIR.json").exists():
            pair = read(source / "PAIR.json")
            vector = structure_vector(case_from_dict(next(case for case in pair if case["arm"] == "CONTROL"), allow_dynamic=True))
        new_calls = [row for row in requests if row["intent"]["directory"].startswith("candidates/" + identifier + "/")]
        audit_calls = [row for row in requests if row["intent"]["directory"].startswith("reviews/" + identifier + "/")]
        generation_cost, audit_cost = cost(new_calls), cost(audit_calls)
        sunk = {"lower_cny": 0, "upper_cny": 0, "status": "NOT_APPLICABLE_NEW_GENERATION"}
        paid_source = None
        if retained:
            binding_root = ROOT if source.is_relative_to(ROOT) else out
            binding = generation_binding(source, binding_root, out, original_root)
            prior_bindings[identifier] = {"root": str(binding_root), **binding}
            paid_source = binding_root / binding["paid_source_directory"]
            old_ledger_path = paid_source.parent.parent / "REQUEST_LEDGER.jsonl"
            if old_ledger_path not in prior_ledgers:
                prior_ledgers[old_ledger_path] = ledger(old_ledger_path)[0]
            old_calls = [row for row in prior_ledgers[old_ledger_path]
                         if row["intent"]["directory"].startswith("candidates/" + paid_source.name + "/")]
            sunk = cost(old_calls)
            if not old_calls:
                sunk.update(status="MISSING_BOUND_PRIOR_USAGE", upper_cny=None)
            sunk_sources[str(paid_source)] = sunk
        pair_cost = add_cost(generation_cost, audit_cost, sunk)
        for review in audit.get("reviews", []):
            if review.get("effort") in effort_reviews:
                effort_reviews[review["effort"]].append(review)
        verdicts = [item.get("review", {}).get("verdict") for item in audit.get("reviews", [])]
        valid_verdicts = [item["review"]["verdict"] for item in audit.get("reviews", []) if valid_review(item)]
        protocol_failures = sum(not valid_review(item) for item in audit.get("reviews", []))
        hard_gate = read(source / "HARD_GATE.json", {})
        state = admission.get("status", "NOT_RUN")
        if not admission and result.get("status") == "FAIL":
            state = "REJECTED"
        elif not admission and (audit or new_calls or audit_calls):
            state = "QUARANTINED_INCOMPLETE"
        elif not admission and result.get("status") == "PASS":
            state = "DEV_ENGINEERING_VALID"
        trace_facts = forensic_pairs.get(identifier, {"status": "NOT_RUN"})
        recorded_state = state
        if retained and trace_facts["status"] == "CONFIRMED_INCONSISTENCY":
            state = "QUARANTINED_TRACE_PAYLOAD_INCONSISTENCY"
        record = {"id": identifier, "suite": suite, "origin": "RETAINED_BASELINE" if retained else "NEW_CANDIDATE",
            "status": state, "engineering_status": result.get("status", "NOT_RUN"),
            "recorded_admission_status": recorded_state, "trace_observation_status": trace_facts["status"],
            "trace_forensic": trace_facts,
            "hard_gate": "PASS" if hard_gate.get("passed") is True else "FAIL" if hard_gate.get("passed") is False else "NOT_RUN",
            "failed_stage": result.get("failed_stage", ""), "provider_category": result.get("category", ""),
            "error_type": result.get("error_type", ""),
            "audit_status": audit.get("status", "NOT_RUN"), "audit_verdicts": verdicts,
            "audit_disagreement": len(valid_verdicts) == 2 and len(set(valid_verdicts)) > 1,
            "audit_verdict_disagreement": len(verdicts) == 2 and None not in verdicts and len(set(verdicts)) > 1,
            "audit_protocol_failure_responses": protocol_failures,
            "audit_response_error_categories": dict(Counter(item["provider_category"] for item in audit.get("reviews", [])
                if item.get("provider_category"))),
            "audit_validation_error_counts": dict(Counter(error for item in audit.get("reviews", [])
                for error in item.get("validation_errors", []) or [])),
            "audit_semantic_error_code_counts": dict(Counter(code for item in audit.get("reviews", [])
                for code in (item.get("review") or {}).get("error_codes", []) or [])),
            "audit_invalid_evidence_reference_responses": sum(invalid_reference(item) for item in audit.get("reviews", [])),
            "audit_decision_reject_responses": sum(value == "REJECT" for value in verdicts),
            "audit_semantic_reject_responses": sum(value == "REJECT" for value in valid_verdicts),
            "recorded_strict_replays": admission.get("recorded_strict_replays", retained.get("reference_replay_rows",
                                                   result.get("reference_and_replay_count", 0))),
            "history_scope": admission.get("history_scope", "FULL_HISTORY" if retained else task.get("history_scope", "NOT_RUN")),
            "structural_cell_sha256": vector.get("structural_cell_sha256"), "structural_vector": vector,
            "difficulty_calibrated": False, "simulation_only": suite in {"T361", "T362", "T363"},
            "new_generation_cost": generation_cost, "new_audit_cost": audit_cost, "sunk_generation_cost": sunk,
            "paid_generation_source": str(paid_source) if paid_source else None,
            "direct_pair_cost_including_sunk_generation": pair_cost,
            "source_directory": str(source), "source_result_sha256": sha(source / "RESULT.json") if result else None,
            "admission_file": (review_dir / "ADMISSION.json").relative_to(out).as_posix() if admission else None,
            "formal_accepted": False, "same_model_audit_independent_science": False, "new_scientific_families": 0}
        if state == "DEV_ACCEPTED":
            valid_reviews = len(verdicts) == 2 and set(item.get("effort") for item in audit["reviews"]) == {"high", "max"}
            if (result.get("status") != "PASS" or hard_gate.get("passed") is not True or admission.get("hard_gate_errors")
                    or audit.get("status") != "DEV_AUTO_AUDITED" or not valid_reviews or set(verdicts) != {"ACCEPT"}
                    or not all(valid_review(item) for item in audit["reviews"])
                    or admission.get("recorded_strict_replays", 0) < 6 or admission.get("history_scope") != "FULL_HISTORY"
                    or not vector.get("runtime_consumed") or admission.get("formal_accepted") is not False
                    or admission.get("same_model_audit_independent_science") is not False
                    or admission.get("source_result_sha256") != record["source_result_sha256"]
                    or admission.get("audit_result_sha256") != canonical_sha256(audit)):
                raise ValueError("DEV_ACCEPTED contradicts bound hard-gate/audit/history evidence: " + identifier)
            accepted.append(record)
        elif state.startswith("QUARANTINED"):
            quarantine.append(record)
        rows.append(record)
    for filename, values in (("DEV_POOL_INDEX.jsonl", accepted), ("QUARANTINE_INDEX.jsonl", quarantine)):
        (out / filename).write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values), encoding="utf-8")
    coverage = []
    for suite, name in NAMES.items():
        old = [row for row in rows if row["suite"] == suite and row["origin"] == "RETAINED_BASELINE"]
        fresh = [row for row in rows if row["suite"] == suite and row["origin"] == "NEW_CANDIDATE"]
        admitted = [row for row in accepted if row["suite"] == suite]
        old_cells = {row["structural_cell_sha256"] for row in old if row["structural_cell_sha256"]}
        fresh_cells = {row["structural_cell_sha256"] for row in fresh if row["engineering_status"] == "PASS" and row["structural_cell_sha256"]}
        accepted_cells = {row["structural_cell_sha256"] for row in admitted}
        capacity_row = capacity_rows.get(suite, {key: "NOT_RUN" for key in ("capacity_status", "compiled_cell_upper_bound",
            "requested_structure_goal", "goal_unreachable_in_current_finite_grammar", "finite_axes", "capacity_basis",
            "capacity_limits", "reference_verified_planned_cells", "planned_fresh_cells", "allocation_status", "allocation_history_scope")})
        goal = capacity_row["requested_structure_goal"]
        shortage = max(goal - len(accepted_cells), 0) if isinstance(goal, int) else "NOT_RUN"
        if capacity_row["goal_unreachable_in_current_finite_grammar"] is True:
            shortage_reason = "CURRENT_FINITE_GRAMMAR_BOUND_BELOW_GOAL"
        elif shortage == "NOT_RUN":
            shortage_reason = "NOT_RUN_CAPACITY_EVIDENCE_MISSING"
        elif shortage:
            shortage_reason = "EXECUTION_AUDIT_HISTORY_OR_ADMISSION_NOT_COMPLETE"
        else:
            shortage_reason = "GOAL_REACHED_IN_DEVELOPMENT_POOL"
        coverage.append({"suite": suite, "name": name, "retained_pairs": len(old), "baseline_cells": len(old_cells),
            "baseline_trace_inconsistent_pairs": sum(row["trace_observation_status"] == "CONFIRMED_INCONSISTENCY" for row in old),
            "baseline_no_observed_contradiction_pairs": sum(row["trace_observation_status"] == "NO_OBSERVED_CONTRADICTION" for row in old),
            "new_engineering_valid_pairs": sum(row["engineering_status"] == "PASS" for row in fresh),
            "new_verified_executable_cells": len(fresh_cells - old_cells), "known_executable_cells": len(old_cells | fresh_cells),
            "dev_accepted_pairs": len(admitted), "accepted_cells": len(accepted_cells),
            "quarantined_pairs": sum(row["suite"] == suite for row in quarantine),
            **capacity_row, "accepted_cells_below_goal": shortage, "structure_goal_status": shortage_reason,
            "program_preflight_status": preflight["status"] if suite == "T362" else "NOT_APPLICABLE",
            "program_preflight_pairs": preflight["pairs"] if suite == "T362" else "NOT_APPLICABLE",
            "program_preflight_structure_cells": preflight["distinct_structure_cells"] if suite == "T362" else "NOT_APPLICABLE",
            "structural_cells": sorted(old_cells | fresh_cells), "empirical_difficulty": "NOT_RUN",
            "new_scientific_families": 0, "simulation_only": suite in {"T361", "T362", "T363"}})
    csv_write(out / "MECHANISM_COVERAGE.csv", coverage, list(coverage[0]))
    quality_fields = [key for key in rows[0] if key != "structural_vector"] if rows else ["id", "status", "engineering_status", "audit_status"]
    csv_write(out / "PAIR_QUALITY.csv", rows, quality_fields)
    all_cost = cost(requests)
    by_category = {name: cost([row for row in requests if category(row) == name])
                   for name in ("generation", "audit", "calibration", "other")}
    audited_baseline_sources = {row["paid_generation_source"] for row in rows
        if row["origin"] == "RETAINED_BASELINE" and row["audit_status"] != "NOT_RUN"}
    sunk_cost = add_cost(*(sunk_sources[name] for name in sorted(audited_baseline_sources)))
    failure_counts = Counter(row["failure"]["category"] for row in requests if row["failure"])
    unknown = sum(row["finished"] is None and (not row["failure"] or row["failure"]["category"] in {"REQUEST_UNRESOLVED", "UNKNOWN"}) for row in requests)
    calibration = calibration_summary(out)
    calibration_status = calibration["status"]
    summary = {"version": VERSION, "provider_calls_from_report": 0, "baseline_pairs": len(baseline),
        "path_mapping": {"original_root": str(original_root) if original_root is not None else None,
                         "current_root": str(ROOT), "fallback_to_original_workspace": False},
        "planned_generation_unique_ids": len(planned_generation), "planned_audit_unique_ids": len(planned_audit), "plan_snapshots": plans,
        "generation_terminal_pass": sum(row["origin"] == "NEW_CANDIDATE" and row["engineering_status"] == "PASS" for row in rows),
        "generation_terminal_fail": sum(row["origin"] == "NEW_CANDIDATE" and row["engineering_status"] == "FAIL" for row in rows),
        "generation_blocked_external": sum(row["origin"] == "NEW_CANDIDATE" and row["engineering_status"] == "BLOCKED_EXTERNAL" for row in rows),
        "generation_validation_jobs": sum(row["origin"] == "NEW_CANDIDATE" and row["engineering_status"] != "NOT_RUN" for row in rows),
        "generation_quality_rejections": sum(row["origin"] == "NEW_CANDIDATE" and row["error_type"] == "CandidateRejected" for row in rows),
        "generation_failure_stages": dict(Counter(row["failed_stage"] for row in rows if row["origin"] == "NEW_CANDIDATE" and row["failed_stage"])),
        "generation_started_ids": sorted({row["intent"]["directory"].split("/")[1] for row in requests if category(row) == "generation"}),
        "generation_planned_not_run": sorted(identifier for identifier in planned_generation if not any(
            row["id"] == identifier and (row["engineering_status"] != "NOT_RUN" or row["new_generation_cost"]["request_intents"]) for row in rows)),
        "audit_completed_pairs": sum(row["audit_status"] != "NOT_RUN" for row in rows),
        "retained_baseline_audit_completed_pairs": sum(row["origin"] == "RETAINED_BASELINE" and row["audit_status"] != "NOT_RUN" for row in rows),
        "audit_started_pairs": sum(row["new_audit_cost"]["request_intents"] > 0 for row in rows),
        "audit_incomplete_pairs": sum(row["new_audit_cost"]["request_intents"] > 0 and row["audit_status"] == "NOT_RUN" for row in rows),
        "audit_planned_not_run": sorted(identifier for identifier in planned_audit if not any(
            row["id"] == identifier and (row["audit_status"] != "NOT_RUN" or row["new_audit_cost"]["request_intents"]) for row in rows)),
        "audit_disagreements": sum(row["audit_disagreement"] for row in rows),
        "audit_verdict_disagreements": sum(row["audit_verdict_disagreement"] for row in rows),
        "audit_protocol_failure_pairs": sum(row["audit_protocol_failure_responses"] > 0 for row in rows),
        "audit_protocol_failure_responses": sum(row["audit_protocol_failure_responses"] for row in rows),
        "audit_response_error_categories": dict(sum((Counter(row["audit_response_error_categories"]) for row in rows), Counter())),
        "audit_validation_error_counts": dict(sum((Counter(row["audit_validation_error_counts"]) for row in rows), Counter())),
        "audit_semantic_error_code_counts": dict(sum((Counter(row["audit_semantic_error_code_counts"]) for row in rows), Counter())),
        "audit_invalid_evidence_reference_responses": sum(row["audit_invalid_evidence_reference_responses"] for row in rows),
        "audit_decision_reject_responses": sum(row["audit_decision_reject_responses"] for row in rows),
        "audit_semantic_reject_responses": sum(row["audit_semantic_reject_responses"] for row in rows),
        "dev_accepted_pairs": len(accepted), "quarantined_pairs": len(quarantine),
        "retained_baseline_dev_accepted_pairs": sum(row["origin"] == "RETAINED_BASELINE" for row in accepted),
        "new_candidate_dev_accepted_pairs": sum(row["origin"] == "NEW_CANDIDATE" for row in accepted),
        "rejected_pairs": sum(row["status"] == "REJECTED" for row in rows),
        "request_intents": len(requests), "complete_responses": sum(row["finished"] is not None and row["finished"].get("status") == "PASS" for row in requests),
        "response_usage_receipts": sum(row["finished"] is not None for row in requests),
        "http200_responses": sum(((row["finished"] or row["failure"]).get("transport") or {}).get("http_status") == 200
                                 for row in requests if row["finished"] or row["failure"]),
        "complete_responses_definition": "Complete ModelPort response objects retain completion status when downstream audit JSON/contract validation fails. Audit response categories, validation errors and semantic error codes are separate from ledger transport/provider failures.",
        "failure_event_count": sum(row["event"] == "REQUEST_FAILED" for row in events),
        "failure_categories": dict(failure_counts), "unknown_terminal_requests": unknown,
        "new_spend": all_cost, "new_spend_by_role": by_category, "reused_audited_baseline_sunk_generation": sunk_cost,
        "unit_new_batch_spend_per_dev_accepted": unit(all_cost, len(accepted)),
        "unit_batch_with_reused_generation_per_dev_accepted": unit(add_cost(all_cost, sunk_cost), len(accepted)),
        "unit_cost_denominator_note": "All current failures, calibration and incomplete attempts remain in batch spend. Retained generation is sunk, never a new request. Missing billing is unknown, not zero.",
        "trace_aliasing_forensic": forensic, "t321_design_fidelity_limitation": t321_fidelity,
        "structure_capacity_evidence": capacity, "mechanism_coverage": coverage,
        "t362_structure_preflight": preflight,
        "audit_calibration": calibration,
        "audit_effort_comparison": {effort: {"attempts": len(values), "contract_valid": sum(valid_review(row) for row in values),
            "contract_valid_rate": sum(valid_review(row) for row in values) / len(values) if values else None,
            "verdicts": dict(Counter(row.get("review", {}).get("verdict", "NO_VALID_VERDICT") for row in values)),
            "cost": cost([row for row in requests if category(row) == "audit"
                          and row["intent"].get("parameters", {}).get("reasoning_effort") == effort])}
            for effort, values in effort_reviews.items()},
        "stability": stability(requests), "formal_scientific_claims": False,
        "same_model_audit_independent_science": False, "new_scientific_families": 0,
        "human_gold": "NOT_REQUIRED_FOR_DEVELOPMENT", "PI_adjudication": "NOT_REQUIRED_FOR_DEVELOPMENT"}
    holdout = read(out / "calibration/FROZEN_PLAN.json", {}).get("holdout_positive_suites", [])
    observed = sorted({row["suite"] for row in rows if row["audit_status"] != "NOT_RUN" and row["suite"] in holdout})
    summary["holdout"] = {"planned_suites": holdout, "audited_suites": observed,
        "execution_status": "NOT_RUN" if not observed else "COMPLETE" if set(holdout) <= set(observed) else "PARTIAL",
        "scientific_independent_validation": False}
    summary["audit_parameter_conditions"], summary["audit_same_input_effort_comparison"] = audit_conditions(out, requests)
    summary["effort_comparison_limitation"] = "Read frozen parameter strata; different output ceilings across packet versions are not a controlled effort-only comparison."
    atomic_json(out / "COST_AND_YIELD.json", summary)
    regression = []
    for path in sorted(out.glob("*.xml")):
        tree = ElementTree.parse(path).getroot()
        suites = list(tree.iter("testsuite"))
        counts = {name: sum(int(row.get(name, 0)) for row in suites) for name in ("tests", "failures", "errors", "skipped")}
        regression.append({"file": path.name, **counts, "status": "PASS" if counts["tests"] and not counts["failures"] and not counts["errors"] else "FAIL"})
    readiness = ["# 18项研发准备度", "", "结构单元只计真实执行的依赖、拓扑、时序或证据路径；名称、seed、领域和正文不计。E/M/H均为设计意图。有限语法编译上限、程序预检和真实模型生成分别计数。", "",
        "|测评|旧对/结构单元|新工程对/新增结构单元|研发入池对/结构单元|编译上限|计划新增/预检通过单元|不足3种原因与限制|", "|---|---:|---:|---:|---:|---:|---|"]
    for row in coverage:
        limit = "历史5.1.0缺口；仅VERSION_SCOPED隔离" if row["suite"] == "T322" else "SIMULATION_ONLY" if row["simulation_only"] else "同模型审核；无科学独立性声明"
        if row["baseline_trace_inconsistent_pairs"]:
            limit += f"；旧{row['baseline_trace_inconsistent_pairs']}对存在轨迹回执矛盾，保留隔离"
        reason = {"CURRENT_FINITE_GRAMMAR_BOUND_BELOW_GOAL": "当前有限语法上限不足3；需扩展真实可执行结构",
                  "NOT_RUN_CAPACITY_EVIDENCE_MISSING": "NOT_RUN：容量证据缺失",
                  "EXECUTION_AUDIT_HISTORY_OR_ADMISSION_NOT_COMPLETE": "真实生成、审核、历史验证或入池尚未凑足3种",
                  "GOAL_REACHED_IN_DEVELOPMENT_POOL": "研发池已达目标"}[row["structure_goal_status"]]
        axes = json.dumps(row["finite_axes"], ensure_ascii=False, sort_keys=True).replace("|", "\\|")
        limits = json.dumps(row["capacity_limits"], ensure_ascii=False).replace("|", "\\|")
        readiness.append(f"|{row['suite']} {row['name']}|{row['retained_pairs']}/{row['baseline_cells']}|{row['new_engineering_valid_pairs']}/{row['new_verified_executable_cells']}|{row['dev_accepted_pairs']}/{row['accepted_cells']}|{row['compiled_cell_upper_bound']}|{row['planned_fresh_cells']}/{row['reference_verified_planned_cells']}|{reason}；{limit}；有限轴{axes}；{limits}|")
    readiness += ["", f"T362程序预检：{preflight['status']}，程序构造{preflight['pairs']}对、参考执行{preflight['reference_runs']}次、记录响应严格Replay {preflight['strict_recorded_response_replays']}次、结构单元{preflight['distinct_structure_cells']}种；provider_calls={preflight['provider_calls']}，cases_entered_pool={preflight['cases_entered_pool']}。这些计数不加入真实生成或研发入池分母。", "",
        "结构容量原始证据：STRUCTURE_CAPACITY.json、COVERAGE_ALLOCATION.json；程序预检原始证据：T362_STRUCTURE_PREFLIGHT.json。缺少证据保持NOT_RUN。"]
    (out / "SUITE18_READINESS.md").write_text("\n".join(readiness) + "\n", encoding="utf-8")
    stop = read(out / "STOP.json", {})
    history_gap = read(out / "T322_HISTORY_INVESTIGATION.json", {}).get("known_affected_unique_cases", "NOT_RUN")
    next_actions = ["# 下一步", "", "继续使用当前版本化研发策略；Gold、PI和跨家族资格不作为研发入池前置条件。"]
    if stop:
        next_actions += ["", "存在停止收据：`" + json.dumps(stop, ensure_ascii=False, sort_keys=True) + "`。保留请求终态，禁止盲目重发；先核对服务方收据、余额或网络状态。"]
    if calibration_status != "PASS":
        next_actions += ["", f"自动审核负例校准为{calibration_status}；检查实际负例拒绝、契约引用与否证能力，不能把硬门拒绝冒充模型识别成功。"]
    if forensic.get("affected_pair_ids"):
        next_actions += ["", "轨迹取证隔离：" + ", ".join(forensic["affected_pair_ids"]) +
            "。保留原样本与全部历史证据；用新版本修正执行证据并重新审核后再判断研发入池。引擎1.4.4原响应重分析不能替代原源码严格Replay或新审核，禁止直接覆盖旧证据。"]
    if t321_fidelity["status"] != "NOT_RUN":
        next_actions += ["", t321_design_note(t321_fidelity),
            "后续新版本须核对声明结构与实际消费payload，并实现明确版本化的clean-close语义或拒绝不支持的声明；禁止重试或改写已封存候选来获取审核通过。"]
    next_actions += ["", f"T322：旧版缺口计数{history_gap}；找回精确5.1.0源码/评分器/原始版本绑定前，只能VERSION_SCOPED隔离，不宣称全历史非重复。",
        "", "优先扩展尚不足3种的真实结构单元；复用旧32对，拒绝靠正文扩写刷数量。补齐尚未执行的保留集、分时段测试与严格回放；未知项目保持NOT_RUN。",
        "", "用户操作：聊天中曾出现的密钥请在DeepSeek官方控制台轮换，并仅更新本机DEEPSEEK_API_KEY/.env；不回显、不写入证据。此项外部动作不阻塞已授权研发执行。",
        "", "正式科学冻结、确认性Pilot与Campaign本轮均未启动；同模型两次审核不具备跨模型科学独立性。"]
    (out / "NEXT_ACTIONS.md").write_text("\n".join(next_actions) + "\n", encoding="utf-8")
    def bound(value):
        return f"¥{value['lower_cny']:.6f}–{value['upper_cny']:.6f}" if value["upper_cny"] is not None else f"已知下界¥{value['lower_cny']:.6f}，上界UNKNOWN"
    lines = ["# DeepSeek同模型自动审核研发工厂交接", "", f"保留基线{len(baseline)}对，原基线审核完成{summary['retained_baseline_audit_completed_pairs']}/{len(baseline)}对；本轮DEV_ACCEPTED {len(accepted)}对（新生成入池{summary['new_candidate_dev_accepted_pairs']}对，旧基线复用入池{summary['retained_baseline_dev_accepted_pairs']}对），隔离{len(quarantine)}对，生成失败与入池拒收合计{summary['rejected_pairs']}对（含生成FAIL {summary['generation_terminal_fail']}对）。工程研发已允许同模型生成、审核与修复；未改旧科研正式状态。", "",
        f"计划生成{len(planned_generation)}个唯一ID，实际发起{len(summary['generation_started_ids'])}个；生成终态PASS {summary['generation_terminal_pass']}、FAIL {summary['generation_terminal_fail']}。显式审核计划{len(planned_audit)}个唯一ID（另有生成阶段附随审核）；全部来源完成{summary['audit_completed_pairs']}对，原始verdict分歧{summary['audit_verdict_disagreements']}对、两份契约均有效的分歧{summary['audit_disagreements']}对。各版本计划均保留，未执行ID见COST_AND_YIELD.json。", "",
        f"请求{len(requests)}次，完整ModelPort completion {summary['complete_responses']}次，HTTP 200 {summary['http200_responses']}次，终态未知{unknown}次；账本请求失败分类：{json.dumps(dict(failure_counts), ensure_ascii=False)}。审核响应错误分类：{json.dumps(summary['audit_response_error_categories'], ensure_ascii=False)}；审核契约错误：{json.dumps(summary['audit_validation_error_counts'], ensure_ascii=False)}；语义审核error_codes：{json.dumps(summary['audit_semantic_error_code_counts'], ensure_ascii=False)}。完整completion的审核JSON无效不降为UNKNOWN或HTTP失败。报告自身调用0次。", "",
        f"新增花费估算：{bound(all_cost)}；已复用且审核的旧样本沉没生成成本：{bound(sunk_cost)}。实际账单UNKNOWN。批次单位成本保留失败和负例投入，零接受时不输出虚假单位成本。", "",
        f"负例审核校准：{calibration_status}，实际{calibration['executed']}/{calibration['planned']}，仅决策双REJECT {calibration['decision_rejection_passes']}，契约与引用均有效的双拒绝{calibration['model_rejection_passes']}，硬门拦截{calibration['hard_gate_rejection_passes']}。原始verdict分歧{calibration['verdict_disagreements']}、契约有效分歧{calibration['contract_valid_verdict_disagreements']}、无效证据引用响应{calibration['invalid_evidence_reference_responses']}；REJECT但引用无效不能记PASS。", "",
        "回归：" + (json.dumps(regression, ensure_ascii=False) if regression else "NOT_RUN（本轮目录未提供JUnit结果）") + "。",
        "", f"T322当前可执行能力与全历史新颖性证明分开；5.1.0缺口计数{history_gap}，相关候选仍隔离。T362程序预检{preflight['status']}：{preflight['pairs']}对/{preflight['distinct_structure_cells']}结构，参考执行{preflight['reference_runs']}次、严格记录响应Replay {preflight['strict_recorded_response_replays']}次、provider_calls={preflight['provider_calls']}、入池={preflight['cases_entered_pool']}；与真实新生成分母分开。各项有限语法上限、不足3种原因及实际入池结构见SUITE18_READINESS.md。",
        "", f"审核high/max同输入比较：{summary['audit_same_input_effort_comparison']['status']}，严格同输入/工具/协议/输出预算配对{summary['audit_same_input_effort_comparison']['paired_inputs']}组；逐条件有效契约率与单位有效审核成本见COST_AND_YIELD.json。不同协议或预算不合并推断档位优劣；契约有效不等于独立科学语义准确。",
        "", "工程可靠性、数据质量、结构多样性分别见PAIR_QUALITY.csv、审核原始JSON和MECHANISM_COVERAGE.csv；不将32对称为32个新机制。T361–T363继续SIMULATION_ONLY，难度尚未实证校准。",
        "", f"观测到{len(summary['stability']['windows'])}个真实UTC半小时时窗；短时间成功不能证明长期稳定。正式接受、新科学家族、科学独立审核均为0。",
        "", "复跑汇总：`python scripts/v5/report_development_factory.py --out " + out.as_posix() +
            (" --original-root " + str(original_root) if original_root is not None else "") + "`。完整运行阶段见`python scripts/v5/run_development_factory.py --help`，未运行阶段不能继承旧PASS。",
        "", "原始失败、未知请求、未执行计划与历史样本全部保留。剩余操作见NEXT_ACTIONS.md；本报告不启动正式生产或发布。"]
    if forensic["status"] != "NOT_RUN":
        lines[2:2] = [f"旧基线轨迹取证：{forensic['retained_pairs']}对、{forensic['reference_rows']}行中，{forensic['pairs_without_observed_contradiction']}对无已观察回执矛盾；{forensic['affected_pairs']}对、{forensic['mismatched_reference_rows']}行、{forensic['result_mismatches']}个工具结果存在矛盾，原数据保留并隔离。{forensic.get('engine_version')}原响应重分析通过{forensic['current_engine_reanalysis_pass']}行；这是reanalysis，不替代原源码strict Replay或新版审核。未被后续请求见证的末次回执{forensic['terminal_results_unobserved']}个；若存在则保持UNKNOWN。详见FORENSIC_TRACE_ALIASING.json。", ""]
    if t321_fidelity["status"] != "NOT_RUN":
        lines += ["", t321_design_note(t321_fidelity)]
    (out / "ROUND_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if ledger_before != (sha(out / "REQUEST_LEDGER.jsonl") if (out / "REQUEST_LEDGER.jsonl").exists() else None):
        raise ValueError("ledger changed during reporting; rerun after the active writer finishes")
    evidence = {path.relative_to(out).as_posix(): sha(path) for path in sorted(out.rglob("*"))
                if path.is_file() and path.name != "EVIDENCE_INDEX.json" and not path.name.endswith(".lock")
                and "__pycache__" not in path.parts}
    for binding in prior_bindings.values():
        for name, digest in binding["files"].items():
            if sha(Path(binding["root"]) / name) != digest:
                raise ValueError("prior generation cost/reuse evidence changed during reporting")
    atomic_json(out / "EVIDENCE_INDEX.json", {"version": VERSION, "provider_calls": 0,
        "report_script_sha256": sha(Path(__file__)), "files": evidence,
        "external_baseline_bindings": {row["id"]: {"source_directory": row["source_directory"],
            "source_result_sha256": row.get("source_result_sha256"), "pair_sha256": row.get("pair_sha256")}
            for row in baseline.values()}, "external_generation_cost_and_reuse_bindings": prior_bindings,
        "formal_scientific_claims": False, "same_model_audit_independent_science": False})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, help="Map only this explicit original absolute prefix into the current source root; never read the original checkout")
    args = parser.parse_args()
    with writer_lock(args.out):
        result = build(args.out, original_root=args.original_root)
    print(json.dumps({key: result[key] for key in ("baseline_pairs", "dev_accepted_pairs", "quarantined_pairs", "unknown_terminal_requests")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
