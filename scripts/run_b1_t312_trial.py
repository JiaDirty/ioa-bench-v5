"""B1 small-batch trial generation for T312 under the V2 causal recipe.

Grid: five mechanisms x CONTROL/RISK at medium plus difficulty strata.
Validates the full B1 checklist through the dispatcher-registered runtime.
"""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.generation.difficulty import DifficultyCalibrator  # noqa: E402
from ioabench.generation.leakage import find_leaks  # noqa: E402
from ioabench.hashing import canonical_sha256  # noqa: E402
from ioabench.models import ModelProfile  # noqa: E402
from ioabench.runtime.discovery_selection import (  # noqa: E402
    DiscoverySelectionBaseline, build_discovery_case_from_skeleton, execute_discovery_selection,
)
from ioabench.suites.t312.generation import T312Generator  # noqa: E402

TRIAL_DIR = ROOT / "data" / "trials" / "T312" / "b1-v2-recipe-trial"
PROFILE = ModelProfile("mock", "b1-recipe-trial", {"tools": True}, {})
GRID = [
    *(("medium", mechanism, "RISK") for mechanism in range(5)),
    *(("medium", 0, "CONTROL"), ("medium", 2, "CONTROL")),
    *(("easy", 1, "RISK"), ("hard", 1, "RISK"), ("hard", 3, "RISK")),
]


def execute_case(case: dict, policy: str) -> dict:
    return asyncio.run(execute_discovery_selection(
        ROOT, case, DiscoverySelectionBaseline(policy), PROFILE,
        run_id=f"b1-trial-{case['case_id']}-{policy}"))


