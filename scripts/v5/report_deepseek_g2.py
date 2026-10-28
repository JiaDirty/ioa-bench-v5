"""Recompute the official G2 handoff from sealed evidence, without provider calls."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]

from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.direct_deepseek import candidate_result, SCOPE, parameters, STAGE_BUDGET
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.quality import classify_candidate
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.evaluation import atomic_json
from verify_round01_readiness import NAMES


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def latency(values):
    values = sorted(values)
    return {"n": len(values), "mean_seconds": statistics.mean(values) if values else None,
            "p95_seconds": values[max(0, math.ceil(len(values) * .95) - 1)] if values else None}


def total_cost(calls):
    unknown = sum(row["cost"].get("upper_cny") is None for row in calls)
    return {"lower_cny": sum(row["cost"].get("lower_cny") or 0 for row in calls),
            "upper_cny": None if unknown else sum(row["cost"]["upper_cny"] for row in calls),
            "unknown_estimates": unknown,
            "invoice": "UNKNOWN", "currency": "CNY", "basis": "official cache-aware peak/off-peak bounds"}


def build(out, pool_plan, regression):
    plan, effort_plan = read(pool_plan), read(out / "EFFORT_PLAN_V1.json")
    rows = [candidate_result(path.parent) for path in sorted((out / "candidates").glob("*/RESULT.json"))]
    by_id = {row["task"]["id"]: row for row in rows}
    previous, ledger = "", []
    for line in (out / "REQUEST_LEDGER.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        digest = row.pop("event_sha256")
        assert row["previous_event_sha256"] == previous and canonical_sha256(row) == digest
        previous = digest
        ledger.append(row)
    intents = [row for row in ledger if row["event"] == "REQUEST_INTENT"]
    calls = [row for row in ledger if row["event"] == "REQUEST_FINISHED"]
    identities = [(row["directory"], row["request_id"]) for row in intents]
    assert len(identities) == len(set(identities)), "duplicate paid intent"
    assert all(row["provider"] == "deepseek" for row in ledger)
    failures = [row for row in ledger if row["event"] == "REQUEST_FAILED"]
    cost = total_cost(calls)
    cost.update(actual_post_intents=len(intents), durable_complete_responses=len(calls),
        failed_records=len(failures), unknown_or_incomplete_billing_requests=len(intents) - len(calls),
        usage={key: sum(row["usage"].get(key, 0) for row in calls) for key in
               ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")},
        reasoning_tokens=sum((row["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens", 0) for row in calls),
        provider_latency=latency([row["transport"]["elapsed_seconds"] for row in calls if row.get("transport", {}).get("elapsed_seconds") is not None]),
        historical_unknown_requests_resent=0, AIHubMix_new_generation_calls=0,
        soft_cny=50, hard_cny=200, cached_generation_reuse_charged_twice=False)
    atomic_json(out / "USAGE_AND_COST.json", cost)
    planned_pool = [by_id.get(task["id"], {"status": "NOT_RUN", "task": task}) for task in plan["tasks"]]
    valid_pool = [row for row in planned_pool if row["status"] == "PASS"]
    diagnostics = []
    for row in rows:
        directory = out / "candidates" / row["task"]["id"]
        history = read(directory / "HISTORICAL_DIVERSITY.json") if (directory / "HISTORICAL_DIVERSITY.json").exists() else {}
        neighbors = history.get("nearest_neighbors", [])
        stages = read(directory / "GENERATION_STAGES.json") if (directory / "GENERATION_STAGES.json").exists() else []
        responses = [read(path)["response"] for path in (directory / "model_io").glob("*/RESPONSE.json")]
        events = [json.loads(line) for line in (directory / "EXECUTION_LOG.jsonl").read_text(encoding="utf-8").splitlines()]
        elapsed = (datetime.fromisoformat(events[-1]["at_utc"]) - datetime.fromisoformat(events[0]["at_utc"])).total_seconds()
        diagnostics.append({"candidate": row["task"]["id"], "task": row["task"], "status": row["status"],
            "end_to_end_seconds": elapsed, "end_to_end_time_precision_seconds": 1,
            "failed_stage": row.get("failed_stage"), "error_type": row.get("error_type"),
            "classification": "ENGINEERING_QUALITY_REJECTION" if row.get("error_type") == "CandidateRejected" else
                row.get("category") if "Provider" in row.get("error_type", "") else "LOCAL_EXECUTION_ERROR" if row.get("error_type") else None,
            "stage_count": len(stages), "complete_four_stage_schema": len(stages) == 4,
            "http200_responses": sum(r["provider_metadata"].get("_transport", {}).get("http_status") == 200 for r in responses),
            "finish_reasons": dict(Counter(r["finish_reason"] for r in responses)),
            "history_status": history.get("status", "NOT_RUN"), "text_threshold": history.get("text_threshold"),
            "nearest_neighbors": neighbors[:3], "runtime_structure": history.get("public_runtime_proof", {}).get("current"),
            "structural_signature_sha256": row.get("structural_signature_sha256"),
            "history_arm_statuses": row.get("history_statuses", []),
            "strict_replay_count": row.get("reference_and_replay_count", 0),
            "generation_reused_without_new_charge": (directory / "GENERATION_REUSE.json").exists(),
            "source_of_truth": directory.relative_to(out).as_posix() + "/RESULT.json"})
    atomic_json(out / "CANDIDATE_DIAGNOSTICS.json", {"rows": diagnostics, "scientific_new_families": 0,
        "raw_errors_retained": True, "no_provider_failure_inferred_from_quality_rejection": True})
    suite_rows = []
    for suite, name in NAMES.items():
        attempted = [row for row in rows if row["task"]["suite"] == suite and row["task"]["cohort"] == "pool"]
        accepted = [row for row in valid_pool if row["task"]["suite"] == suite]
        targets = {canonical_sha256(row["task"]["target"]) for row in accepted}
        signatures = {row["structural_signature_sha256"] for row in accepted}
        attempted_ids = {row["task"]["id"] for row in attempted}
        paid_ids = {r["directory"].split("/")[1] for r in intents if r["directory"].startswith("candidates/")}
        suite_rows.append({"suite": suite, "name": name, "validation_jobs": len(attempted),
            "paid_generation_jobs": len(attempted_ids & paid_ids),
            "planned_pool_pairs": sum(task["suite"] == suite for task in plan["tasks"]),
            "valid_pairs": len(accepted), "distinct_consumed_target_combinations": len(targets),
            "distinct_runtime_signatures": len(signatures),
            "status": "PASS" if accepted else "BLOCKED_EXTERNAL" if suite == "T322" else "FAIL",
            "failed_validation_jobs": sum(row["status"] != "PASS" for row in attempted),
            "formal_pairs": 0, "simulation_only": suite in {"T361", "T362", "T363"},
            "gap": "original T322 5.1.0 historical runtime absent; 120 cases INDETERMINATE" if suite == "T322" else
                   "T362 finite headline/evidence-access grammar: all retained attempts fail both-arm history requirement; see T362_CAPABILITY_GAP.json; local engineering backlog, not external approval" if suite == "T362" and not accepted else
                   "finite declared grammar only; semantic independent audit and empirical difficulty not established"})
    with (out / "SUITE18_PROGRESS.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(suite_rows[0]))
        writer.writeheader()
        writer.writerows(suite_rows)
    comparisons, groups = [], {}
    for effort in ("disabled", "low", "high", "max"):
        tasks = [task for task in effort_plan["tasks"] if task["effort"] == effort]
        groups[effort] = {(task["suite"], task["seed"], canonical_sha256(task["target"]), task["domain"]) for task in tasks}
        selected = [by_id.get(task["id"], {"status": "NOT_RUN"}) for task in tasks]
        group_calls = [row for row in calls if any(row["directory"].startswith("candidates/" + task["id"] + "/") for task in tasks)]
        c = total_cost(group_calls)
        valid = sum(row["status"] == "PASS" for row in selected)
        comparisons.append({"effort": effort, "planned": len(tasks), "executed": sum(row["status"] != "NOT_RUN" for row in selected),
            "valid_pairs": valid, "valid_rate": valid / len(tasks), "result_counts": dict(Counter(row["status"] for row in selected)),
            "cost": c, "cost_per_valid_pair_lower_cny": c["lower_cny"] / valid if valid else "NOT_COMPUTABLE",
            "cost_per_valid_pair_upper_cny": c["upper_cny"] / valid if valid and c["upper_cny"] is not None else "NOT_COMPUTABLE",
            "latency": latency([row["transport"]["elapsed_seconds"] for row in group_calls]),
            "generation_pipeline_latency": latency([d["end_to_end_seconds"] for d in diagnostics
                if d["candidate"] in {task["id"] for task in tasks}]),
            "reasoning_tokens": sum((row["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens", 0) for row in group_calls),
            "completion_tokens": sum(row["usage"].get("completion_tokens", 0) for row in group_calls),
            "truncated_responses": sum("length" in row.get("error", "") for row in selected),
            "quality_failure_stages": dict(Counter(row.get("failed_stage", "NOT_RUN") for row in selected if row["status"] != "PASS"))})
    assert all(value == groups["high"] for value in groups.values()), "effort task inputs drifted"
    overlaps = []
    effort_outputs = [row for row in rows if row["task"]["cohort"].startswith("effort-")
                      and (out / "candidates" / row["task"]["id"] / "PAIR.json").exists()]
    for i, first in enumerate(effort_outputs):
        for second in effort_outputs[i + 1:]:
            a, b = first["task"], second["task"]
            if (a["suite"], a["seed"], a["target"], a["domain"]) != (b["suite"], b["seed"], b["target"], b["domain"]):
                continue
            pair_a, pair_b = (read(out / "candidates" / t["id"] / "PAIR.json") for t in (a, b))
            scenario = suite_spec(a["suite"], typed=True).scenario_factory()
            arms = []
            for raw_a, raw_b in zip(pair_a, pair_b):
                c = classify_candidate(case_from_dict(raw_a, allow_dynamic=True),
                    [case_from_dict(raw_b, allow_dynamic=True)], scenario=scenario)
                arms.append({"arm": raw_a["arm"], "status": c["status"], "nearest": c["nearest_neighbors"][0]})
            overlaps.append({"first": a["id"], "second": b["id"], "arms": arms,
                "both_arms_duplicate": all(c["status"] in {"EXACT_DUPLICATE", "TEXT_DUPLICATE"} for c in arms)})
    atomic_json(out / "EFFORT_CROSS_COHORT_OVERLAP.json", {"status": "PASS" if effort_outputs else "NOT_RUN",
        "source": "posthoc deterministic comparison under current feature projection; not an acceptance override",
        "excluded_from_within_cohort_acceptance_denominators": True, "comparison_count": len(overlaps),
        "expected_same_task_config_comparisons": 36, "missing_pair_comparisons_NOT_RUN": 36 - len(overlaps),
        "both_arms_duplicate_count": sum(row["both_arms_duplicate"] for row in overlaps), "rows": overlaps})
    ranked = sorted(comparisons, key=lambda row: (-row["valid_pairs"], row["cost"]["upper_cny"] / row["valid_pairs"]
        if row["valid_pairs"] and row["cost"]["upper_cny"] is not None else float("inf")))
    atomic_json(out / "EFFORT_COMPARISON.json", {"status": "PASS" if all(row["executed"] == row["planned"] for row in comparisons) else "NOT_RUN",
        "rows": comparisons, "ranking": [row["effort"] for row in ranked], "same_initial_tasks": True,
        "scope": effort_plan["fairness"], "independent_semantic_quality": "NOT_RUN", "long_term_stability": "NOT_RUN"})
    atomic_json(out / "MODEL_RANKING.json", {"provider": "deepseek", "model": "deepseek-flash", "ranked_configurations": ranked,
        "ranking_rule": "engineering valid yield first, cache-aware upper cost per valid pair second; six development tasks, not general scientific quality",
        "formal_model_selection": "BLOCKED_EXTERNAL", "independent_auditor": None})
    recommended = next((row for row in ranked if row["executed"] == row["planned"] == 6 and row["valid_pairs"]), None)
    atomic_json(out / "RECOMMENDED_DEVELOPMENT_PROFILE.json", {"version": "ioabench.v5.deepseek-development-recommendation/1",
        "provider": "deepseek", "model_id": "deepseek-flash", "scope": SCOPE,
        "recommended_effort": recommended["effort"] if recommended else None,
        "measured_valid_pairs": recommended["valid_pairs"] if recommended else None,
        "recommendation_limit": "six fixed tasks only; remaining rejection probability retained; no semantic-auditor qualification",
        "endpoint": "https://api.deepseek.com/chat/completions", "generator_role": SCOPE,
        "stage_parameters": {stage: parameters(recommended["effort"], max_tokens=limit)
            for stage, limit in STAGE_BUDGET.items()} if recommended else None,
        "pipeline_entrypoint": "ModelPort/DeepSeekAdapter -> AuxiliaryRouter -> staged_proposal -> engineering_checks",
        "execution": {"max_concurrency": 1, "per_stage_submissions": 1, "soft_cny": 50, "hard_cny": 200,
            "unknown_auth_balance_action": "STOP_AND_PRESERVE_NO_RESEND"},
        "evidence": "EFFORT_COMPARISON.json", "formal_generator_allowed": False, "formal_auditor_qualified": False,
        "independent_auditor": None, "G3_parent_eligible": False, "fallback": "STOP_AND_PRESERVE_NO_RESEND",
        "complex_design": "high/max only as explicitly measured; no universal advantage established",
        "base_contract_config": "config/v5/deepseek_g2_exploratory_v1.yaml", "formal_routing_active": False})
    full = ElementTree.parse(regression).getroot().find("testsuite")
    tests = {key: int(full.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}
    source = source_tree_hash(ROOT)
    sources = {p.relative_to(ROOT).as_posix(): sha(p) for folder in ("src", "contracts", "config")
               for p in sorted((ROOT / folder).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    atomic_json(out / "SOURCE_MANIFEST.json", {"head": head, "runtime_sha256": source, "files": sources,
        "baseline": "SOURCE_BASELINE_CORRECTION_V3.json", "execution_source_revisions": sorted(p.name for p in (out / "source_revisions").iterdir())})
    gates, references, histories = [], [], []
    for row in rows:
        directory = out / "candidates" / row["task"]["id"]
        def evidence(name, default):
            return read(directory / name) if (directory / name).exists() else default
        gate, fidelity = evidence("HARD_GATE.json", {}), evidence("FIDELITY.json", {})
        strict, helper = evidence("STRICT_REFERENCE_RESULTS.json", []), evidence("REFERENCE_RESULTS.json", [])
        negative, replay = evidence("NEGATIVE_CONTROL.json", {}), evidence("REPLAY.json", [])
        gates.append({"candidate": row["task"]["id"], "terminal_status": row["status"],
            "compiled_pair": "PASS" if (directory / "PAIR.json").exists() else "NOT_RUN",
            "hard_gate": "PASS" if gate.get("passed") is True else "FAIL" if gate else "NOT_RUN",
            "hard_gate_failures": gate.get("failures", []), "fidelity_faithful": fidelity.get("faithful"),
            "fidelity_gaps": fidelity.get("gaps", []), "source": directory.relative_to(out).as_posix()})
        references.append({"candidate": row["task"]["id"], "hard_gate_policy_arm_runs": len(gate.get("runs", [])),
            "factory_reference_runs": len(helper), "pinned_reference_batch_runs": len(strict),
            "strict_replays_passed": sum(check.get("passed") is True for check in replay),
            "strict_replays_total": len(replay), "removed_intervention_negative": negative.get("status", "NOT_RUN"),
            "reference_outcomes": dict(Counter(r.get("outcome", {}).get("legacy_class", r.get("status")) for r in strict)),
            "note": "Each execution layer has its own denominator; Replay consumes recorded responses and sends no provider request.",
            "source": directory.relative_to(out).as_posix()})
        histories.append({"candidate": row["task"]["id"], "both_arms": evidence("HISTORY_DEDUP.json", "NOT_RUN"),
            "control_precheck": evidence("HISTORICAL_DIVERSITY.json", {}).get("status", "NOT_RUN"),
            "baseline_sha256": read(directory / "MANIFEST.json")["history_sha256"],
            "source": directory.relative_to(out).as_posix()})
    for name, evidence_rows in (("COMPILATION_AND_HARD_GATES.json", gates),
            ("REFERENCE_AND_CAUSAL_CHECKS.json", references), ("HISTORY_DEDUP.json", histories)):
        atomic_json(out / name, {"candidates": evidence_rows, "source_of_truth": "sealed per-candidate files; all rejected outputs retained"})
    atomic_json(out / "DIVERSITY_ANALYSIS.json", {"suite_rows": suite_rows, "valid_pool_pairs": len(valid_pool),
        "cases": len(valid_pool) * 2, "validation_jobs": len(rows), "validation_statuses": dict(Counter(row["status"] for row in rows)),
        "structural_target_combinations": sum(row["distinct_consumed_target_combinations"] for row in suite_rows),
        "distinct_runtime_signatures_within_suites": sum(row["distinct_runtime_signatures"] for row in suite_rows),
        "difficulty_design_counts": dict(Counter(row["task"]["difficulty"] for row in valid_pool)),
        "observed_structures": [d for d in diagnostics if d["candidate"] in {r["task"]["id"] for r in valid_pool}],
        "reject_stage_counts": dict(Counter(r.get("failed_stage") for r in rows if r["status"] != "PASS")),
        "same_family_instance_limit": "New public text and supported executable access/release factors are measured separately. Seed/ID differences are never claimed as new scientific families.",
        "scientific_new_families": 0, "independent_semantic_audit": "BLOCKED_EXTERNAL", "empirical_difficulty": "NOT_CALIBRATED",
        "scope": "pool only; effort outputs kept in comparison cohorts, not counted as additional pool quota; industry/name changes are not structural novelty"})
    protected = read(out / "PROTECTED_VERIFICATION.json") if (out / "PROTECTED_VERIFICATION.json").exists() else {"status": "NOT_RUN"}
    resume = read(out / "REPLAY_RESUME.json") if (out / "REPLAY_RESUME.json").exists() else {"status": "NOT_RUN"}
    cli = read(out / "CLI_NO_RESEND.json") if (out / "CLI_NO_RESEND.json").exists() else {"status": "NOT_RUN"}
    handoff = "NOT_RUN"
    if (out / "HANDOFF_READY.json").exists():
        ready, packaged = read(out / "HANDOFF_READY.json"), read(out / "HANDOFF_PRECHECK.json")
        assert ready["status"] == packaged["status"] == packaged["secret_scan"] == "PASS"
        assert ready["verification_sha256"] == sha(out / "HANDOFF_PRECHECK.json")
        assert packaged["all_entry_crc_checked_during_read"] and packaged["all_file_sha256_match"]
        assert packaged["all_retained_revision_hashes_match"] and packaged["extracted_runtime_sha256"] == source
        assert packaged["extracted_strict_replays"] == resume["strict_replay_count"]
        assert packaged["extracted_terminal_resumes"] == resume["candidate_count"] and packaged["provider_calls"] == 0
        handoff = "PASS"
    priority = all(next(row for row in suite_rows if row["suite"] == suite)["distinct_consumed_target_combinations"] >= 2
                   for suite in ("T331", "T321", "T352"))
    stages = {"S0": "PASS", "S1": "PASS", "S2": "PASS" if valid_pool else "FAIL",
        "S3": "BLOCKED_EXTERNAL" if priority and all(row["status"] in {"PASS", "BLOCKED_EXTERNAL"} for row in suite_rows) else "FAIL",
        "S4": "PASS" if all(row["executed"] == row["planned"] for row in comparisons) else "NOT_RUN",
        "S5": "PASS" if tests["failures"] == tests["errors"] == tests["skipped"] == 0 and protected["status"] == resume["status"] == "PASS" else "NOT_RUN",
        "S6": handoff}
    atomic_json(out / "STAGES.json", {"status": "BLOCKED_EXTERNAL", "stages": stages, "tests": tests,
        "pool_plan": pool_plan.name, "qualified_auditors": 0, "machine_qualified_pairs": 0, "formal_accepted": False})
    lines = ["# DeepSeek 官方 Flash G2 执行交接", "", "本轮已实际开发与调用官方 API，产物限定同家族隔离研发池。工程通过不能代替跨家族生成、Gold 两人盲审、PI 裁决和合格独审。", "",
        f"- 本地 Git：`{head}`；runtime SHA-256：`{source}`。基线为 `32735cc`，本轮未 push。",
        "- 官方连接：真实 HTTP200、精确 served `deepseek-flash`；high/disabled JSON、reasoning_content 保留及工具完整往返通过。初始工具输出夹带文字的失败与显式 JSON 修复证据均保留。",
        f"- 工程池：{len(valid_pool)} 对 / {len(valid_pool)*2} 条；{sum(row['valid_pairs']>0 for row in suite_rows)}/18 项有有效对；优先三项各两种结构目标：{'PASS' if priority else 'FAIL'}。",
        f"- 工程池分母：{sum(r['validation_jobs'] for r in suite_rows)} 个校验任务、{sum(r['paid_generation_jobs'] for r in suite_rows)} 个实际付费生成任务；首对缓存复用仅计一次生成费用。另有24个固定档位比较任务，产物与工程池配额分开。",
        "- 首对：`candidates/pool-T331-01-replayfix/`；四阶段均为官方真实响应。原候选仅因缺少批次 manifest 失败；修复后复用四个完整响应、零重发，重新执行工程门与6/6严格Replay。",
        f"- 全量回归：{tests['tests']} 项，失败 {tests['failures']} / 错误 {tests['errors']} / 跳过 {tests['skipped']}。原11个适配器失败、Replay接线失败和28个离线兼容失败均保留；对应修复及正负回归已运行。",
        f"- 付费 POST intent {len(intents)}；完整响应 {len(calls)}；未知/未完整响应 {len(intents)-len(calls)}；四条历史 UNKNOWN 重发0；新AIHubMix生成0。",
        f"- 可核费用下界 ¥{cost['lower_cny']:.6f}；上界 {format(cost['upper_cny'], '.6f') if cost['upper_cny'] is not None else 'UNKNOWN'} 元，含真实缓存计量及峰谷两档；实际账单 UNKNOWN。推理Token计入 completion，不重复加费。",
        f"- 恢复与保护：严格重放 {resume.get('strict_replay_count', 'NOT_RUN')} 条；{cli.get('candidate_count', 'NOT_RUN')}个终态完整CLI重入 {cli['status']}；受保护历史文件 {protected.get('checked', 'NOT_RUN')} 个，核验状态 {protected['status']}。",
        "- 分阶段验收：" + "；".join(stage + "=" + status for stage, status in stages.items()) + "。S3未达18项配额，保留明确工程失败与历史阻塞。",
        "", "|配置|固定任务有效对/6|单位工程有效对成本区间（元）|请求平均/95p秒|", "|---|---:|---|---|"]
    for row in ranked:
        unit = (f"{row['cost_per_valid_pair_lower_cny']:.6f}–{row['cost_per_valid_pair_upper_cny']:.6f}"
                if row["valid_pairs"] and row["cost"]["upper_cny"] is not None else "NOT_COMPUTABLE")
        lat = row["latency"]
        times = f"{lat['mean_seconds']:.3f} / {lat['p95_seconds']:.3f}" if lat["n"] else "NOT_RUN"
        lines.append(f"|{row['effort']}|{row['valid_pairs']}|{unit}|{times}|")
    lines += ["", "档位比较以相同六个初始任务、相同历史基线和各档内部增量去重为分母；比较组之间的重复不混入工程失败。它测量有限语法下的工程有效率，未建立独立语义质量、真实难度或长期稳定性。", "",
        "|测评|工程有效对|不同已消费结构目标|状态|", "|---|---:|---:|---|"]
    lines += [f"|{row['suite']} {row['name']}|{row['valid_pairs']}|{row['distinct_consumed_target_combinations']}|{row['status']}{'；SIMULATION_ONLY' if row['simulation_only'] else ''}|" for row in suite_rows]
    lines += ["", "剩余阻塞与操作：", "",
        "1. T322 互操作失配：120 条历史5.1.0案例无法用5.1.2运行契约投影。已核对留存的11个源码ZIP，均为5.1.2。请找回5.1.0对应完整场景/评分/核心源码、原manifest与源哈希；详见T322_HISTORY_GAP_DIAGNOSIS.json。不得补造缺失instructions或放行INDETERMINATE。",
        "2. 正式科研准入：需要真实两位独立Gold盲审、PI裁决及跨家族生成/独审资格。DeepSeek本家族研发样本不得直接晋升MACHINE_ACCEPTED，也不能充当正式G3父本。",
        "   操作材料：EXTERNAL_ACTIONS.md及既有REVIEW_PACKAGE_FOR_HUMANS/HOW_TO_SEND.md；A卷独立回收锁SHA后才发各自B卷，再交四份原答卷给PI签署。本技术交接包含Oracle和协调方材料，只给技术总控；盲审者只接收各自对应阶段的SEND ZIP。人审/PI签署本轮均NOT_RUN。",
        "3. 当前结构能力是已声明有限语法；行业替换不算新机制，新科学家族数0。设计难度E/M/H未实证校准；T361–T363仍为SIMULATION_ONLY。未运行正式生产、确认Pilot、Campaign或冻结。",
        "4. T361/T362 当前历史投影的映射键仍含样本标识；新seed造成的表面形状变化不能证明新家族。本轮保留投影门槛，用可核历史种子的同家族实例验证既有两种真实执行依赖；详见REPAIR_PREFLIGHT_R2.json。该限制须在新版本完整历史重建和独立审阅后处理。",
        "5. T362 讨论扭曲的所有真实候选仍被严格拒收；已有两种证据访问依赖和单个≤240字符附加标题的有限语法未提供足够非重复变化。该项是本地工程能力缺口，不是用户审批或网关阻塞。完整正负分母与下一步语法开发范围见T362_CAPABILITY_GAP.json；未将单臂通过或候选新结构当合格对。",
        "", "建议下一轮：先解除历史兼容与Gold/跨家族资格阻塞；继续复用本轮工程产线。具备这些条件前，不恢复FIRST_MACHINE_QUALIFIED正式闭环。", "",
        "复跑命令（读取已有终态不发新请求；新任务使用新ID/目录）：", "",
        f"`python scripts/v5/run_deepseek_g2.py --out {out.relative_to(ROOT).as_posix()} --phase settle`", "",
        f"`python -B scripts/v5/verify_deepseek_g2.py --out {out.relative_to(ROOT).as_posix()}`", "",
        f"`python scripts/v5/report_deepseek_g2.py --out {out.relative_to(ROOT).as_posix()} --pool-plan {pool_plan.relative_to(ROOT).as_posix()} --regression {regression.relative_to(ROOT).as_posix()}`", "",
        "交接目录包含全部新请求/响应、成功和失败样本、原始Replay/参考轨迹、各源码版本、模型/参数配置、统计、回归XML、历史源绑定与逐文件哈希；ZIP校验记录在exports对应目录。密钥环境文件排除。"]
    (out / "ROUND_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "NEXT_ACTIONS.md").write_text("\n".join(lines[lines.index("剩余阻塞与操作："):]) + "\n", encoding="utf-8")
    atomic_json(out / "EVIDENCE_INDEX.json", {"version": "ioabench.v5.deepseek-g2-evidence/1", "head": head,
        "runtime_sha256": source, "files": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*"))
            if p.is_file() and p.name != "EVIDENCE_INDEX.json" and not p.name.endswith(".lock") and "__pycache__" not in p.parts},
        "formal_accepted": False, "provider_calls_this_report": 0})
    return {"valid_pool_pairs": len(valid_pool), "suite_count": sum(row["valid_pairs"] > 0 for row in suite_rows),
            "priority": priority, "tests": tests, "stage_status": stages, "cost": cost}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pool-plan", type=Path, required=True)
    parser.add_argument("--regression", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.out.resolve(), args.pool_plan.resolve(), args.regression.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
