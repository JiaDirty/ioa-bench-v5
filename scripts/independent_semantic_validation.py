"""Independent (tested-model-free) semantic validation over frozen datasets (G2).

Runs the dual-model semantic validation over the authoritative frozen datasets
using two validators independent of the tested-model roster (glm-5.3-flash +
gemini-3.5-flash-lite per artifacts/gates/AUX_MODEL_PROFILES.json).  This is a
read-only quality-evidence pass: datasets are immutable, results land in
artifacts/gates/INDEPENDENT_SEMANTIC_VALIDATION.json and per-suite cache files
under data/datasets/<suite>/<version>/independent-semantic-validation*.json.

Usage: python scripts/independent_semantic_validation.py [--suites T311,T312,...] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.generation.ai_semantic import validate_candidates  # noqa: E402
from ioabench.models import AIHubMixAdapter  # noqa: E402

from ioabench.frozen_versions import FROZEN_VERSIONS  # single source of truth

# validators independent of the tested-model roster (see AUX_MODEL_PROFILES)
PRIMARY = "glm-5.3-flash"
SECONDARY = "gemini-3.5-flash-lite"


async def validate_suite(adapter: AIHubMixAdapter, suite: str) -> dict:
    version = FROZEN_VERSIONS[suite]
    dataset = ROOT / "data" / "datasets" / suite / version
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    verdicts = await validate_candidates(
        cases, adapter=adapter, primary_model=PRIMARY, secondary_model=SECONDARY,
        cache_path=str(dataset / "independent-semantic-validation-cache.json"))
    rejected = [item.candidate_id for item in verdicts if not item.accepted]
    result = {"suite": suite, "dataset_version": version, "validator_models": [PRIMARY, SECONDARY],
              "accepted_cases": sum(1 for item in verdicts if item.accepted),
              "total_cases": len(verdicts), "all_accepted": not rejected,
              "rejected_candidate_ids": rejected}
    (dataset / "independent-semantic-validation.json").write_text(
        json.dumps({"validator_models": [PRIMARY, SECONDARY],
                    "accepted_cases": result["accepted_cases"], "total_cases": result["total_cases"],
                    "all_accepted": result["all_accepted"],
                    "verdicts": [{"candidate_id": item.candidate_id, "accepted": item.accepted,
                                  "labels": [v.label for v in item.verdicts]} for item in verdicts]},
                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suites", default=",".join(FROZEN_VERSIONS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    report = {"artifact": "INDEPENDENT_SEMANTIC_VALIDATION",
              "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "purpose": "tested-model-free dual semantic validation over authoritative frozen datasets (goal item 11)",
              "suites": []}
    out = ROOT / "artifacts" / "gates" / "INDEPENDENT_SEMANTIC_VALIDATION.json"
    for suite in args.suites.split(","):
        if args.dry_run:
            print(f"[dry-run] {suite}@{FROZEN_VERSIONS[suite]}: would validate 90 cases with {PRIMARY} + {SECONDARY}")
            continue
        result = await validate_suite(adapter, suite.strip())
        report["suites"].append(result)
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{suite}@{result['dataset_version']}: {result['accepted_cases']}/{result['total_cases']} accepted"
              + (f" REJECTED={result['rejected_candidate_ids'][:5]}" if result["rejected_candidate_ids"] else ""))
    if not args.dry_run:
        report["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        report["all_accepted_18"] = len(report["suites"]) == 18 and all(s["all_accepted"] for s in report["suites"])
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"report: {out} (all_accepted_18={report.get('all_accepted_18')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
