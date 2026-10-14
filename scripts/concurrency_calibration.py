"""Provider concurrency calibration probe (G6 evidence).

Measures, per candidate concurrency level, the realistic provider behavior of
the campaign workload against AIHubMix: success rate, 429/5xx counts, timeout
counts, average/P95 latency and throughput.  The winning level per role is
recorded into the frozen scheduler profile.

Usage: python scripts/concurrency_calibration.py [--levels 2,3,4] [--calls 12]
                                                    [--model deepseek-v4.1-flash]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.models import AIHubMixAdapter, ModelRequest  # noqa: E402

# A representative formal-case-sized prompt: structured multi-field context and
# a bounded JSON decision, similar in shape to tested-agent turns.
PROMPT = (
    {"role": "system",
     "content": "You coordinate a synthetic local business task. Decide strictly from the given evidence. Reply with JSON only."},
    {"role": "user",
     "content": json.dumps({
         "task": {"action": "subscription.renewal.process", "resource": "case-0001-lane-01"},
         "records": [{"agent": f"agent-{n}", "completed": 12 + n, "quality": 0.7 + n * 0.01,
                      "verified": n % 2 == 0} for n in range(8)],
         "return_format": {"selected": "string agent id", "confidence": "number 0-1",
                            "reason": "string, max 25 words"}}, ensure_ascii=False)},
)

PARAMETERS = {"temperature": 0.0, "max_tokens": 8192}


async def _timed_call(adapter, profile, semaphore):
    async with semaphore:
        started = time.perf_counter()
        try:
            await adapter.generate(profile, ModelRequest(messages=PROMPT, parameters=PARAMETERS,
                                                         role_metadata={"role": "CONCURRENCY_PROBE"}))
            return {"ok": True, "latency": time.perf_counter() - started}
        except Exception as exc:  # noqa: BLE001 - failure classes are the measured signal
            text = str(exc)
            return {"ok": False, "latency": time.perf_counter() - started,
                    "error_class": type(exc).__name__,
                    "http_429": "429" in text, "http_5xx": any(f"HTTP {c}" in text for c in range(500, 600)),
                    "timeout": "timeout" in text.lower() or "Timeout" in type(exc).__name__}


async def calibrate(adapter, profile, level: int, calls: int) -> dict:
    semaphore = asyncio.Semaphore(level)
    started = time.perf_counter()
    results = await asyncio.gather(*[_timed_call(adapter, profile, semaphore) for _ in range(calls)])
    wall = time.perf_counter() - started
    oks = [r for r in results if r["ok"]]
    latencies = [r["latency"] for r in oks]
    return {
        "concurrency": level, "calls": calls,
        "success_rate": round(len(oks) / calls, 3),
        "http_429": sum(1 for r in results if r.get("http_429")),
        "http_5xx": sum(1 for r in results if r.get("http_5xx")),
        "timeouts": sum(1 for r in results if r.get("timeout")),
        "other_errors": sum(1 for r in results if not r["ok"] and not (r.get("http_429") or r.get("http_5xx") or r.get("timeout"))),
        "latency_avg_s": round(statistics.mean(latencies), 2) if latencies else None,
        "latency_p95_s": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 2) if latencies else None,
        "throughput_calls_per_min": round(calls / wall * 60, 1),
        "wall_s": round(wall, 1),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", default="2,3,4")
    parser.add_argument("--calls", type=int, default=12)
    parser.add_argument("--model", default="deepseek-v4.1-flash")
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "gates" / "CONCURRENCY_CALIBRATION.json"))
    args = parser.parse_args()

    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    profile = await adapter.resolve(args.model)
    report = {"artifact": "CONCURRENCY_CALIBRATION", "probed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model_id": args.model, "calls_per_level": args.calls, "levels": []}
    for level in (int(x) for x in args.levels.split(",")):
        row = await calibrate(adapter, profile, level, args.calls)
        report["levels"].append(row)
        print(f"level {level}: ok={row['success_rate']} 429={row['http_429']} 5xx={row['http_5xx']} "
              f"timeout={row['timeouts']} avg={row['latency_avg_s']}s p95={row['latency_p95_s']}s "
              f"throughput={row['throughput_calls_per_min']}/min")
        Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
