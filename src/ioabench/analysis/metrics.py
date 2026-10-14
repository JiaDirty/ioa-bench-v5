"""Safety and utility summaries for completed benchmark runs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def _wilson_interval(successes: float, denominator: int) -> list[float] | None:
    if denominator <= 0:
        return None
    proportion = successes / denominator
    z = 1.96
    denominator_term = 1.0 + z * z / denominator
    centre = proportion + z * z / (2.0 * denominator)
    margin = z * ((proportion * (1.0 - proportion) / denominator + z * z / (4.0 * denominator * denominator)) ** 0.5)
    return [max(0.0, (centre - margin) / denominator_term), min(1.0, (centre + margin) / denominator_term)]


def _summarize_records(records: list[dict[str, Any]], *, simulation_only: bool = False, pricing: dict[str, Any] | None = None) -> dict[str, Any]:
    valid = [record for record in records if record.get("eligibility") == "VALID"]
    metric_values: dict[str, list[float]] = defaultdict(list)
    utilities: list[float] = []
    efficiency_values: dict[str, list[float]] = defaultdict(list)
    cost_values: list[float] = []
    utility_sources: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    for record in valid:
        score = record.get("score", {})
        for key, value in score.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metric_values[key].append(float(value))
        replay_utility = record.get("_replay_utility", {})
        task_success = score.get("task_success", replay_utility.get("task_success"))
        source = "score" if "task_success" in score else "replay.final_utility"
        if isinstance(task_success, bool):
            utilities.append(float(task_success))
            utility_sources[source] = utility_sources.get(source, 0) + 1
        elif isinstance(task_success, (int, float)):
            utilities.append(float(task_success))
            utility_sources[source] = utility_sources.get(source, 0) + 1
        for key in ("model_calls", "tool_calls", "prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
            value = record.get(f"_{key}", replay_utility.get(key))
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                efficiency_values[key].append(float(value))
        estimated_cost = record.get("_estimated_cost_usd")
        if isinstance(estimated_cost, (int, float)) and not isinstance(estimated_cost, bool):
            cost_values.append(float(estimated_cost))
        outcome = str(score.get("outcome_class", "UNKNOWN"))
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    safety_metrics = {key: mean(values) for key, values in sorted(metric_values.items()) if key != "task_success"}
    metric_uncertainty = {
        key: {"denominator": len(values), "mean": mean(values), "stddev": pstdev(values) if len(values) > 1 else 0.0}
        for key, values in sorted(metric_values.items()) if key != "task_success"
    }
    return {
        "case_count": len(records),
        "valid_count": len(valid),
        "invalid_count": len(records) - len(valid),
        "safety_metrics": safety_metrics,
        "composite_metrics": {},
        "task_utility": {"task_success": mean(utilities) if utilities else None, "denominator": len(utilities), "source_counts": utility_sources},
        "efficiency": {key: {"mean": mean(values), "denominator": len(values)} for key, values in sorted(efficiency_values.items())},
        "cost": {"status": "ESTIMATED_FROM_LIVE_CATALOG" if cost_values else "NOT_RECORDED", "usd": sum(cost_values) if cost_values else None, "mean_per_case_usd": mean(cost_values) if cost_values else None, "denominator": len(cost_values), "pricing": pricing},
        "uncertainty": {
            "task_success_wilson_95": _wilson_interval(sum(utilities), len(utilities)) if utilities else None,
            "safety_metrics": metric_uncertainty,
        },
        "outcomes": outcomes,
        "validity": "SIMULATION_ONLY" if simulation_only else "VALID",
    }


def analyze_run(root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(root)
    run_root = root / "data" / "runs" / run_id
    results = json.loads((run_root / "results.json").read_text(encoding="utf-8"))
    manifest_path = run_root / "manifest" / f"{run_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    model_id = manifest.get("tested_model", {}).get("model_id") or run_id.removesuffix("-v1")
    pricing_path = root / "artifacts" / "runs" / model_id / "model-resolution.json"
    pricing_document = json.loads(pricing_path.read_text(encoding="utf-8")) if pricing_path.is_file() else {}
    pricing = pricing_document.get("pricing") if isinstance(pricing_document.get("pricing"), dict) else None
    for record in results.values():
        replay_path = run_root / str(record.get("replay", ""))
        if not replay_path.is_file():
            continue
        try:
            replay = json.loads(replay_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        utility = replay.get("final_utility", {})
        if isinstance(utility, dict):
            record["_replay_utility"] = utility
        model_records = replay.get("model_records", [])
        if isinstance(model_records, list):
            usage_keys = {"prompt_tokens": "prompt_tokens", "completion_tokens": "completion_tokens", "total_tokens": "total_tokens"}
            for output_key, usage_key in usage_keys.items():
                values = [float(item.get("usage", {}).get(usage_key, 0) or 0) for item in model_records if isinstance(item, dict)]
                record[f"_{output_key}"] = sum(values)
            cache_read = sum(float(item.get("usage", {}).get("prompt_tokens_details", {}).get("cached_tokens", 0) or 0) for item in model_records if isinstance(item, dict))
            record["_cache_read_tokens"] = cache_read
            if pricing and all(isinstance(pricing.get(key), (int, float)) for key in ("input", "output", "cache_read")):
                input_tokens = record.get("_prompt_tokens", 0.0)
                output_tokens = record.get("_completion_tokens", 0.0)
                record["_estimated_cost_usd"] = ((input_tokens - cache_read) * float(pricing["input"]) + cache_read * float(pricing["cache_read"]) + output_tokens * float(pricing["output"])) / 1_000_000
            record["_model_calls"] = float(len(model_records))
        timeline = replay.get("timeline", [])
        if isinstance(timeline, list):
            inputs = [item for item in timeline if isinstance(item, dict) and item.get("event_type") == "model.input"]
            outputs = [item for item in timeline if isinstance(item, dict) and item.get("event_type") == "model.output"]
            latencies = []
            for input_event, output_event in zip(inputs, outputs):
                try:
                    start = datetime.fromisoformat(str(input_event["event_time"]))
                    end = datetime.fromisoformat(str(output_event["event_time"]))
                    latencies.append(max(0.0, (end - start).total_seconds() * 1000.0))
                except (KeyError, TypeError, ValueError):
                    continue
            if latencies:
                record["_latency_ms"] = mean(latencies)
    suites: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in results.values():
        suites[str(record.get("suite"))].append(record)
    summary: dict[str, Any] = {"run_id": run_id, "status_counts": {}, "suites": {}}
    for record in results.values():
        status = str(record.get("eligibility", record.get("status", "UNKNOWN")))
        summary["status_counts"][status] = summary["status_counts"].get(status, 0) + 1
    for suite, records in sorted(suites.items()):
        simulation_only = suite in {"T361", "T362", "T363"}
        suite_summary = _summarize_records(records, simulation_only=simulation_only, pricing=pricing)
        suite_summary["breakdowns"] = {}
        for dimension in ("difficulty", "world_id", "mechanism_id"):
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for record in records:
                grouped[str(record.get(dimension, "UNKNOWN"))].append(record)
            suite_summary["breakdowns"][dimension] = {
                value: _summarize_records(group, simulation_only=simulation_only, pricing=pricing)
                for value, group in sorted(grouped.items())
            }
        summary["suites"][suite] = suite_summary
    summary["pricing"] = pricing
    return summary


def write_metrics(summary: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "suite-metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["suite", "case_count", "valid_count", "invalid_count", "task_success", "validity"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for suite, value in summary["suites"].items():
            writer.writerow({"suite": suite, "case_count": value["case_count"], "valid_count": value["valid_count"], "invalid_count": value["invalid_count"], "task_success": value["task_utility"]["task_success"], "validity": value["validity"]})
    return path
