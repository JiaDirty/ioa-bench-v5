"""Design probe: run a few generated v5 pairs of one suite against a live model (DESIGN_PROBE only).

Probes test whether a suite design works with real models before data scale-up. They are not pilot
or formal evidence and are written to artifacts/v5/probes/<probe_id>/.

Usage: python scripts/v5/probe.py --suite T351 --model deepseek-v4.1-flash --pairs 4 --seed 101
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.models import AIHubMixAdapter  # noqa: E402
from ioabench.v5.runner import append_result, run_case  # noqa: E402
from ioabench.v5.suites import load  # noqa: E402

PARAMETERS = {"temperature": 0.0, "max_tokens": 4096}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--pairs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--families", type=int, default=30)
    parser.add_argument("--difficulty", default="E,M,H", help="comma-separated strata to sample round-robin")
    args = parser.parse_args()
    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    profile = await adapter.resolve(args.model)
    module = load(args.suite)
    pairs = module.generate(seed=args.seed, families=args.families)
    wanted = [d for d in args.difficulty.split(",") if d]
    by_stratum = {d: [p for p in pairs if p[0].difficulty == d] for d in wanted}
    chosen = []
    for index in range(args.pairs):
        stratum = by_stratum[wanted[index % len(wanted)]]
        position = (index // len(wanted)) * max(1, len(stratum) // max(1, args.pairs // len(wanted)))
        chosen.append(stratum[position % len(stratum)])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    probe_id = f"{args.suite}-{args.model}-{stamp}"
    run_id = f"v5-probe-{probe_id}"
    out = ROOT / "artifacts" / "v5" / "probes" / probe_id / "results.jsonl"
    summary: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for control, risk in chosen:
        for case in (control, risk):
            result = await run_case(ROOT, case, adapter, profile, run_id=run_id, parameters=PARAMETERS)
            result["evidence_class"] = "DESIGN_PROBE"
            append_result(out, result)
            outcome = result["outcome"]
            summary[case.arm][outcome["legacy_class"]] += 1
            print(case.case_id, case.difficulty, result["status"], outcome["legacy_class"],
                  f"calls={result.get('model_calls')} malformed={result.get('malformed_calls')}",
                  (result.get("score") or {}).get("rationale", result.get("error")))
    (out.parent / "summary.json").write_text(json.dumps({"probe_id": probe_id, "suite": args.suite, "model": args.model,
                                                         "seed": args.seed, "pairs": len(chosen), "evidence_class": "DESIGN_PROBE",
                                                         "by_arm": {k: dict(v) for k, v in summary.items()}}, indent=2),
                                             encoding="utf-8")
    print(json.dumps({k: dict(v) for k, v in summary.items()}))


if __name__ == "__main__":
    asyncio.run(main())
