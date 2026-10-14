"""Generate a small offline T311 construct trial; never calls a provider."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from ioabench.models import ModelProfile
from ioabench.runtime.t311_baselines import T311Baseline
from ioabench.runtime.t311_construct import execute_t311, freeze_t311_offline_result
from ioabench.runtime.t311_fixture import build_t311_case_from_skeleton
from ioabench.suites.t311.generation import T311Generator


def run_trial(root: Path, output: Path, count: int = 6) -> dict:
    if count < 1:
        raise ValueError("count must be positive")
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    profile = ModelProfile("mock", "t311-construct-trial", {"tools": True}, {})
    results = []
    cases = []
    generator = T311Generator()
    for index in range(1, count + 1):
        skeleton = generator.generate(mechanism_index=(index - 1) % 5,
                                      difficulty=("easy", "medium", "hard")[(index - 1) % 3],
                                      seed=index, condition="RISK")
        case = build_t311_case_from_skeleton(asdict(skeleton))
        case["case_id"] = f"T311-trial-{index:03d}"
        case["task"]["resource"] = f"resource-{case['case_id']}"
        case["oracle_payload"]["allowed_resource"] = case["task"]["resource"]
        cases.append(case)
        for policy in ("safe", "naive", "alternative", "recovery"):
            result = asyncio.run(execute_t311(root, case, T311Baseline(policy), profile, run_id=f"T311-trial-{index:03d}-{policy}"))
            replay = freeze_t311_offline_result(result, output / "replays" / f"{index:03d}-{policy}", case)
            results.append({"case_id": case["case_id"], "policy": policy, "outcome": result["score"]["outcome_class"], "task_utility": result["score"]["task_utility"], "replay": str(replay.relative_to(output))})
    summary = {"trial_id": "T311-construct-trial-2.0.0", "provider_calls": 0, "formal_dataset": False, "generator": "T311Generator", "runtime": "T311-construct-1.0.0", "case_count": count, "baseline_runs": len(results), "results": results}
    (output / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    print(json.dumps(run_trial(Path(__file__).resolve().parents[1], args.output, args.count), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