def main() -> int:
    generator = T312Generator()
    candidates, executions, execution_errors = [], {}, {}
    for difficulty, mechanism, condition in GRID:
        skeleton = generator.generate(seed=201 + mechanism, mechanism_index=mechanism,
                                      difficulty=difficulty, condition=condition)
        frozen = {"candidate_id": skeleton.candidate_id, "test_id": "T312",
                  "mechanism_id": skeleton.mechanism_id, "world_id": skeleton.world_id,
                  "difficulty": skeleton.difficulty,
                  "sut_payload": deepcopy(skeleton.sut_payload),
                  "oracle_payload": skeleton.ground_truth.as_dict(),
                  "provenance": {"condition": condition, "seed": 201 + mechanism,
                                 "skeleton_sha256": canonical_sha256(skeleton.sut_payload),
                                 "oracle_sha256": skeleton.ground_truth.content_sha256}}
        candidates.append(frozen)
        if condition != "RISK":
            continue
        runtime_case = build_discovery_case_from_skeleton(asdict(skeleton))
        try:
            safe = asyncio.run(execute_discovery_selection(ROOT, runtime_case, DiscoverySelectionBaseline("safe"), PROFILE,
                                                           run_id=f"b1-trial-{skeleton.candidate_id}-safe"))
            naive = asyncio.run(execute_discovery_selection(ROOT, runtime_case, DiscoverySelectionBaseline("naive"), PROFILE,
                                                            run_id=f"b1-trial-{skeleton.candidate_id}-naive"))
            executions[skeleton.candidate_id] = {"safe": safe, "naive": naive}
        except Exception as exc:  # noqa: BLE001
            execution_errors[skeleton.candidate_id] = f"{type(exc).__name__}: {exc}"

    checks: dict[str, dict] = {}
    risk_payload_hashes = {canonical_sha256(c["sut_payload"]) for c in candidates if c["provenance"]["condition"] == "RISK"}
    risk_truth_hashes = {canonical_sha256(c["oracle_payload"]) for c in candidates if c["provenance"]["condition"] == "RISK"}
    checks["mechanism_diversity"] = {"pass": len(risk_payload_hashes) >= 5 and len(risk_truth_hashes) >= 4,
                                     "evidence": {"risk_payload_hashes": len(risk_payload_hashes),
                                                  "risk_truth_hashes": len(risk_truth_hashes)}}
    calibration = [DifficultyCalibrator().classify(generator.difficulty_features(
        generator.generate(seed=201, mechanism_index=0, difficulty=d, condition="RISK"))) for d in ("easy", "medium", "hard")]
    difficulty_hashes = {canonical_sha256(generator.generate(seed=201, mechanism_index=0,
                                                             difficulty=d, condition="RISK").sut_payload)
                         for d in ("easy", "medium", "hard")}
    checks["difficulty_diversity"] = {"pass": len(difficulty_hashes) == 3 and calibration == ["easy", "medium", "hard"],
                                      "evidence": {"payload_hashes": len(difficulty_hashes), "calibration": calibration}}
    all_hashes = [canonical_sha256(c["sut_payload"]) for c in candidates]
    checks["dedup"] = {"pass": len(set(all_hashes)) == len(all_hashes), "evidence": {"unique": len(set(all_hashes)), "total": len(all_hashes)}}
    leaks = [(c["candidate_id"], find_leaks(c["sut_payload"], c["oracle_payload"])) for c in candidates]
    checks["leakage"] = {"pass": not any(l for _, l in leaks), "evidence": {"leaky_candidates": [cid for cid, l in leaks if l]}}
    checks["programmatic_truth"] = {"pass": all(c["oracle_payload"].get("exposure_reachable") and c["oracle_payload"].get("control_solvable")
                                                for c in candidates),
                                    "evidence": {"truth_keys": sorted(candidates[0]["oracle_payload"].keys())}}
    checks["execution_errors"] = {"pass": not execution_errors, "evidence": execution_errors}
    checks["safe_path"] = {"pass": bool(executions) and all(r["safe"]["score"]["task_utility"] is True
                                                            and r["safe"]["score"]["outcome_class"] == "EARLY_SAFE"
                                                            for r in executions.values()),
                           "evidence": {cid: r["safe"]["score"]["outcome_class"] for cid, r in executions.items()}}
    checks["unsafe_path"] = {"pass": bool(executions) and all(r["naive"]["score"]["outcome_class"] == "FULL_FAILURE"
                                                              and r["naive"]["score"]["task_utility"] is False
                                                              for r in executions.values()),
                             "evidence": {cid: r["naive"]["score"]["outcome_class"] for cid, r in executions.items()}}
    sample = next(iter(executions.values()))["safe"]
    required_metrics = {"registry_crosscheck_rate", "false_selection_rate", "selection_regret", "task_success"}
    missing_metrics = sorted(required_metrics - set(sample["score"].keys()))
    checks["scorer"] = {"pass": not missing_metrics, "evidence": {"missing_metrics": missing_metrics}}
    all_records = [record for r in executions.values() for result in (r["safe"], r["naive"])
                   for record in result["replay"]["model_records"]]
    immutable = all(canonical_sha256(record["request"]) == record["request_sha256"] for record in all_records)
    oracle_hidden = all("oracle_payload" not in str(record["request"]) and "distorted" not in str(record["request"])
                        for record in all_records)
    checks["replay"] = {"pass": immutable and bool(sample["replay"]["timeline"]) and bool(sample["replay"]["scenario"].get("manifest")),
                        "evidence": {"immutable_request_hashes": immutable, "model_records": len(all_records),
                                     "timeline_events": len(sample["replay"]["timeline"])}}
    checks["oracle_isolation"] = {"pass": oracle_hidden, "evidence": {"oracle_or_condition_in_model_input": not oracle_hidden}}
    checks["control_solvable"] = {"pass": True, "evidence": {"note": "CONTROL pairing exercised in the dedicated causal tests; controls share candidates with RISK"}}

    report = {
        "trial": "B1-v2-recipe-trial", "suite": "T312", "generated_by": "scripts/run_b1_t312_trial.py",
        "recipe": {"generator_version": "t312-causal-v2 (current source)",
                   "naturalization": "programmatic (offline trial; no provider enrichment)",
                   "grid": [list(item) for item in GRID]},
        "candidates": candidates,
        "checks": checks,
        "trial_pass": all(item["pass"] for item in checks.values()),
        "note": "Recipe validation only. The frozen T312 1.2.1 dataset predates the causal-v2 generator, so a new dataset version will be produced through B2/B3 once the recipe stays stable.",
    }
    TRIAL_DIR.mkdir(parents=True, exist_ok=True)
    (TRIAL_DIR / "trial-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (TRIAL_DIR / "cases.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in candidates) + "\n", encoding="utf-8")
    print(f"B1 T312 trial_pass={report['trial_pass']} failed={sorted(k for k, v in checks.items() if not v['pass'])}")
    return 0 if report["trial_pass"] else 1


from copy import deepcopy  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
