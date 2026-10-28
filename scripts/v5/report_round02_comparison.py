"""Recompute Round02 denominators, costs and recommendations from immutable attempts."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from ioabench.models import ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract
from ioabench.v5.evaluation import atomic_json
from compare_auxiliary_models import read, sha
from settle_provider_round02 import wilson


def csv_write(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                          for key, value in row.items()} for row in rows)


def attempts(out):
    return [{"evidence": str(path.relative_to(out)).replace("\\", "/"), "evidence_sha256": sha(path), **read(path)}
            for path in sorted(out.rglob("attempt-*.json"))]


def cost(rows):
    amounts = [row.get("cost", {}).get("amount") for row in rows]
    return {"known_subtotal_usd": sum(value for value in amounts if isinstance(value, (int, float))),
            "missing_usage_or_rate_attempts": sum(value is None for value in amounts),
            "total_estimated_usd": sum(amounts) if amounts and all(value is not None for value in amounts) else None,
            "actual_bill_usd": None, "basis": "live catalog rates and returned usage; never AA prices or actual bill"}


def reasoning_tokens(usage):
    for key, field in (("completion_tokens_details", "reasoning_tokens"), ("output_tokens_details", "thinking_tokens")):
        if field in (usage.get(key) or {}):
            return usage[key][field]
    return usage.get("reasoning_tokens")


def response_category(row):
    response = row.get("response", {})
    if response.get("finish_reason") == "refusal" or response.get("provider_metadata", {}).get("stop_reason") == "refusal":
        return "PROVIDER_POLICY_REFUSAL"
    return row.get("category", row["status"])


def request_rows(out, records, catalog):
    result = []
    for item in records:
        response, usage = item.get("response", {}), item.get("usage", {})
        metadata = response.get("provider_metadata", {})
        status = (metadata.get("transport_metadata") or {}).get("http_status")
        if status is None:
            match = re.search(r'"http_status"\s*:\s*"?(\d{3})', item.get("error", ""))
            status = int(match[1]) if match else "UNKNOWN"
        params = item.get("actual_parameters", {})
        protocol = metadata.get("endpoint_family")
        binding = out / Path(item["evidence"]).parent / "REQUEST_BINDING.json"
        if not protocol and binding.exists():
            contracts = read(binding).get("binding", {}).get("contracts", [])
            protocol = next((r["profile"]["capabilities"].get("endpoint_family") for r in contracts
                             if r["profile"]["model_id"] == item["requested_model_id"]), None)
        entry = next((r for r in catalog if (r.get("model_id") or r.get("id")) == item["requested_model_id"]), {})
        schema_path = out / "schemas" / (item["requested_model_id"] + ".json")
        family = read(schema_path).get("vendor", "UNKNOWN") if schema_path.exists() else "UNKNOWN"
        parts = Path(item["evidence"]).parts
        outcome = out.joinpath(*parts[:3], "RESULT.json") if parts[0] in {"quality", "protocols"} else None
        stage = read(outcome) if outcome and outcome.exists() else {}
        text = response.get("text")
        try:
            json.loads(text)
            json_parse = "PASS"
        except (TypeError, ValueError):
            json_parse = "FAIL" if text is not None else "NOT_RUN"
        result.append({"display_name": entry.get("model_name", "UNKNOWN"), "exact_api_id": item["requested_model_id"],
            "served_id": item.get("served_model_id", "UNKNOWN"), "family": family,
            "endpoint": "https://api.inferera.com/v1" + {"anthropic.messages": "/messages", "openai.responses": "/responses"}.get(protocol, "/chat/completions"),
            "protocol": protocol or "UNKNOWN", "effort_sent": params.get("reasoning_effort", params.get("reasoning", params.get("output_config", {})).get("effort", "OMITTED")),
            "thinking_mode": params.get("thinking", "MODEL_DEFAULT"), "max_output_sent": next((params[k] for k in ("max_tokens", "max_completion_tokens", "max_output_tokens") if k in params), "UNKNOWN"),
            "actual_parameters": params, "request_id": item["request_id"], "request_sha256": item["request_sha256"],
            "input_tokens": usage.get("prompt_tokens", "UNKNOWN"), "reasoning_tokens": reasoning_tokens(usage) if reasoning_tokens(usage) is not None else "UNKNOWN",
            "output_tokens": usage.get("completion_tokens", "UNKNOWN"), "price_source": "MODEL_CATALOG.json#" + item["requested_model_id"],
            "usd_estimated": item.get("cost", {}).get("amount", "UNKNOWN"), "elapsed_ms": item.get("elapsed_seconds", 0)*1000,
            "http_code": status, "finish_reason": response.get("finish_reason", "UNKNOWN"), "json_parse": json_parse,
            "schema_pass": stage.get("tasks", {}).get("json", "NOT_RUN"), "tool_loop_pass": stage.get("tasks", {}).get("tool-loop", "NOT_RUN"),
            "quality_pass": stage.get("status", "NOT_RUN") if parts[0] == "quality" else "NOT_RUN",
            "status": item["status"], "diagnostic_category": response_category(item), "evidence": item["evidence"], "evidence_sha": item["evidence_sha256"]})
    return result


def scorecard(out, plan, records):
    rows = []
    for config in plan["configs"]:
        cid = config["id"]
        r = [read(path) for path in (out / "protocols" / cid).glob("r*/RESULT.json")]
        q = [read(path) for path in (out / "quality" / cid).glob("*/RESULT.json")]
        bound = [row for row in records if row["evidence"].startswith(("protocols/" + cid + "/", "quality/" + cid + "/"))]
        transport = [row for row in bound if (row.get("response", {}).get("provider_metadata", {}).get("transport_metadata") or {}).get("http_status") == 200]
        pairs = [row for row in q if row["task"].startswith(("T321", "T331", "T352"))]
        valid = sum(row["status"] == "ENGINEERING_VALID" and row.get("nonduplicate") is True for row in pairs)
        passed_q = valid + sum(row["status"] == "PASS" for row in q)
        passed_r = sum(value == "PASS" for row in r for value in row["tasks"].values())
        executed_r = sum(value in {"PASS", "FAIL"} for row in r for value in row["tasks"].values())
        estimate = cost(bound)
        params = config["parameters"]
        levels = params.get("reasoning_effort", params.get("reasoning", params.get("output_config", {})).get("effort"))
        row = {"config_id": cid, "exact_api_id": config["model"], "protocol": config["protocol"],
            "endpoint": "https://api.inferera.com/v1", "effort_sent": levels or "OMITTED",
            "thinking_mode": params.get("thinking", "MODEL_DEFAULT"), "R_output_budget": 4096, "Q_output_budget": 16384,
            "R_planned": 8, "R_pass": passed_r, "R_fail": executed_r - passed_r, "R_NOT_RUN": 8 - executed_r,
            "Q_planned": 8, "Q_pass": passed_q, "Q_completed": len(q), "Q_fail": len(q) - passed_q, "Q_NOT_RUN": 8-len(q),
            "engineering_pairs_planned": 6, "engineering_nonduplicate_valid_pairs": valid,
            "engineering_pairs_attempted": len(pairs),
            "engineering_pair_Wilson95": wilson(valid, len(pairs)), "R_Wilson95": wilson(passed_r, executed_r),
            "provider_attempts": len(bound), "http200": len(transport),
            "unresolved": sum(item["status"] in {"REQUEST_UNRESOLVED", "REQUEST_STARTED"} for item in bound),
            "usage_reported": ({key: sum(item.get("usage", {}).get(key, 0) for item in bound)
                                   for key in ("prompt_tokens", "completion_tokens", "total_tokens")} if bound else None),
            "missing_usage_attempts": sum(not item.get("usage") for item in bound),
            "reasoning_tokens_reported_known_subtotal": sum(reasoning_tokens(item.get("usage", {})) or 0 for item in bound),
            "missing_reasoning_breakdown": sum(reasoning_tokens(item.get("usage", {})) is None for item in bound),
            "median_elapsed_ms": statistics.median(item["elapsed_seconds"]*1000 for item in bound if "elapsed_seconds" in item) if bound else None,
            "cost": estimate, "engineering_cost_per_pair_usd": estimate["total_estimated_usd"] / valid if valid and estimate["total_estimated_usd"] is not None else None,
            "machine_qualified_cost_per_pair": "NOT_COMPUTABLE", "auditor_qualified": False,
            "confidence": ("STABLE_OBSERVED_SHORT_WINDOW_BEFORE_AUTH_STOP" if (out / "STOP.json").exists() else "STABLE_OBSERVED_SHORT_WINDOW") if len(r) == 2 and all(item["status"] == "PASS" for item in r) else "PROVISIONAL_OR_INCOMPLETE",
            "quality_evidence": [str(path.relative_to(out)).replace("\\", "/") for path in (out / "quality" / cid).glob("*/RESULT.json")],
            "failures": dict(Counter(response_category(item) for item in bound if item["status"] != "SUCCEEDED")),
            "served_ids": sorted({item.get("served_model_id", "UNKNOWN") for item in bound}),
            "parameter_binding": config}
        rows.append(row)
    eligible = [row for row in rows if row["Q_completed"] == 8 and row["R_pass"] == 8
                and row["engineering_cost_per_pair_usd"] is not None and row["engineering_nonduplicate_valid_pairs"] > 0]
    min_cost = min((row["engineering_cost_per_pair_usd"] for row in eligible), default=None)
    min_latency = min((row["median_elapsed_ms"] for row in eligible), default=None)
    for row in rows:
        row["weighted_engineering_score"] = (
            .35*row["engineering_nonduplicate_valid_pairs"]/6 + .25*row["Q_pass"]/8
            + .20*row["http200"]/row["provider_attempts"]
            + .10*min_cost/row["engineering_cost_per_pair_usd"] + .10*min_latency/row["median_elapsed_ms"]
            if row in eligible else None)
    return rows


def build(out):
    plan_path = out / "BENCHMARK_TASKSET_FROZEN.json"
    plan = read(plan_path) if plan_path.exists() else {"configs": [], "tasks": []}
    records = attempts(out)
    rows = scorecard(out, plan, records)
    csv_write(out / "SCORECARD_ALL_MODELS.csv", rows)
    atomic_json(out / "SCORECARD_ALL_MODELS.json", rows)
    catalog = read(out / "MODEL_CATALOG.json")
    csv_write(out / "REQUEST_RESULTS.csv", request_rows(out, records, catalog))
    protocol_rows = []
    for config in read(out / "PROTOCOL_PLAN.json")["configs"]:
        paths = list((out / "protocols" / config["id"]).glob("*/RESULT.json"))
        supplemental = [p for p in (out / "protocols").glob(config["model"] + "--native-default/*/RESULT.json")]
        protocol_rows.append({"exact_api_id": config["model"], "default_protocol": config["protocol"],
            "default_result": read(paths[0])["status"] if paths else config.get("status", "NOT_RUN"),
            "supplemental_results": [read(p) for p in supplemental],
            "reason": config.get("reason"), "quality": "BLOCKED_AUTH_PERMISSION" if (out / "STOP.json").exists() else "SEE_SCORECARD"})
    csv_write(out / "ALL_CANDIDATE_DISPOSITIONS.csv", protocol_rows)
    catalog_rows = []
    for path in sorted((out / "schemas").glob("*.json")):
        schema = read(path)
        entry = next((item for item in catalog if (item.get("model_id") or item.get("id")) == path.stem), {})
        catalog_rows.append({"exact_api_id": path.stem, "display_name": entry.get("model_name"),
            "family": schema.get("vendor"), "context": schema.get("specs", {}).get("context_window"),
            "max_output": schema.get("specs", {}).get("max_output_tokens"), "pricing": entry.get("pricing"),
            "pricing_lines": entry.get("pricing_lines"), "protocol_claims": schema.get("protocols"),
            "reasoning_claims": schema.get("specs", {}).get("reasoning_options"), "schema_sha256": sha(path),
            "actual_POST": sum(item.get("requested_model_id") == path.stem for item in records),
            "actual_http200": sum(item.get("requested_model_id") == path.stem and
                (item.get("response", {}).get("provider_metadata", {}).get("transport_metadata") or {}).get("http_status") == 200 for item in records),
            "official_source_boundary": "saved OFFICIAL_* and cited per-model schema; claims are not measured limits",
            "stream_TTFT": "NOT_RUN", "context_boundary": "NOT_RUN"})
    csv_write(out / "MODEL_CATALOG_AND_OFFICIAL_DOC_MATRIX.csv", catalog_rows)
    (out / "PROFILE_MATRIX.yaml").write_text(yaml.safe_dump({"version": plan.get("version"), "catalog": catalog_rows,
        "configurations": rows, "scientific_qualification": "BLOCKED_GOLD_PI", "frozen_SUT_changed": False},
        allow_unicode=True, sort_keys=False), encoding="utf-8")
    eligible = [row for row in rows if row["weighted_engineering_score"] is not None and
                not row["exact_api_id"].startswith("deepseek-")]
    ranked = sorted(eligible, key=lambda row: row["weighted_engineering_score"], reverse=True)
    cost_ranked = sorted(eligible, key=lambda row: row["engineering_cost_per_pair_usd"])
    frontier = [row["config_id"] for row in eligible if not any(
        other["engineering_nonduplicate_valid_pairs"] >= row["engineering_nonduplicate_valid_pairs"]
        and other["engineering_cost_per_pair_usd"] <= row["engineering_cost_per_pair_usd"]
        and other["median_elapsed_ms"] <= row["median_elapsed_ms"]
        and (other["engineering_nonduplicate_valid_pairs"], -other["engineering_cost_per_pair_usd"], -other["median_elapsed_ms"])
            != (row["engineering_nonduplicate_valid_pairs"], -row["engineering_cost_per_pair_usd"], -row["median_elapsed_ms"])
        for other in eligible)]
    atomic_json(out / "PARETO_CONFIGS.json", {"dimensions": ["valid_pair_yield", "unit_engineering_cost", "median_latency"],
        "frontier": frontier, "scope": "completed same-task eligible configurations only"})
    choices = {"COMPLEX_GENERATOR": ranked[:1], "MAIN_GENERATOR": ranked[:1],
        "LOW_COST_VALID_GENERATOR": cost_ranked[:1], "BATCH_EXPANSION": cost_ranked[:1],
        "REPAIR": [row for row in ranked if any(read(out / path).get("task") == "causal-repair" and
                         read(out / path)["status"] == "PASS" for path in row["quality_evidence"])][:1]}
    family = {row["exact_api_id"]: row["family"] for row in catalog_rows}
    main_family = family.get(ranked[0]["exact_api_id"]) if ranked else None
    choices["FALLBACK"] = [row for row in ranked if family.get(row["exact_api_id"]) != main_family][:1]
    choices["INDEPENDENT_AUDITOR_CANDIDATE_NOT_QUALIFIED"] = choices["FALLBACK"]
    selection = {key: value[0]["config_id"] if value else None for key, value in choices.items()}
    atomic_json(out / "ROLE_RECOMMENDATIONS.json", {"status": "PROVISIONAL_ENGINEERING_ONLY" if eligible else "NOT_ESTABLISHED",
        "recommendations": selection, "auditor_qualified": False, "first_machine_qualified": "BLOCKED",
        "cost_includes": "this configuration's R/Q attempts and failures; startup protocol costs separately in total ledger",
        "cost_excludes": "unperformed independent production audit, unknown billing and negotiated discounts",
        "deepseek_1017": "isolated comparison only; excluded from factory roles"})
    contracts = []
    for role, selected in choices.items():
        if not selected or role == "INDEPENDENT_AUDITOR_CANDIDATE_NOT_QUALIFIED":
            continue
        row = selected[0]
        config = row["parameter_binding"]
        parameters = dict(config["parameters"])
        for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            if key in parameters:
                parameters[key] = 16384
        entry = next(item for item in catalog if (item.get("model_id") or item.get("id")) == config["model"])
        contract = AuxiliaryContract(ModelProfile("aihubmix", config["model"], {"endpoint_family": config["protocol"]}, {}),
            parameters, entry, str(out / "SCORECARD_ALL_MODELS.json"), ("AUX_PROTOCOL_PROBE", "GENERATOR", "CALIBRATOR"))
        contracts.append({"recommended_role": role, "config_id": config["id"], "contract": asdict(contract)})
    atomic_json(out / "AUXILIARY_ROUTING_PROFILE.json", {"version": "ioabench.v5.engineering-routing-profile/1",
        "base_url": "https://api.inferera.com/v1", "contracts": contracts, "catalog": catalog,
        "activation": "ENGINEERING_OPT_IN_ONLY_GOLD_QUALIFICATION_STILL_REQUIRED", "auditor_contracts": [],
        "formal_SUT_changed": False, "status": "BLOCKED_AUTH_PERMISSION" if (out / "STOP.json").exists() else "PROVISIONAL_ENGINEERING_ONLY",
        "source_sha256": source_tree_hash(ROOT),
        "evidence_sha256": {"SCORECARD_ALL_MODELS.json": sha(out / "SCORECARD_ALL_MODELS.json"),
                            "MODEL_CATALOG.json": sha(out / "MODEL_CATALOG.json"),
                            "BENCHMARK_TASKSET_FROZEN.json": sha(plan_path)} if plan_path.exists() else {}})
    profile = read(out / "AUXILIARY_ROUTING_PROFILE.json")
    selected_ids = {item["config_id"] for item in contracts}
    for folder in ("protocols", "quality"):
        for cid in selected_ids:
            for path in (out / folder / cid).rglob("*"):
                if path.is_file() and not path.name.endswith(".lock"):
                    profile["evidence_sha256"][path.relative_to(out).as_posix()] = sha(path)
    atomic_json(out / "AUXILIARY_ROUTING_PROFILE.json", profile)
    previous = ""
    with (out / "REQUEST_LEDGER.jsonl").open("w", encoding="utf-8") as stream:
        for record in records:
            row = {"previous_sha256": previous, "attempt": record}
            from ioabench.hashing import canonical_sha256
            row["sha256"] = canonical_sha256(row)
            previous = row["sha256"]
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    totals = {"at_utc": datetime.now(timezone.utc).isoformat(), "attempts": len(records),
        "statuses": dict(Counter(row["status"] for row in records)), "failure_categories": dict(Counter(
            response_category(row) for row in records if row["status"] != "SUCCEEDED")), "cost": cost(records),
        "usage_reported": dict(Counter({key: sum(row.get("usage", {}).get(key, 0) for row in records)
                                        for key in ("prompt_tokens", "completion_tokens", "total_tokens")})),
        "historical_unresolved_resends": 0, "historical_unresolved": 4,
        "machine_qualified_cost": "NOT_COMPUTABLE", "Gold_PI": "HUMAN_REQUIRED",
        "denominators": {"R_planned": len(rows)*8, "R_pass": sum(r["R_pass"] for r in rows),
            "R_fail": sum(r["R_fail"] for r in rows), "R_NOT_RUN": sum(r["R_NOT_RUN"] for r in rows),
            "Q_planned": len(rows)*8, "Q_started": sum(r["Q_completed"] for r in rows),
            "Q_pass": sum(r["Q_pass"] for r in rows), "Q_results_FAIL_or_interrupted": sum(r["Q_fail"] for r in rows),
            "Q_NOT_RUN": sum(r["Q_NOT_RUN"] for r in rows)},
        "quality_interpretation": "A result interrupted by global STOP is not a model-quality failure; inspect raw RESULT and REQUEST_RESULTS diagnostic_category."}
    atomic_json(out / "USAGE_AND_COST.json", totals)
    lines = ["# 模型比较与角色推荐", "", "固定任务、配置和分母见 BENCHMARK_TASKSET_FROZEN.json。工程排序不替代科研Gate。", "",
             "|配置|工程非重复pair/6|任务/8|R/8|每pair估算USD|工程加权分|", "|---|---:|---:|---:|---:|---:|"]
    lines += [f"|{row['config_id']}|{row['engineering_nonduplicate_valid_pairs']}|{row['Q_pass']}|{row['R_pass']}|{row['engineering_cost_per_pair_usd']:.6f}|{row['weighted_engineering_score']:.4f}|" for row in ranked]
    lines += ["", "角色推荐：", "", *[f"- {role}: {value or 'NOT_ESTABLISHED'}" for role, value in selection.items()], "",
        "成本以真实usage及网关目录价格估算，非账单；启动协议费用单列总账，未执行独审成本不记0。机器合格成本NOT_COMPUTABLE。",
        "短窗口两个不重叠批次不能证明长期可靠；Wilson区间和全部失败/未执行数见完整scorecard。",
        "DeepSeek 1017仅隔离工程比较；不改变正式SUT，不纳入数据工厂角色选择。独审候选未取得资格。"]
    (out / "PARETO_AND_ROLE_RECOMMENDATIONS.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.out), ensure_ascii=False))


if __name__ == "__main__":
    main()
