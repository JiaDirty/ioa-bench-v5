"""Compare sealed tool observations and reanalyse retained responses without providers."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.engine import ENGINE_VERSION, run_episode
from ioabench.v5.core.exposure import case_exposure_proof
from ioabench.v5.core.outcome import derive_outcome
from ioabench.v5.core.trace_integrity import inspect_tool_observations as inspect_trace
from ioabench.v5.dynamic.runner import _resolve_scenario
from ioabench.v5.evaluation import adapter_for, atomic_json
from ioabench.v5.replay import RecordedPort


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def reanalyse(row, case, manifest):
    port = RecordedPort(row["trace"]["records"])
    adapter = adapter_for(case)
    auxiliary = adapter.reference_auxiliary() if hasattr(adapter, "reference_auxiliary") else None
    trace = asyncio.run(run_episode(case, _resolve_scenario(adapter), port,
        ModelProfile(**manifest["profile"]), parameters=manifest["parameters"], auxiliary=auxiliary))
    proof = case_exposure_proof(trace.records, case, trace.decision_tools)
    score = adapter.score(trace, case) if trace.status == "COMPLETED" else None
    actions = [item.as_dict() for item in trace.actions]
    actual = {"status": trace.status, "events": trace.events, "final_state": trace.final_state,
              "exposure": proof, "score": score.as_dict() if score else None,
              "outcome": derive_outcome(trace.status, proof, score)}
    expected = {key: row["trace"][key] if key in {"events", "final_state"} else row[key]
                for key in actual}
    checks = {key: canonical_sha256(actual[key]) == canonical_sha256(expected[key]) for key in actual}
    checks["all_original_requests_exactly_matched"] = port.consumed == len(port.records)
    checks["action_arguments_order_status_and_state_hashes"] = canonical_sha256(
        [{k: v for k, v in a.items() if k != "result"} for a in actions]) == canonical_sha256(
        [{k: v for k, v in a.items() if k != "result"} for a in row["trace"]["actions"]])
    consistent = inspect_trace({"actions": actions, "records": trace.records})
    checks["corrected_tool_observations_consistent"] = not consistent["mismatches"] and not consistent["alignment_errors"]
    changed = [index for index, (old, new) in enumerate(zip(row["trace"]["actions"], actions)) if old != new]
    return {"checks": checks, "changed_action_indices": changed,
            "corrected_actions_sha256": canonical_sha256(actions),
            "corrected_comparison_count": consistent["compared"], "provider_calls": 0}


def diagnose(baseline, out):
    census = read(baseline)
    rows, suites = [], Counter()
    for pair in census["pairs"]:
        source = Path(pair["source_directory"])
        reference = source / "STRICT_REFERENCE_RESULTS.json"
        digest = hashlib.sha256(reference.read_bytes()).hexdigest()
        if digest != pair["source_evidence_sha256"][reference.name]:
            raise ValueError("sealed baseline evidence changed: " + pair["id"])
        cases = {item["case_id"]: case_from_dict(item, allow_dynamic=True) for item in read(source / "PAIR.json")}
        for ordinal, row in enumerate(read(reference)):
            old = inspect_trace(row["trace"])
            item = {"pair_id": pair["id"], "suite": pair["suite"], "case_id": row["case_id"],
                    "run_id": row["run_id"], "row_ordinal": ordinal,
                    "source_file": str(reference), "source_sha256": digest, "historical_observations": old}
            try:
                manifest = read(source / "strict/artifacts/v5/evaluations" / row["run_id"] / "manifest.json")
                item["current_engine_reanalysis"] = reanalyse(row, cases[row["case_id"]], manifest)
            except Exception as exc:
                item["current_engine_reanalysis"] = {"status": "FAIL", "error": type(exc).__name__ + ": " + str(exc), "provider_calls": 0}
            if old["mismatches"]:
                suites[pair["suite"]] += 1
            rows.append(item)
    affected = sorted({row["pair_id"] for row in rows if row["historical_observations"]["mismatches"]})
    reanalysis_pass = sum(all(row["current_engine_reanalysis"].get("checks", {"missing": False}).values()) for row in rows)
    report = {"version": "ioabench.v5.trace-aliasing-forensic/1.0.0", "engine_version": ENGINE_VERSION,
        "baseline_file": str(baseline), "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
        "scope": "32 preserved baseline pairs; sealed strict reference traces; retained-response reanalysis only",
        "provider_calls": 0, "original_evidence_modified": False, "strict_historical_replay_claim": False,
        "new_generation_requests": 0, "pair_count": len(census["pairs"]), "reference_rows": len(rows),
        "affected_pair_ids": affected, "affected_rows_by_suite": dict(suites),
        "historical_mismatch_count": sum(len(x["historical_observations"]["mismatches"]) for x in rows),
        "historical_alignment_error_count": sum(len(x["historical_observations"]["alignment_errors"]) for x in rows),
        "current_reanalysis_pass": reanalysis_pass, "current_reanalysis_fail": len(rows) - reanalysis_pass,
        "limitation": "Only tool results later present in a retained SUT request are directly comparable. Missing terminal observations remain unverified; source-version differences are labelled reanalysis, never strict historical replay.",
        "pool_requirement": "Keep originals and historical PASS records immutable. Affected packets require versioned corrected execution evidence and fresh audit before current development admission; do not silently repair old evidence.",
        "rows": rows}
    if out.exists() and read(out) != report:
        raise ValueError("immutable forensic report differs; use a new output version")
    if not out.exists():
        atomic_json(out, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose(args.baseline, args.out)
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False))
