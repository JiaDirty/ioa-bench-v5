"""Versioned engineering acceptance on existing 18 classic + 19 dynamic structures; no API."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.models import ModelProfile
from ioabench.v5.core.case import SUITES
from ioabench.v5.dynamic import registry
from ioabench.v5.evaluation import atomic_json, read_results, run_batch, safe_id, writer_lock
from ioabench.v5.replay import replay_case
from ioabench.v5.suites import load


def _adapter_map():
    return ({suite: load(suite) for suite in SUITES}
            | {suite: registry.get_adapter(suite) for suite in registry.implemented()})


def _check_reference_behavior(cases, rows, policy, adapters):
    expected_cases = {case.case_id: case for case in cases}
    observed_rows = {}
    issues = []
    for row in rows:
        case_id = row.get("case_id")
        if case_id not in expected_cases or case_id in observed_rows:
            issues.append({"case_id": case_id, "reason": "unexpected or duplicate result"})
            continue
        observed_rows[case_id] = row
    for case_id, case in expected_cases.items():
        row = observed_rows.get(case_id)
        if row is None:
            issues.append({"case_id": case_id, "reason": "missing result"})
            continue
        score, outcome = row.get("score") or {}, row.get("outcome") or {}
        expected_safety = adapters[case.suite_id].EXPECTED_REFERENCE[policy][case.arm]
        if row.get("status") != "COMPLETED" or row.get("scientifically_eligible") is not True:
            issues.append({"case_id": case_id, "reason": "incomplete or scientifically ineligible"})
        if not row.get("exposure", {}).get("exposed") or not row.get("exposure", {}).get("opportunity"):
            issues.append({"case_id": case_id, "reason": "stimulus or decision opportunity not observed"})
        if score.get("safety") != expected_safety:
            issues.append({"case_id": case_id, "reason": "reference safety mismatch",
                           "expected": expected_safety, "actual": score.get("safety")})
        if outcome.get("unsafe_any") != (expected_safety in {"UNSAFE", "UNSAFE_RECOVERED"}):
            issues.append({"case_id": case_id, "reason": "safety outcome contradicts suite reference"})
        if row.get("simulation_only") is not case.simulation_only:
            issues.append({"case_id": case_id, "reason": "SIMULATION_ONLY flag mismatch"})
    return {"passed": not issues, "checked_cases": len(expected_cases), "issues": issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    safe_id(args.run_id)
    directory = ROOT / "artifacts" / "v5" / "system_acceptance" / args.run_id
    directory.mkdir(parents=True, exist_ok=True)
    with writer_lock(directory):
        path = directory / "system-cases.jsonl"
        if path.exists():
            raise FileExistsError("acceptance already has inputs; use a new run ID")
        started = datetime.now(timezone.utc).isoformat()
        adapters = _adapter_map()
        cases = [case for adapter in adapters.values() for pair in adapter.generate(seed=11, families=1)[:1] for case in pair]
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for case in cases:
                stream.write(json.dumps(case.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        profile = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
        runs = []
        for policy in ("witness", "naive"):
            run_id = f"{args.run_id}-{policy}"
            run_batch(ROOT, path, run_id=run_id, profile=profile, reference_policy=policy)
            run_dir = ROOT / "artifacts" / "v5" / "evaluations" / run_id
            rows = read_results(run_dir)
            behavior = _check_reference_behavior(cases, rows, policy, adapters)
            before = (run_dir / "results.jsonl").read_bytes()
            run_batch(ROOT, path, run_id=run_id, profile=profile, reference_policy=policy, resume=True)
            resumed = before == (run_dir / "results.jsonl").read_bytes()
            replay = [replay_case(ROOT, run_id, case.case_id) for case in cases]
            atomic_json(directory / f"replay-{policy}.json", replay)
            runs.append({"policy": policy, "run_id": run_id, "scheduled": len(cases),
                         "completed": sum(row["status"] == "COMPLETED" for row in rows),
                         "ledger_integrity_passes": sum(row["monitor_report"]["ledger_integrity"]["passed"] is True for row in rows),
                         "behavior_check": behavior,
                         "exposed_cases": sum(bool(row.get("exposure", {}).get("exposed")) for row in rows),
                         "decision_opportunities": sum(bool(row.get("exposure", {}).get("opportunity")) for row in rows),
                         "replay_passes": sum(result["passed"] for result in replay),
                         "resumed_without_reexecution": resumed,
                         "safety_counts": {label: sum((row.get("score") or {}).get("safety") == label for row in rows)
                                           for label in ("SAFE", "UNSAFE", "UNSAFE_RECOVERED")}})
        passed = (len(cases) == 74 and all(r["completed"] == 74 and r["ledger_integrity_passes"] == 74
                                         and r["behavior_check"]["passed"] and r["exposed_cases"] == 74
                                         and r["decision_opportunities"] == 74
                                         and r["replay_passes"] == 74 and r["resumed_without_reexecution"] for r in runs))
        result = {"evidence_class": "ENGINEERING_REFERENCE", "passed": passed,
                  "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
                  "classic_suites": len(SUITES), "dynamic_structures": len(registry.implemented()),
                  "supplied_cases": len(cases), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "runs": runs, "provider_calls": 0, "publication_ready": False,
                  "scope": "Existing adapter engineering fixtures checked against declared reference outcomes; not qualified data or arbitrary-world compiler coverage."}
        atomic_json(directory / "acceptance.json", result)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
