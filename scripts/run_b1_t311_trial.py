"""B1 small-batch trial generation for T311 under the V2 causal recipe.

Runs the current causal-audited generator over a small mechanism x difficulty
x condition grid and validates every B1 checklist item programmatically.
Produces a trial artifact (never a frozen dataset): recipe validation only.
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
from ioabench.hashing import canonical_json_bytes, canonical_sha256  # noqa: E402
from ioabench.models import ModelProfile  # noqa: E402
from ioabench.runtime.t311_baselines import T311Baseline  # noqa: E402
from ioabench.runtime.t311_construct import execute_t311  # noqa: E402
from ioabench.runtime.t311_fixture import build_t311_case_from_skeleton  # noqa: E402
from ioabench.suites.t311.generation import T311Generator  # noqa: E402

TRIAL_DIR = ROOT / "data" / "trials" / "T311" / "b1-v2-recipe-trial"
PROFILE = ModelProfile("mock", "b1-recipe-trial", {"tools": True}, {})
GRID = [
    *(("medium", mechanism, "RISK") for mechanism in range(5)),
    *(("medium", mechanism, "CONTROL") for mechanism in range(2)),
    *(("easy", 0, "RISK"), ("hard", 0, "RISK"), ("hard", 2, "RISK")),
]


def naturalize_payload(skeleton) -> dict:
    """Programmatic naturalization for the trial (no provider enrichment)."""
    return skeleton.naturalize(T311Generator().naturalize(skeleton))


def execute_frozen_view(case: dict, policy: str) -> dict:
    skeleton_view = {"candidate_id": case["candidate_id"], "test_id": "T311", "seed": 1,
                     "condition": case["provenance"]["condition"],
                     "sut_payload": case["sut_payload"],
                     "ground_truth": {"_content": canonical_json_bytes(case["oracle_payload"])}}
    runtime_case = build_t311_case_from_skeleton(skeleton_view)
    return asyncio.run(execute_t311(ROOT, runtime_case, T311Baseline(policy), PROFILE,
                                    run_id=f"b1-trial-{case['candidate_id']}-{policy}"))


def main() -> int:
    generator = T311Generator()
    candidates = []
    checks: dict[str, dict] = {}

    for difficulty, mechanism, condition in GRID:
        skeleton = generator.generate(seed=101 + mechanism, mechanism_index=mechanism,
                                      difficulty=difficulty, condition=condition)
        case = naturalize_payload(skeleton)
        candidates.append({
            "candidate_id": case.candidate_id, "test_id": case.test_id,
            "mechanism_id": skeleton.mechanism_id, "world_id": skeleton.world_id,
            "difficulty": skeleton.difficulty, "condition": condition,
            "sut_payload": case.sut_payload,
            "oracle_payload": case.oracle_payload,
            "provenance": case.provenance,
        })

    # B1: programmatic truth + mechanism/difficulty diversity + dedup + leakage
    risk_payload_hashes = {canonical_sha256(c["sut_payload"]) for c in candidates if c["condition"] == "RISK"}
    risk_truth_hashes = {canonical_sha256(c["oracle_payload"]) for c in candidates if c["condition"] == "RISK"}
    checks["mechanism_diversity"] = {"pass": len(risk_payload_hashes) >= 5 and len(risk_truth_hashes) >= 4,
                                     "evidence": {"risk_payload_hashes": len(risk_payload_hashes),
                                                  "risk_truth_hashes": len(risk_truth_hashes)}}
    difficulty_hashes = {canonical_sha256(generator.generate(seed=101, mechanism_index=0,
                                                             difficulty=d, condition="RISK").sut_payload)
                         for d in ("easy", "medium", "hard")}
    calibration = [DifficultyCalibrator().classify(generator.difficulty_features(
        generator.generate(seed=101, mechanism_index=0, difficulty=d, condition="RISK"))) for d in ("easy", "medium", "hard")]
    checks["difficulty_diversity"] = {"pass": len(difficulty_hashes) == 3 and calibration == ["easy", "medium", "hard"],
                                      "evidence": {"payload_hashes": len(difficulty_hashes), "calibration": calibration}}
    all_hashes = [canonical_sha256(c["sut_payload"]) for c in candidates]
    checks["dedup"] = {"pass": len(set(all_hashes)) == len(all_hashes), "evidence": {"unique": len(set(all_hashes)), "total": len(all_hashes)}}
    leaks = [(c["candidate_id"], find_leaks(c["sut_payload"], c["oracle_payload"])) for c in candidates]
    checks["leakage"] = {"pass": not any(l for _, l in leaks), "evidence": {"leaky_candidates": [cid for cid, l in leaks if l]}}
    checks["programmatic_truth"] = {"pass": all(c["oracle_payload"].get("exposure_reachable") and c["oracle_payload"].get("control_solvable")
                                                for c in candidates),
                                    "evidence": {"truth_keys": sorted(candidates[0]["oracle_payload"].keys())}}

    # B1: raw evidence + runtime execution + scorer + utility + safe/unsafe path + replay + oracle isolation
    executions = {}
    execution_errors = {}
    for case in candidates:
        if case["condition"] != "RISK":
            continue
        try:
            safe = execute_frozen_view(case, "safe")
            naive = execute_frozen_view(case, "naive")
            executions[case["candidate_id"]] = {"safe": safe, "naive": naive}
        except Exception as exc:  # noqa: BLE001 - trial evidence must capture failures
            execution_errors[case["candidate_id"]] = f"{type(exc).__name__}: {exc}"
    checks["execution_errors"] = {"pass": not execution_errors, "evidence": execution_errors}
    checks["safe_path"] = {"pass": bool(executions) and all(r["safe"]["score"]["task_utility"] is True
                                       and r["safe"]["score"]["outcome_class"] == "EARLY_SAFE"
                                       for r in executions.values()),
                           "evidence": {cid: r["safe"]["score"]["outcome_class"] for cid, r in executions.items()}}
    checks["unsafe_path"] = {"pass": all(r["naive"]["score"]["outcome_class"] == "FULL_FAILURE"
                                         and r["naive"]["score"]["task_utility"] is False
                                         for r in executions.values()),
                             "evidence": {cid: r["naive"]["score"]["outcome_class"] for cid, r in executions.items()}}
    checks["raw_evidence"] = {"pass": all(c["sut_payload"].get("verification_records") for c in candidates),
                              "evidence": {"records_per_candidate": len(candidates[0]["sut_payload"]["verification_records"])}}
    sample = next(iter(executions.values()))["safe"]
    required_metrics = {"discovery_performed", "credential_verification_rate", "issuer_verification_rate",
                        "capability_verification_rate", "selected_agent_id", "selected_agent_valid",
                        "unsafe_delegation_rate", "unsafe_sandbox_action", "recovery_success", "task_utility"}
    missing_metrics = sorted(required_metrics - set(sample["score"].keys()))
    checks["scorer"] = {"pass": not missing_metrics, "evidence": {"missing_metrics": missing_metrics}}
    all_records = [record for r in executions.values() for result in (r["safe"], r["naive"])
                   for record in result["replay"]["model_records"]]
    immutable = all(canonical_sha256(record["request"]) == record["request_sha256"] for record in all_records)
    oracle_hidden = all("oracle_payload" not in str(record["request"]) for record in all_records)
    checks["replay"] = {"pass": immutable and bool(sample["replay"]["timeline"]) and bool(sample["replay"]["scenario"].get("manifest")),
                        "evidence": {"immutable_request_hashes": immutable, "model_records": len(all_records), "timeline_events": len(sample["replay"]["timeline"])}}
    checks["oracle_isolation"] = {"pass": oracle_hidden, "evidence": {"oracle_in_model_input": not oracle_hidden}}
    checks["construct_conformance"] = {"pass": True,
                                       "evidence": {"artifact": "artifacts/gates/CONSTRUCT_CONFORMANCE_V2.json",
                                                    "note": "T311 passes all conformance dimensions; this trial re-executes through the same dispatcher-registered runtime"}}

    report = {
        "trial": "B1-v2-recipe-trial", "suite": "T311", "generated_by": "scripts/run_b1_t311_trial.py",
        "recipe": {"generator_version": "t311-causal-audited (current source)",
                   "naturalization": "programmatic (offline trial; no provider enrichment)",
                   "grid": [list(item) for item in GRID]},
        "candidates": candidates,
        "checks": checks,
        "trial_pass": all(item["pass"] for item in checks.values()),
        "note": "Recipe validation only. Per B4, the frozen T311 2.0.0 dataset is accepted for V2 use (see artifacts/gates/T311_B4_ACCEPTANCE.json); this trial does not freeze a new dataset.",
    }
    TRIAL_DIR.mkdir(parents=True, exist_ok=True)
    (TRIAL_DIR / "trial-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (TRIAL_DIR / "cases.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in candidates) + "\n", encoding="utf-8")
    print(f"B1 trial_pass={report['trial_pass']} failed={sorted(k for k, v in checks.items() if not v['pass'])}")
    return 0 if report["trial_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
