"""Stage-1 protocol probes for the AIHubMix deepseek-v4.1-flash path (PI-V5-006a).

Minimal live verification, sequential, ~3-5 calls total:
  A  single turn without tools            -> thinking presence, served identity, response structure
  B1 tool turn                            -> tool_calls + reasoning_content shape
  B2 follow-up WITHOUT reasoning replay   -> replicates the current v5 engine byte-behavior
  C  follow-up WITH full reasoning replay -> gateway acceptance test (direct API requires it)

Evidence: artifacts/v5/probes/protocol-probe-<date>.json. Not part of any benchmark protocol.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.models import AIHubMixAdapter, ModelRequest  # noqa: E402

REQUESTED = "deepseek-v4.1-flash"
# Probe budget == the confirmation-protocol output ceiling: rerunning this probe doubles as the
# live acceptance test that AIHubMix accepts the parameter for this model (PI decision 2026-10-11:
# unified max_tokens=131072 across all 18 suites; ceiling only — the model is never expected to
# exhaust it, and thinking mode, constructs and scoring are unchanged).
PARAMETERS = {"temperature": 0.0, "max_tokens": 131072}
TOOL = {"type": "function", "function": {
    "name": "get_unit_price",
    "description": "Return the list price of one catalog unit.",
    "parameters": {"type": "object", "additionalProperties": False,
                   "properties": {"sku": {"type": "string"}}, "required": ["sku"]}}}


def digest(resp: Any) -> dict[str, Any]:
    return {"requested_model": resp.model_id, "served_model": resp.provider_metadata.get("model"),
            "endpoint_family": resp.provider_metadata.get("endpoint_family"),
            "response_id": resp.provider_metadata.get("id"),
            "finish_reason": resp.finish_reason, "usage": dict(resp.usage),
            "text": (resp.text or "")[:300], "text_len": len(resp.text or ""),
            "reasoning_present": resp.reasoning_content is not None,
            "reasoning_len": len(resp.reasoning_content or ""),
            "reasoning_head": (resp.reasoning_content or "")[:200],
            "tool_call_names": [c.get("function", {}).get("name") for c in resp.tool_calls],
            "tool_call_ids": [c.get("id") for c in resp.tool_calls],
            "metadata_keys": sorted(resp.provider_metadata)}


async def main() -> None:
    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    profile = await adapter.resolve(REQUESTED)
    report: dict[str, Any] = {"probe_version": "protocol-probe-1.0.0", "requested": REQUESTED,
                              "requested_at_utc": datetime.now(timezone.utc).isoformat(),
                              "profile_capabilities": dict(profile.capabilities), "probes": {}}

    t0 = time.time()
    resp_a = await adapter.generate(profile, ModelRequest(
        messages=({"role": "user", "content": "Reply with exactly: PROBE-OK"},), parameters=dict(PARAMETERS)))
    report["probes"]["A_single_turn_no_tools"] = {"seconds": round(time.time() - t0, 1), **digest(resp_a)}

    msgs1 = ({"role": "system", "content": "You are a pricing desk assistant. Use the provided tool whenever it can answer the question."},
             {"role": "user", "content": "What is the list price for sku IOA-001? Use the get_unit_price tool."})
    t0 = time.time()
    resp_b1 = await adapter.generate(profile, ModelRequest(messages=msgs1, parameters=dict(PARAMETERS), tools=(TOOL,)))
    report["probes"]["B1_tool_turn"] = {"seconds": round(time.time() - t0, 1), **digest(resp_b1)}

    if not resp_b1.tool_calls:
        report["probes"]["B2_no_replay_turn"] = {"outcome": "SKIPPED — turn 1 produced no tool_calls"}
        report["probes"]["C_replay_turn"] = {"outcome": "SKIPPED — turn 1 produced no tool_calls"}
    else:
        call = resp_b1.tool_calls[0]
        tool_result = {"role": "tool", "tool_call_id": str(call.get("id")),
                       "content": json.dumps({"sku": "IOA-001", "unit_price": 42.5, "status": "ok"}, sort_keys=True)}
        follow_up = ({"role": "user", "content": "Now summarize the price for the order desk."},)
        base_assistant = {"role": "assistant", "content": resp_b1.text or "", "tool_calls": [dict(call)]}

        t0 = time.time()
        try:
            resp_b2 = await adapter.generate(profile, ModelRequest(
                messages=msgs1 + (base_assistant, tool_result) + follow_up,
                parameters=dict(PARAMETERS), tools=(TOOL,)))
            report["probes"]["B2_no_replay_turn"] = {"seconds": round(time.time() - t0, 1), "outcome": "HTTP_200",
                                                     **digest(resp_b2)}
        except Exception as exc:  # typed provider errors included; probe must record, not crash
            report["probes"]["B2_no_replay_turn"] = {"seconds": round(time.time() - t0, 1),
                                                     "outcome": f"{type(exc).__name__}: {exc}"}
        if resp_b1.reasoning_content:
            replayed = dict(base_assistant)
            replayed["reasoning_content"] = resp_b1.reasoning_content
            t0 = time.time()
            try:
                resp_c = await adapter.generate(profile, ModelRequest(
                    messages=msgs1 + (replayed, tool_result) + follow_up,
                    parameters=dict(PARAMETERS), tools=(TOOL,)))
                report["probes"]["C_replay_turn"] = {"seconds": round(time.time() - t0, 1), "outcome": "HTTP_200",
                                                     **digest(resp_c)}
            except Exception as exc:
                report["probes"]["C_replay_turn"] = {"seconds": round(time.time() - t0, 1),
                                                     "outcome": f"{type(exc).__name__}: {exc}"}
        else:
            report["probes"]["C_replay_turn"] = {"outcome": "SKIPPED — turn 1 produced no reasoning_content"}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "artifacts" / "v5" / "probes" / f"protocol-probe-{stamp}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, probe in report["probes"].items():
        summary = {k: probe.get(k) for k in ("outcome", "served_model", "finish_reason", "reasoning_present",
                                             "reasoning_len", "tool_call_names", "seconds") if k in probe}
        print(name, json.dumps(summary, ensure_ascii=False))
    print("evidence:", out)


if __name__ == "__main__":
    asyncio.run(main())
