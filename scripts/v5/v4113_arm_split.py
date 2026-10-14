"""Diagnostic: split v4.1.13 formal outcomes by experimental arm (CONTROL/RISK).

Read-only over historical runs/datasets; writes artifacts/v5/architecture/v4113_arm_split.json.
Used by ADR-V5-000 section 1 as evidence that most v4 suites lack a demonstrated manipulation.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.frozen_versions import FROZEN_VERSIONS  # noqa: E402

UNSAFE = {"UNSAFE_ACTION", "FULL_FAILURE", "LATE_RECOVERY"}


def main() -> None:
    condition = {}
    for suite, version in FROZEN_VERSIONS.items():
        for line in (ROOT / "data" / "datasets" / suite / version / "cases.jsonl").open(encoding="utf-8"):
            case = json.loads(line)
            condition[case["candidate_id"]] = case["provenance"]["condition"]
    out = {"source": "v4.1.13 formal runs (read-only)", "unsafe_classes": sorted(UNSAFE), "suites": {}}
    for suite, version in FROZEN_VERSIONS.items():
        run = ROOT / "data" / "runs" / f"deepseek-v4.1-flash-{suite}-{version}-v4.1.13-formal" / "results.json"
        results = json.loads(run.read_text(encoding="utf-8"))
        arms: dict[str, dict] = {}
        for result in results.values():
            arm = condition[result["case_id"]]
            score = result.get("score") or {}
            outcome = score.get("outcome_class", result.get("status"))
            entry = arms.setdefault(arm, {"n": 0, "utility": 0, "unsafe": 0, "outcomes": collections.Counter()})
            entry["n"] += 1
            entry["utility"] += bool(score.get("task_utility"))
            entry["unsafe"] += outcome in UNSAFE
            entry["outcomes"][outcome] += 1
        out["suites"][suite] = {arm: {"n": v["n"], "utility_rate": round(v["utility"] / v["n"], 4),
                                      "unsafe_rate": round(v["unsafe"] / v["n"], 4),
                                      "outcomes": dict(v["outcomes"])} for arm, v in sorted(arms.items())}
        c, r = out["suites"][suite]["CONTROL"], out["suites"][suite]["RISK"]
        out["suites"][suite]["risk_minus_control_unsafe"] = round(r["unsafe_rate"] - c["unsafe_rate"], 4)
    target = ROOT / "artifacts" / "v5" / "architecture" / "v4113_arm_split.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for suite, row in out["suites"].items():
        print(suite, row["CONTROL"]["utility_rate"], row["CONTROL"]["unsafe_rate"], row["RISK"]["unsafe_rate"],
              row["risk_minus_control_unsafe"])


if __name__ == "__main__":
    main()
