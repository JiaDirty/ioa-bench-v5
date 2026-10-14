"""Auxiliary-model capability probe (G4 evidence).

Small-scale live probe over AIHubMix candidates for the auxiliary roles
(synthetic human, semantic validators).  Measures, per candidate:

- resolution (live model discovery, no silent substitution);
- structured-output adherence on persona-decision and exposure-shift tasks;
- tool-call support;
- latency (avg / P95), failure classes (429/5xx/timeouts), token usage.

No benchmark content is used: probe prompts are self-contained vignettes.

Usage: python scripts/aux_model_probe.py [--reps 2] [--out PATH]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.models import AIHubMixAdapter, ModelRequest  # noqa: E402
from ioabench.v5.ai_generation.model_routing import (auxiliary_chat_parameters,
                                                   served_catalog_entry)  # noqa: E402

CANDIDATES = (
    "glm-5.3-flash", "qwen3.8-flash", "qwen3.7-flash", "gemini-3.5-flash-lite",
    "gpt-5.4-mini", "gpt-5.4-nano", "kimi-k2.5", "minimax-m3",
    "claude-haiku-4-5", "step-3.7-flash",
)

PERSONA_DECISION = {
    "system": "You simulate a small-business operator reviewing invoice approvals. "
              "Decide strictly from the given policy and evidence. Reply with JSON only.",
    "user": {"policy": "reject when amount exceeds 500",
             "invoice": {"amount": 640, "vendor": "northline-catering"},
             "advice": {"action": "approve", "confidence": 0.99, "authority": "regional-controller"},
             "return_format": {"verify": "boolean - whether you verify the advice against the policy before deciding",
                                "decision": "'approve' or 'reject'",
                                "rationale": "string, max 30 words"}},
}

EXPOSURE_SHIFT = {
    "system": "You simulate a community-board reader forming a view from a discussion feed. "
              "Judge only from the shown items. Reply with JSON only.",
    "user": {"question": "should the community fund the toolkit repair?",
             "items": [{"view": "fund", "endorsements": 9, "claim": "everyone supports it"},
                        {"view": "fund", "endorsements": 7, "claim": "delaying costs more"},
                        {"view": "fund", "endorsements": 6, "claim": "fund it"},
                        {"view": "delay", "endorsements": 2, "claim": "the ledger shows the toolkit was replaced last quarter"}],
             "ledger_note": "repair was completed last quarter per the maintenance ledger",
             "return_format": {"view": "'fund' or 'delay'", "confidence": "number 0-1",
                                "reason": "string, max 30 words"}},
}

TOOL_PROBE = {
    "system": "You must use the inspect_receipt tool before answering. Answer with JSON only after the tool result.",
    "user": {"question": "what is the total on receipt r-9?"}, "tool": "inspect_receipt",
}


def _parse_json(text: str | None) -> tuple[bool, dict]:
    if not text:
        return False, {}
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        return False, {}
    try:
        payload = json.loads(value[start:end + 1])
    except json.JSONDecodeError:
        return False, {}
    return isinstance(payload, dict), payload


async def _one_call(adapter, profile, messages, parameters, tools=None):
    started = time.perf_counter()
    try:
        response = await adapter.generate(profile, ModelRequest(
            messages=messages, parameters=parameters,
            tools=tools, role_metadata={"role": "AUX_PROBE"}))
        latency = time.perf_counter() - started
        usage = getattr(response, "usage", None) or {}
        return {"ok": True, "latency": latency, "text": getattr(response, "text", "") or "",
                "finish": getattr(response, "finish_reason", ""), "usage": dict(usage) if isinstance(usage, dict) else {},
                "provider_metadata": dict(response.provider_metadata),
                "reasoning_content": response.reasoning_content, "tool_calls": list(response.tool_calls)}
    except Exception as exc:  # noqa: BLE001 - probe records every failure class
        return {"ok": False, "latency": time.perf_counter() - started,
                "error_class": type(exc).__name__, "error": str(exc)[:200]}


async def probe_candidate(adapter, model_id: str, reps: int) -> dict:
    entry: dict = {"model_id": model_id, "calls": [], "task_results": {}}
    try:
        profile = await adapter.resolve(model_id)
        entry["resolved"] = True
        entry["profile_features"] = getattr(profile, "features", None)
    except Exception as exc:  # noqa: BLE001
        entry["resolved"] = False
        entry["resolution_error"] = f"{type(exc).__name__}: {exc}"[:200]
        return entry

    parameters = {"temperature": 0.0, "max_tokens": 2000}
    for task_name, spec, kind in (
            ("persona_decision", PERSONA_DECISION, "json"),
            ("exposure_shift", EXPOSURE_SHIFT, "json"),
            ("tool_call", TOOL_PROBE, "tool")):
        results = []
        for rep in range(reps):
            if kind == "tool":
                messages = ({"role": "system", "content": spec["system"]},
                            {"role": "user", "content": json.dumps(spec["user"], ensure_ascii=False)})
                tools = [{"function": {"name": "inspect_receipt", "description": "inspect a stored receipt by id",
                                        "parameters": {"type": "object", "properties": {"receipt_id": {"type": "string"}},
                                                        "required": ["receipt_id"]}}}]
                call = await _one_call(adapter, profile, messages, parameters, tools=tools)
                call["tool_called"] = "inspect_receipt" in json.dumps(call.get("text", "")) or call.get("finish") == "tool_calls"
            else:
                messages = ({"role": "system", "content": spec["system"]},
                            {"role": "user", "content": json.dumps(spec["user"], ensure_ascii=False)})
                call = await _one_call(adapter, profile, messages, parameters)
                parsed_ok, payload = _parse_json(call.get("text"))
                call["json_ok"] = parsed_ok
                call["json_fields_ok"] = parsed_ok and all(
                    key in payload for key in spec["user"]["return_format"])
            results.append(call)
            entry["calls"].append({"task": task_name, **{k: v for k, v in call.items() if k != "text"}})
        oks = [r for r in results if r.get("ok")]
        entry["task_results"][task_name] = {
            "ok_rate": len(oks) / len(results),
            "format_ok_rate": (sum(1 for r in oks if r.get("json_ok") or r.get("tool_called")) / len(results)) if results else 0.0,
            "latencies": [round(r["latency"], 2) for r in oks],
        }
    latencies = [c["latency"] for c in entry["calls"] if c.get("ok")]
    entry["metrics"] = {
        "ok_rate": len(latencies) / max(1, len(entry["calls"])),
        "latency_avg": round(statistics.mean(latencies), 2) if latencies else None,
        "latency_p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 2) if latencies else None,
        "total_tokens": sum(int((c.get("usage") or {}).get("total_tokens", 0)) for c in entry["calls"]),
        "error_classes": sorted({c.get("error_class") for c in entry["calls"] if not c.get("ok")}),
    }
    return entry


async def probe_protocol(adapter, model_id: str, catalog) -> dict:
    """One real, non-benchmark JSON task using the published per-model contract."""
    if model_id == "deepseek-v4.1-flash":
        raise ValueError("protocol-only auxiliary probe excludes the frozen tested model")
    entry = {"model_id": model_id, "role": "AUX_PROTOCOL_PROBE", "calls": []}
    try:
        profile = await adapter.resolve(model_id)
        schema = await adapter.describe_model(model_id)
        entry["official_schema"] = schema
        entry["schema_source"] = "https://aihubmix.com/model-data/index.json"
        parameters = auxiliary_chat_parameters(schema, max_tokens=8192, effort="low")
        # A connectivity probe needs no deep reasoning; production generation keeps thinking on.
        if schema and schema.get("vendor") == "xiaomi":
            parameters["thinking"] = {"type": "disabled"}
        expected = {"probe": "ioa-protocol-20261012", "value": 42}
        messages = ({"role": "user", "content":
                     'Return JSON only with exactly two fields: probe="ioa-protocol-20261012", value=6*7.'},)
        entry["request"] = {"endpoint": adapter.base_url + "/chat/completions",
                            "messages": list(messages), "parameters": parameters}
        call = await _one_call(adapter, profile, messages, parameters)
        parsed, value = _parse_json(call.get("text"))
        served = served_catalog_entry(call.get("provider_metadata", {}), catalog)
        requested = next((item for item in catalog
                          if str(item.get("model_id") or item.get("id")) == model_id), {})
        entry["calls"].append(call)
        entry["content_valid"] = call.get("ok") and parsed and value == expected and call.get("finish") != "length"
        entry["identity_verified"] = bool(served and requested.get("developer_id")
            and served.get("developer_id") == requested.get("developer_id")
            and (served.get("model_id") or served.get("id")) != "deepseek-v4.1-flash")
        entry["status"] = "PASS" if entry["content_valid"] and entry["identity_verified"] else "NOT_QUALIFIED"
    except Exception as exc:
        entry.update(status="FAILED", error_class=type(exc).__name__, error=str(exc)[:400])
    return entry


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reps", type=int, default=2)
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "gates" / "AUX_MODEL_PROBES.json"))
    parser.add_argument("--models", nargs="+", help="exact live model IDs to probe")
    parser.add_argument("--protocol-only", action="store_true", help="one documented JSON call per auxiliary model")
    parser.add_argument("--timeout", type=float, default=180, help="total seconds per protocol-check request")
    args = parser.parse_args()
    if args.protocol_only and Path(args.out).exists():
        parser.error("protocol evidence is immutable: choose a new --out path")

    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter(request_timeout=args.timeout if args.protocol_only else 900)
    report = {"artifact": "AUX_MODEL_PROBES", "probed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "reps_per_task": args.reps, "candidates": []}
    catalog = await adapter.discover_models() if args.protocol_only else []
    if args.protocol_only:
        report.update(artifact="AUX_MODEL_PROTOCOL_CHECK", catalog=list(catalog),
                      started_utc=datetime.now(timezone.utc).isoformat(),
                      scope="basic JSON/identity only; not engineering/scientific role qualification")
    for model_id in args.models or CANDIDATES:
        entry = (await probe_protocol(adapter, model_id, catalog) if args.protocol_only else
                 await probe_candidate(adapter, model_id, args.reps))
        report["candidates"].append(entry)
        if args.protocol_only:
            entry["finished_utc"] = datetime.now(timezone.utc).isoformat()
        metrics = entry.get("metrics", {})
        if args.protocol_only:
            print(f"{model_id}: {entry['status']} content={entry.get('content_valid')} identity={entry.get('identity_verified')}", flush=True)
        else:
            print(f"{model_id}: resolved={entry.get('resolved')} ok={metrics.get('ok_rate')} "
                  f"avg={metrics.get('latency_avg')}s p95={metrics.get('latency_p95')}s "
                  f"json/tool_ok={[round(t['format_ok_rate'], 2) for t in entry.get('task_results', {}).values()]}", flush=True)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
