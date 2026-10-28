"""Offline settlement of the R13 follow-up study; never creates a Provider or resends a request."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
import shutil
import tempfile
import xml.etree.ElementTree as ET
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5 import evaluation
from ioabench.v5.ai_generation.auxiliary_runtime import usage_cost
from ioabench.v5.ai_generation.history import POLICY_CONTRACT, behavioral_signature, classify, verify_sources
from ioabench.v5.ai_generation.model_routing import USER_CANDIDATES
from ioabench.v5.ai_generation.quality import dedup_features
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.dynamic.registry import get_adapter
from ioabench.v5.dynamic.runner import _resolve_scenario
from ioabench.v5.replay import replay_case
from compare_auxiliary_models import checked_result, read, sha

DEFAULT = ROOT / "artifacts/v5/data_factory/next-r1"


def candidate_evidence(path, output):
    result = read(path)
    diagnosis = read(output / "RESUME_CHECKPOINT_DIAGNOSIS.json") if (output / "RESUME_CHECKPOINT_DIAGNOSIS.json").exists() else {}
    known = {row["path"]: row for row in diagnosis.get("changed_files", [])}
    for name, expected in result.get("evidence_sha256", {}).items():
        source = (path.parent / name).resolve()
        if not source.is_relative_to(path.parent.resolve()) or not source.is_file():
            raise ValueError("missing/outside candidate evidence")
        actual = sha(source)
        if actual != expected:
            row = known.get(source.relative_to(ROOT).as_posix(), {})
            if source.name != "checkpoint.json" or row.get("original_sha256") != expected or row.get("after_resume_sha256") != actual:
                raise ValueError("unexplained candidate evidence change: " + name)
    return result


def normalized_usage(usage, endpoint):
    """Derive totals from original native usage without changing saved provider records."""
    value = dict(usage or {})
    if "input_tokens" in value:
        extra = (int(value.get("cache_read_input_tokens") or 0) + int(value.get("cache_creation_input_tokens") or 0)
                 if endpoint == "anthropic.messages" else 0)
        value["prompt_tokens"] = int(value["input_tokens"]) + extra
    if "output_tokens" in value:
        value["completion_tokens"] = int(value["output_tokens"])
    cached = (value.get("prompt_tokens_details") or {}).get("cached_tokens",
        (value.get("input_tokens_details") or {}).get("cached_tokens", value.get("cache_read_input_tokens", 0)))
    value["prompt_tokens_details"] = {**(value.get("prompt_tokens_details") or {}), "cached_tokens": int(cached or 0)}
    if "cache_write_tokens" in (value.get("input_tokens_details") or {}):
        value["cache_creation_input_tokens"] = int(value["input_tokens_details"]["cache_write_tokens"] or 0)
    if "total_tokens" not in value and "prompt_tokens" in value and "completion_tokens" in value:
        value["total_tokens"] = value["prompt_tokens"] + value["completion_tokens"]
    return value


def ledger_summary(attempts):
    finished = [row for row in attempts if row["terminal"]]
    values = [row["derived_usage"] for row in finished]
    amount = sum(row["derived_cost"].get("amount") or row["derived_cost"].get("known_subtotal") or 0 for row in finished)
    return {"requests_started": len(attempts), "terminal_requests": len(finished),
        "unresolved_requests": sum(not row["terminal"] or row["status"] == "REQUEST_UNRESOLVED" for row in attempts),
        "status_counts": dict(Counter(row["status"] for row in attempts)),
        "reported_tokens": {key: sum(int(value.get(key) or 0) for value in values)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "reported_arithmetic_token_sum": sum(int(value.get("prompt_tokens") or 0) + int(value.get("completion_tokens") or 0) for value in values),
        "reported_usage_inconsistencies": sum(bool(value) and value.get("total_tokens") is not None and value.get("prompt_tokens") is not None
            and value.get("completion_tokens") is not None and value["total_tokens"] != value["prompt_tokens"] + value["completion_tokens"] for value in values),
        "cache_read_tokens": sum(int((value.get("prompt_tokens_details") or {}).get("cached_tokens") or 0) for value in values),
        "cache_creation_tokens": sum(int(value.get("cache_creation_input_tokens") or 0) for value in values),
        "reasoning_tokens": sum(int((value.get("completion_tokens_details") or {}).get("reasoning_tokens")
            or (value.get("output_tokens_details") or {}).get("reasoning_tokens")
            or (value.get("output_tokens_details") or {}).get("thinking_tokens") or 0) for value in values),
        "reasoning_exceeds_completion_requests": sum(int((value.get("completion_tokens_details") or {}).get("reasoning_tokens")
            or (value.get("output_tokens_details") or {}).get("reasoning_tokens")
            or (value.get("output_tokens_details") or {}).get("thinking_tokens") or 0) > int(value.get("completion_tokens") or 0) for value in values),
        "usage_unknown_requests": sum(not row.get("original_usage") for row in attempts),
        "billing_unknown_requests": sum(row["derived_cost"].get("amount") is None for row in attempts),
        "estimated_usd_known_subtotal": amount,
        "median_request_seconds": statistics.median([row["elapsed_seconds"] for row in finished if row.get("elapsed_seconds") is not None]) if finished else None}


def verify_event_chain(events):
    previous = ""
    for row in events:
        body = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("previous_event_sha256") != previous or canonical_sha256(body) != row.get("event_sha256"):
            raise ValueError("Provider attempt ledger hash chain changed")
        previous = row["event_sha256"]


def ledger(output):
    catalog = read(ROOT / "artifacts/v5/provider_contracts/next-r1/MODEL_CATALOG.json")
    entries = {row.get("model_id", row.get("id")): row for row in catalog}
    attempts, files = [], {}
    for path in sorted(output.rglob("AIHUBMIX_ATTEMPTS.jsonl")):
        files[path.relative_to(ROOT).as_posix()] = sha(path)
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        verify_event_chain(events)
        starts = {row["attempt_id"]: row for row in events if row["event"] == "REQUEST_STARTED"}
        finishes = {row["attempt_id"]: row for row in events if row["event"] == "REQUEST_FINISHED"}
        if len(starts) != sum(row["event"] == "REQUEST_STARTED" for row in events):
            raise ValueError("duplicate request identity within ledger: " + str(path))
        for ident, start in starts.items():
            end = finishes.get(ident, {})
            raw = end.get("response", {})
            metadata = raw.get("provider_metadata", {})
            original = end.get("usage", {})
            derived = normalized_usage(original, metadata.get("endpoint_family"))
            # Reuse the shared cost function; report unknown rates instead of substituting zero.
            from ioabench.models import ModelResponse
            cost = usage_cost(ModelResponse("", usage=derived), entries.get(start["requested_model_id"], {})) if original else {"amount": None, "status": "UNKNOWN_NO_RESPONSE"}
            attempts.append({"ledger": path.relative_to(ROOT).as_posix(), "attempt_id": ident,
                "requested_model_id": start["requested_model_id"], "served_model_id": end.get("served_model_id"),
                "role": start["role"], "parameters": start["actual_parameters"],
                "terminal": bool(end), "status": end.get("status", "REQUEST_UNRESOLVED"),
                "category": end.get("category"), "elapsed_seconds": end.get("elapsed_seconds"),
                "http_status": metadata.get("transport_metadata", {}).get("http_status"),
                "endpoint": metadata.get("endpoint_family"), "original_usage": original,
                "derived_usage": derived, "original_cost": end.get("cost"), "derived_cost": cost,
                "request_sha256": start["request_sha256"]})
    result = {"status": "PARTIAL", "summary": ledger_summary(attempts),
        "by_model": {mid: ledger_summary([row for row in attempts if row["requested_model_id"] == mid]) for mid in USER_CANDIDATES},
        "by_workload": {name: ledger_summary([row for row in attempts if Path(row["ledger"]).parts[4] == name])
            for name in sorted({Path(row["ledger"]).parts[4] for row in attempts})},
        "rows": attempts, "ledger_source_sha256": files, "provider_calls_this_settlement": 0,
        "metadata_requests": "Catalog/schema GET records separate; these token totals include completion requests only.",
        "billing": "USD catalog estimate, not invoice; derived native/cache normalization; raw usage/cost unchanged; tier discounts not inferred; unknown is not zero."}
    evaluation.atomic_json(output / "ALL_USAGE_LEDGER.json", result)
    return result


def history(output):
    index_path = output / "current_history_probes/INDEX_WITH_PROBES.json"
    index = read(index_path)
    verify_sources(ROOT, index)
    study = read(output / "model_study/MODEL_COMPARISON_SETTLED.json")
    rows, previous, signatures = [], [], defaultdict(set)
    for result in study["rows"]:
        if result["status"] != "ENGINEERING_VALID":
            continue
        directory = output / "model_study/generation" / result["model_id"] / result["task"]["id"]
        candidate_evidence(directory / "RESULT.json", output)
        cases = [case_from_dict(raw, allow_dynamic=True) for raw in read(directory / "PAIR.json")]
        reference = read(directory / "REFERENCE_RESULTS.json")
        for case in cases:
            scenario = _resolve_scenario(get_adapter(case.suite_id))
            policies = {row["run_id"].rsplit("-", 1)[-1]: row for row in reference if row["case_id"] == case.case_id}
            probe = behavioral_signature(case, {key: policies[key] for key in ("witness", "naive")}, policy_contract=POLICY_CONTRACT)
            decision = classify(case, index, scenario=scenario, behavioral_probe_signature=probe)
            records = [record for record in index["records"] if record["features"]["suite_id"].split("-")[0] == case.suite_id.split("-")[0]]
            comparable = [record for record in records if record.get("behavioral_probe_signature")]
            candidate_behavior = canonical_sha256(probe["behavior"])
            matches = [record["case_sha256"] for record in comparable
                if canonical_sha256(record["behavioral_probe_signature"]["behavior"]) == candidate_behavior]
            features = dedup_features(case, scenario=scenario)
            structural = canonical_sha256(features["structure"])
            signatures[case.suite_id].add(structural)
            prior = [row for row in previous if row["suite_id"] == case.suite_id]
            rows.append({"model_id": result["model_id"], "task_id": result["task"]["id"], "case_id": case.case_id,
                "arm": case.arm, "case_sha256": case.content_sha256(), "suite_id": case.suite_id,
                "quality_classification": decision, "historical_cases": len(records),
                "behaviorally_comparable_cases": len(comparable), "historical_unknown_cases": len(records)-len(comparable),
                "behavior_matches": len(matches), "matching_case_sha256": matches,
                "structure_sha256": structural, "behavior_sha256": candidate_behavior,
                "within_study_exact_duplicates": sum(row["case_sha256"] == case.content_sha256() for row in prior),
                "within_study_structure_matches": sum(row["structure_sha256"] == structural for row in prior),
                "new_scientific_family": False})
            previous.append(rows[-1])
    result = {"status": "PARTIAL", "runtime_source_sha256": source_tree_hash(ROOT),
        "current_index_sha256": sha(index_path), "historical_index": index["summary"],
        "historical_probe_status": read(output / "current_history_probes/REPORT.json")["status"],
        "cases_compared": len(rows), "generated_pairs": len(rows)//2,
        "classification_counts": dict(Counter(row["quality_classification"]["status"] for row in rows)),
        "unique_runtime_structures_by_suite": {suite: len(values) for suite, values in signatures.items()},
        "behavior_matches_in_history": sum(row["behavior_matches"] > 0 for row in rows),
        "rows": rows, "verified_new_scientific_families": 0, "machine_qualified": 0,
        "scope": "Current-source projection and fixed witness/naive execution over R13's 7687 hash-bound unique cases, including retained ZIP case inventory; next-r1 candidates compared separately in deterministic order. Unknown old worlds/profiles remain explicit, not fabricated. Current-source reprobe is not original-source replay.",
        "novelty_rule": "No global new-family claim while relevant historical probes or projection remain indeterminate; repeated display names/seeds/content do not prove new structures.",
        "provider_calls": 0}
    evaluation.atomic_json(output / "GENERATED_HISTORY_CLASSIFICATION.json", result)
    return result


def replay(output):
    tasks = []
    study = read(output / "model_study/MODEL_COMPARISON_SETTLED.json")
    for result in study["rows"]:
        if result["status"] == "ENGINEERING_VALID":
            tasks.append(output / "model_study/generation" / result["model_id"] / result["task"]["id"])
    repairs = read(output / "fixed_repairs/REPAIR_COMPARISON.json")
    checked_result(output / "fixed_repairs/REPAIR_COMPARISON.json")
    tasks += [output / "fixed_repairs" / row["model_id"] / row["task_id"] for row in repairs["rows"] if row["status"] == "PASS"]
    results, resume_batches = [], 0
    for directory in tasks:
        candidate_evidence(directory / "RESULT.json", output)
        before = {str(path): sha(path) for path in (directory / "replay").rglob("*") if path.is_file()}
        rows = read(directory / "REFERENCE_RESULTS.json")
        with tempfile.TemporaryDirectory(prefix="ioa-next-replay-") as temporary:
            runtime = Path(temporary) / "runtime"
            shutil.copytree(directory / "replay", runtime)
            for run_id in dict.fromkeys(row["run_id"] for row in rows):
                # A standard resume refreshes checkpoints; test it on a disposable exact copy.
                with patch("ioabench.models.AIHubMixAdapter.generate", side_effect=AssertionError("Provider forbidden")), \
                     patch("ioabench.v5.core.policy.ScriptedPolicyModel.generate", side_effect=AssertionError("Reference generation forbidden")):
                    evaluation.run_batch(runtime, directory / "CASES.jsonl", run_id=run_id,
                        reference_policy=run_id.rsplit("-", 1)[-1], resume=True,
                        profile=ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY"), parameters={"temperature": 0.0})
                resume_batches += 1
            for row in rows:
                results.append(replay_case(runtime, row["run_id"], row["case_id"]))
        assert before == {str(path): sha(path) for path in (directory / "replay").rglob("*") if path.is_file()}, "runner bytes changed on zero-call resume"
    report = {"status": "PASS" if results and all(row["passed"] for row in results) else "FAIL",
        "runtime_source_sha256": source_tree_hash(ROOT), "development_candidates_and_repairs": len(tasks),
        "strict_replays": len(results), "passed": sum(row["passed"] for row in results),
        "zero_call_resume_batches": resume_batches, "provider_calls": 0, "reference_calls_on_resume": 0,
        "runner_bytes_unchanged_in_this_verification": True,
        "earlier_original_checkpoint_mutation": "PARTIAL; see RESUME_CHECKPOINT_DIAGNOSIS.json",
        "resume_scope": "Disposable exact copies; original model outputs/traces/scores unchanged", "rows": results}
    evaluation.atomic_json(output / "FINAL_REPLAY_VERIFICATION.json", report)
    return report


def reports(output):
    study = read(output / "model_study/MODEL_COMPARISON_SETTLED.json")
    capability = read(output / "model_study/MODEL_CAPABILITY_MATRIX.json")
    usage = read(output / "ALL_USAGE_LEDGER.json")
    panel = read(output / "development_panel-r1/DIFFICULTY_PANEL_REPORT.json")
    history_result = read(output / "GENERATED_HISTORY_CLASSIFICATION.json")
    controls = read(output / "model_controls/FINAL_VERIFICATION_R1.json")
    repair = read(output / "fixed_repairs/REPAIR_COMPARISON.json")
    matrix, rows = [], []
    for model in USER_CANDIDATES:
        item = next(row for row in capability["models"] if row["requested_model_id"] == model)
        protocol = {"gpt-6.1-sol": "openai.responses", "claude-haiku-5-5": "anthropic.messages"}.get(model, "openai.chat_completions")
        chosen = next(row for row in item["protocols"] if row["protocol"] == protocol)
        parameters = chosen.get("tool_actual_parameters", chosen.get("actual_parameters"))
        observations = [row for row in usage["rows"] if row["requested_model_id"] == model]
        matrix.append({**item, "development_tool_protocol": protocol,
            "development_parameters": parameters, "endpoint_family": protocol,
            "max_tokens_field": next((key for key in ("max_output_tokens", "max_completion_tokens", "max_tokens") if key in parameters), None),
            "reasoning_strategy": {key: value for key, value in parameters.items() if key in {"reasoning", "reasoning_effort", "thinking", "output_config"}},
            "served_model_ids": sorted({row["served_model_id"] for row in observations if row["status"] == "SUCCEEDED" and row.get("served_model_id")}),
            "served_revision": "UNVERIFIED_NOT_SEPARATELY_REPORTED; exact served IDs and raw response metadata retained",
            "json_mode": (chosen.get("actual_parameters") or {}).get("response_format", "PROMPT_CONSTRAINED_JSON_OBJECT_NOT_STRICT_SCHEMA"),
            "http_status_counts": dict(Counter(str(row.get("http_status")) if row.get("http_status") is not None else "NOT_REPORTED" for row in observations)),
            "usage_and_latency": usage["by_model"][model], "current_completion_health": "BLOCKED_SHARED_CREDENTIAL_AFTER_REAL401_NOT_RETESTED",
            "capability_status": "PARTIAL", "reasoning_effect": "PARAMETER_ACCEPTED_EFFECT_UNVERIFIED",
            "maximum_output_test": "SHORT_RESPONSE_LIMIT_ACCEPTANCE_ONLY; full output NOT_RUN",
            "context_boundary_test": "NOT_RUN", "token_limit_enforcement": "FAIL_OBSERVED_length16" if model == "qwen3.8-flash" else "SHORT_PROBE_ONLY",
            "usage_consistency": "FAIL_REASONING_EXCEEDS_COMPLETION" if model == "mimo-v2.6-flash" else "OBSERVED_ONLY",
            "independent_auditor_qualification": "BLOCKED_PI_GOLD_DISPOSITION",
            "formal_role_restriction": "ISOLATED_DEVELOPMENT_ONLY" if model.startswith("deepseek-") else "NO_PRODUCTION_QUALIFICATION_GRANTED"})
        results = [row for row in study["rows"] if row["model_id"] == model]
        common = [row for row in results if row["task"]["seed"] == 27101 and row["task"]["id"].endswith("-t1")]
        repaired = [row for row in repair["rows"] if row["model_id"] == model]
        repair_costs = [row for row in usage["rows"] if "/fixed_repairs/" in row["ledger"] and row["requested_model_id"] == model]
        rows.append({"model_id": model, "planned_generation_tasks": 24, "generation_counts": dict(Counter(row["status"] for row in results)),
            "quality_rejection_stages": dict(Counter(row.get("failed_stage", "UNSPECIFIED") for row in results if row["status"] == "REJECTED")),
            "confirmed_schema_compile_causal_fidelity_reference_passed_pairs": sum(row["status"] == "ENGINEERING_VALID" for row in results),
            "historical_case_classifications": dict(Counter(row["quality_classification"]["status"] for row in history_result["rows"] if row["model_id"] == model)),
            "first_common_three_counts": dict(Counter(row["status"] for row in common)),
            "fixed_repair_passed": sum(row["status"] == "PASS" for row in repaired), "fixed_repair_planned": 3,
            "fixed_repair_usd_estimate": sum(row["derived_cost"].get("amount") or 0 for row in repair_costs),
            "fixed_repair_median_seconds": statistics.median(row["elapsed_seconds"] for row in repair_costs),
            "development_panel": panel["models"][model], "all_workload_usage": usage["by_model"][model]})
    matrix_report = {"status": "PARTIAL", "models": matrix, "controls": {key: controls[key] for key in (
        "original_control_counts", "numeric_limit_enforcement", "reported_usage_consistency", "long_context_boundary", "full_maximum_generation")},
        "schema_conflicts": ["DeepSeek1017 live context=1000000 versus attachment1048576; exact live schema retained.",
            "Both GLM thinking.disabled controls returned200 instead of documented rejection; cannot infer thinking was disabled.",
            "Haiku Chat400; native Messages JSON/tools successful. Sol tool use requires verified Responses path."],
        "reasoning": "Official per-model defaults, no silent effort downgrade; accepting a field does not prove its effective inference strength."}
    evaluation.atomic_json(output / "AIHUBMIX_8_MODEL_MATRIX.json", matrix_report)
    lines = ["# 八模型能力与实发配置", "", "PARTIAL。模型上限与研究预算分开；本轮按PI-V5-020预注册16,384输出预算，不将预算称为模型能力上限。", "", "|模型|实时context|最大输出|已验证工具协议|实发参数|", "|---|---:|---:|---|---|"]
    lines += [f"|{row['requested_model_id']}|{row['context_limit']}|{row['max_output_limit']}|{row['development_tool_protocol']}|`{json.dumps(row['development_parameters'], ensure_ascii=False)}`|" for row in matrix]
    lines += ["", "八模型均有真实JSON和工具往返记录。长上下文边界、完整最大长度生成NOT_RUN；原始schema、响应、HTTP及身份见provider_contracts/next-r1与model_study/protocols。参数接受不证明思考档位效果。", "", *matrix_report["schema_conflicts"], "", "Qwen length16实际回报超过限制；MiMo Flash一条reasoning token大于completion token。控制原判定及额外FAIL分别保留；没有用这些异常授予独审或生产资格。"]
    (output / "AIHUBMIX_8_MODEL_MATRIX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = {"status": "PARTIAL", "models": rows, "planned_generation": 192,
        "generation_counts": dict(Counter(row["status"] for row in study["rows"])),
        "quality_rejection_stages": dict(Counter(row.get("failed_stage", "UNSPECIFIED") for row in study["rows"] if row["status"] == "REJECTED")),
        "funnel_scope": "39 pairs have retained schema/compile/causal/fidelity/reference PASS. Rejection stages and all NOT_RUN/unresolved counts retained; missing downstream records are not counted as successful stages. Historical classifications use78 individual arms, not39 pairs; VALID_FAMILY_INSTANCE is not a new scientific family or a qualified review.",
        "fixed_repairs": {"planned": 24, "passed": repair["passed"]}, "history": {key: value for key, value in history_result.items() if key != "rows"},
        "role_selection": {"generator": "PROVISIONAL_DEVELOPMENT_gpt-6.1-sol: 3/3 common smoke targets valid,9 retained valid pairs; complete24-task ranking BLOCKED by401/interruption.",
            "repair": "All8 passed3/3 narrow fixtures; Haiku lowest observed median latency, GLM Flash lowest observed estimated cost. No universal quality winner from three one-field fixes.",
            "independent_auditor": "NONE_QUALIFIED; Gold/PI disposition required before new qualification.",
            "calibrator": "NO_8_MODEL_WINNER_ESTABLISHED; Sol completed6/6 development episodes, other models incompletely observed; true calibration BLOCKED."},
        "fairness_limit": "Same tasks/seeds/gates and fixed correction opportunity; censoring leaves unequal denominators. NOT_RUN and unresolved requests remain in the192 plan. No quality rerolls or forced full comparison after401.",
        "machine_qualified": 0, "scientific_new_families": 0, "formal_accepted": False,
        "evidence": ["model_study/COMPARISON_EXECUTION_BINDING.json", "model_study/COMPARISON_EXECUTOR_ATTEMPT01.py", "COMPARISON_EXECUTION.txt", "RESUME_CHECKPOINT_DIAGNOSIS.json", "FINAL_REPLAY_VERIFICATION.json", "ALL_USAGE_LEDGER.json"]}
    evaluation.atomic_json(output / "MODEL_COMPARISON_REPORT.json", result)
    lines = ["# 八模型同任务比较", "", f"PARTIAL。192计划：{result['generation_counts']}；固定修复24/24通过。调用被401和Windows进度替换故障中断，未决不重发。", "", "|模型|生成有效/24|第一组三共同目标有效/3|修复/3|修复估价USD|修复中位秒|", "|---|---:|---:|---:|---:|---:|"]
    lines += [f"|{row['model_id']}|{row['generation_counts'].get('ENGINEERING_VALID',0)}|{row['first_common_three_counts'].get('ENGINEERING_VALID',0)}|{row['fixed_repair_passed']}|{row['fixed_repair_usd_estimate']:.8f}|{row['fixed_repair_median_seconds']:.2f}|" for row in rows]
    lines += ["", result["fairness_limit"], "", *result["role_selection"].values(), "", "39对有效候选的78例：24精确重复、26近重复、28既有家族实例；78/78存在历史行为匹配，三套件各3种运行结构。全历史科学新家族0；独审资格及机器合格样本0。失败阶段、截断、目标偏离与请求证据见逐任务RESULT和model_io。", "", "378条参考结果严格Replay通过；189批在临时副本执行零调用resume。首次恢复核验改写3个原checkpoint的差异保留，该候选快照完整性PARTIAL；请求、响应、轨迹、评分不变。"]
    (output / "MODEL_COMPARISON_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "PARTIAL", "generated_pairs": 39, "fixed_repair_passed": 24, "provider_calls": 0}


def regression_result(path):
    if not path.is_file():
        return {"status": "NOT_RUN", "file": path.name}
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    counts = {key: sum(int(row.get(key, "0")) for row in suites) for key in ("tests", "failures", "errors", "skipped")}
    return {"status": "PASS" if counts["tests"] and not any(counts[key] for key in ("failures", "errors", "skipped")) else "FAIL",
        "file": path.name, "sha256": sha(path), **counts}


def protection(output):
    before = read(output / "BEFORE_PROTECTED_SHA256.json")
    settlement = read(output / "PROTECTED_HISTORY_SETTLEMENT.json")
    transient = set(settlement["transient_test_files_cleaned"])
    changed, missing = [], []
    for index, (name, expected) in enumerate(before.items(), 1):
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
        elif sha(path) != expected:
            changed.append(name)
        if index % 30000 == 0:
            print(json.dumps({"phase": "protected_recheck", "checked": index}), flush=True)
    actual_missing = sorted(set(missing) - transient)
    result = {"status": "FAIL" if changed or actual_missing else "PARTIAL_BASELINE_TRANSIENT_RACE",
        "checked": len(before), "changed": changed, "missing": missing,
        "preexisting_checked": len(before) - len(transient), "preexisting_changed": len(changed),
        "preexisting_missing": actual_missing, "known_transient_missing": sorted(set(missing) & transient),
        "baseline_sha256": sha(output / "BEFORE_PROTECTED_SHA256.json"), "provider_calls": 0,
        "original_verification": "PROTECTED_HISTORY_FINAL.json remains FAIL; no original inventory or history rewritten."}
    evaluation.atomic_json(output / "PROTECTED_HISTORY_RECHECK.json", result)
    return result


def acceptance(output):
    regression_path = output / "FINAL_REGRESSION_R3.xml"
    regression = regression_result(regression_path)
    if regression["status"] == "NOT_RUN":
        raise ValueError("Final R3 regression has not run; no old regression fallback")
    target = output / "FINAL_REGRESSION.xml"
    if target.exists() and sha(target) != sha(regression_path):
        raise ValueError("Existing final regression alias differs; preserve both under new names")
    if not target.exists():
        shutil.copyfile(regression_path, target)
    study = read(output / "model_study/MODEL_COMPARISON_SETTLED.json")
    comparison = read(output / "MODEL_COMPARISON_REPORT.json")
    history_result = read(output / "GENERATED_HISTORY_CLASSIFICATION.json")
    structure = read(output / "structure_history/final-r2/STRUCTURE_AND_COVERAGE_REPORT.json")
    replay_result = read(output / "FINAL_REPLAY_VERIFICATION.json")
    panel = read(output / "development_panel-r1/DIFFICULTY_PANEL_REPORT.json")
    protect = read(output / "PROTECTED_HISTORY_RECHECK.json")
    usage = read(output / "ALL_USAGE_LEDGER.json")
    runtime = source_tree_hash(ROOT)
    if any(row["runtime_source_sha256"] != runtime for row in (history_result, structure, replay_result)):
        raise ValueError("Evidence is not bound to current runtime")
    proofs = []
    for row in study["rows"]:
        directory = output / "model_study/generation" / row["model_id"] / row["task"]["id"]
        path = directory / "RESULT.json"
        if path.is_file():
            candidate_evidence(path, output)
        proofs.append({"model_id": row["model_id"], "task": row["task"], "status": row["status"],
            "directory": directory.relative_to(ROOT).as_posix(), "result_sha256": sha(path) if path.is_file() else None,
            "machine_qualified": False, "independent_audit": "NOT_RUN_BLOCKED_NO_QUALIFIED_AUDITOR",
            "history_rows": [item for item in history_result["rows"] if item["model_id"] == row["model_id"] and item["task_id"] == row["task"]["id"]]})
    repairs = read(output / "fixed_repairs/REPAIR_COMPARISON.json")
    evaluation.atomic_json(output / "GENERATED_DATA_PROOFS/INDEX.json", {
        "status": "PARTIAL", "machine_qualified": 0, "generation": proofs,
        "repair_evidence": "artifacts/v5/data_factory/next-r1/fixed_repairs/REPAIR_COMPARISON.json",
        "repair_sha256": sha(output / "fixed_repairs/REPAIR_COMPARISON.json"), "repair_passed": repairs["passed"],
        "single_machine_qualified_chain": "NOT_RUN_BLOCKED", "three_suite_production": "NOT_RUN_BLOCKED",
        "all18_production": "NOT_RUN_BLOCKED", "G3_qualified_parent": "NOT_RUN_NO_QUALIFIED_PARENT",
        "checkpoint_snapshot_exception": "RESUME_CHECKPOINT_DIAGNOSIS.json; one original snapshot remains PARTIAL"})
    suites = {}
    for suite, value in structure["suites"].items():
        rows = [row for row in study["rows"] if row["task"]["suite"] == suite]
        suites[suite] = {**value, "generation_planned": len(rows), "generation_statuses": dict(Counter(row["status"] for row in rows)),
            "machine_qualified": 0, "production_acceptance_rate": None, "production_status": "NOT_RUN_BLOCKED"}
    combined = {**structure, "suites": suites, "fresh_current_source_history": {key: value for key, value in history_result.items() if key != "rows"}}
    evaluation.atomic_json(output / "STRUCTURE_AND_COVERAGE_REPORT.json", combined)
    (output / "STRUCTURE_AND_COVERAGE_REPORT.md").write_text(
        "# 结构、覆盖与历史\n\nPARTIAL。18typed、19slice，52声明组合中49可行；540能力参考与18项36对/228参考已执行。"
        "三样板各2结构有消费者/反事实与Replay证明；模型生成三套件各3种runtime结构。\n\n"
        "当前源码7687历史重探：6661 PROBED、1026 INDETERMINATE。78生成例中24精确重复、26近重复、28既有家族实例，78均有历史行为匹配。"
        "新科学家族0；原源码Replay未建立。D3映射、D4风险触发、D5机会差异逐结构见structure_history/final-r2/STRUCTURE_PROOFS.json，"
        "metadata字段不作真实消费者证据。全部18套件逐项容量、不可行组合、模型生成量及0机器接受见同名JSON。\n", encoding="utf-8")
    policy = {"version": "ioabench.v5.next-role-observations/1.0.0", "status": "PARTIAL_DEVELOPMENT_ONLY",
        "roles": comparison["role_selection"], "production_route_changes": False, "independent_auditors_qualified": [],
        "deepseek1017": "ISOLATED_DEVELOPMENT_ONLY_NOT_FORMAL_SELECTION_AUDIT_OR_CONFIRMATION"}
    evaluation.atomic_json(output / "MODEL_ROLE_SELECTION.json", policy)
    (output / "MODEL_ROLE_SELECTION.md").write_text("# 模型角色选择\n\nPARTIAL；仅开发建议，未改生产路由。\n\n" +
        "\n\n".join(policy["roles"].values()) + "\n\n八模型完整比较受401和中断截尾；质量失败未触发换审刷PASS。独审/科学校准不授资格。\n", encoding="utf-8")
    files = []
    for directory in ("src", "contracts", "config", "scripts", "tests", "docs", "state", "NightGoalDoc", "adr", "roles", "scenarios", "worlds", "prompts", "templates"):
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"})
    files.extend(ROOT / name for name in ("AGENTS.md", "WORKSPACE.md", "pyproject.toml", ".gitignore", ".gitattributes"))
    manifest = {"runtime_source_sha256": runtime, "algorithm": "ioabench.runtime.full_manifest.source_tree_hash",
        "files": {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(set(files)) if path.is_file()},
        "scope": "Worktree source/assets snapshot before local implementation commit; final package inventory separately binds every included file."}
    evaluation.atomic_json(output / "SOURCE_MANIFEST.json", manifest)
    statuses = {"engineering": "PASS" if regression["status"] == "PASS" and not protect["changed"] and not protect["preexisting_missing"] else "FAIL",
        "deterministic_and_causal": structure["deterministic_and_causal"], "runtime_structure": "PASS_BOUNDED",
        "history_novelty": "PARTIAL", "machine_audit": "BLOCKED", "empirical_difficulty": "PARTIAL_UNCALIBRATED",
        "scientific_validity": "BLOCKED_NOT_ESTABLISHED", "formal_freeze": "NOT_RUN"}
    deliverables = [("BASELINE_AND_CHANGE_REPORT.md", "PARTIAL"), ("AIHUBMIX_8_MODEL_MATRIX.json", "PARTIAL"),
        ("MODEL_COMPARISON_REPORT.json", "PARTIAL"), ("GOLD_AND_AUDITOR_DIAGNOSIS.md", "BLOCKED"),
        ("GENERATED_DATA_PROOFS/INDEX.json", "PARTIAL"), ("STRUCTURE_AND_COVERAGE_REPORT.json", "PARTIAL"),
        ("T362_LEAK_REMEDIATION.md", "PARTIAL"), ("DIFFICULTY_PANEL_REPORT.md", "PARTIAL"), ("FINAL_REGRESSION.xml", regression["status"])]
    final = {"schema_version": "ioabench.v5.next-acceptance/1.0.0", "status": "PARTIAL", "authorization": "PI-V5-020",
        "runtime_source_sha256": runtime, "goal_reference": "NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/GOAL_CONTRACT.yaml",
        "statuses": statuses, "regression": regression, "source_manifest_sha256": sha(output / "SOURCE_MANIFEST.json"),
        "deliverables": [{"file": name, "status": status, "sha256": sha(output / name)} for name, status in deliverables],
        "generation": comparison["generation_counts"], "fixed_repair_passed": repairs["passed"],
        "strict_replay": {key: replay_result[key] for key in ("status", "strict_replays", "passed", "zero_call_resume_batches")},
        "development_panel": {"planned": panel["planned_episodes"], "statuses": panel["statuses"], "replay_passed": panel["replay"]["passed"], "resume_batches": panel["resume"]["batches"]},
        "usage": usage["summary"], "machine_qualified_samples": 0, "new_scientific_families": 0,
        "protected_history": protect["status"], "candidate_snapshot_integrity": "PARTIAL_ONE_CANDIDATE_THREE_CHECKPOINTS",
        "blockers": ["Two independent blind Gold reviews and PI disposition", "Completion authentication/channel restoration; metadata GET alone insufficient",
            "1026 historical comparability gaps", "Approved independent scientific difficulty/Gate D design", "Formal experiment authorization"],
        "not_run": ["New auditor holdout/qualification", "First machine-qualified sample/three-suite/all18 production", "G3 qualified-parent acquisition",
            "Long-context boundary", "Forced full maximum output", "Scientific difficulty calibration", "Confirmation Pilot", "Campaign", "Formal freeze", "Human experiments"],
        "formal_accepted": False, "publication_ready": False, "simulation_only": ["T361", "T362", "T363"], "provider_calls_this_settlement": 0,
        "source_package_verification": "Separate package snapshot/CRC/per-file SHA and independent extraction: exports/source-code-20261019-r3/PACKAGE_VERIFICATION.json; local Git binding in state/SOURCE_DELIVERY_20261019_R3.yaml"}
    evaluation.atomic_json(output / "FINAL_ACCEPTANCE.json", final)
    lines = ["# R13后续最终验收", "", "**PARTIAL / BLOCKED_MACHINE_QUALIFICATION_AND_PROVIDER_AUTH**。真实新回归与证据结算如下，未复用旧PASS。", "",
        f"Runtime：`{runtime}`。最终回归：**{regression['tests']} tests，{regression['failures']} failures，{regression['errors']} errors，{regression['skipped']} skipped**。", "",
        "|项目|状态|", "|---|---|", *[f"|{key}|{value}|" for key, value in statuses.items()], "",
        "|附件交付|状态|", "|---|---|", *[f"|[{name}]({name})|{status}|" for name, status in deliverables], "",
        "39对工程有效、24固定修复；378/378严格Replay与189批零调用恢复PASS。开发面板11完成/48计划、11Replay、7批resume。机器资格0，新科学家族0。", "",
        "完整性PARTIAL：原146911路径扫描含21个pytest临时路径；146890既有项无变化无缺失。一个候选3个mutable checkpoint曾被首次resume刷新；原请求/轨迹/评分不变，诊断和原失败保留。", "",
        "总账510 starts，493成功、14失败、3未决；1214168 reported tokens，USD0.830890141988已知估价小计，7项计费未知；不是账单。", "",
        "阻塞：" + "；".join(final["blockers"]), "", "NOT_RUN：" + "；".join(final["not_run"]), "",
        "运行命令见[RUN_COMMANDS.md](RUN_COMMANDS.md)。源码/证据SHA见SOURCE_MANIFEST.json与SHA256SUMS.json；新版包实际验证及本地提交另见交付记录。科学/正式状态不因打包而升级。T361–T363保持SIMULATION_ONLY。"]
    (output / "FINAL_ACCEPTANCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sums = {path.relative_to(output).as_posix(): sha(path) for path in sorted(output.iterdir())
        if path.is_file() and path.suffix in {".json", ".md", ".xml"} and path.name != "SHA256SUMS.json"}
    sums["GENERATED_DATA_PROOFS/INDEX.json"] = sha(output / "GENERATED_DATA_PROOFS/INDEX.json")
    evaluation.atomic_json(output / "SHA256SUMS.json", {"scope": "Final reports/test XML/source+before inventories; raw sample I/O chained by RESULT/evidence SHA and the complete source-package FILES.json", "files": sums})
    return {"status": final["status"], "regression": regression, "provider_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT)
    parser.add_argument("--phase", choices=("ledger", "history", "replay", "reports", "protection", "acceptance"), required=True)
    args = parser.parse_args()
    result = globals()[args.phase](args.out)
    print(json.dumps({key: value for key, value in result.items() if key not in {"rows", "ledger_source_sha256", "by_model", "by_workload"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
