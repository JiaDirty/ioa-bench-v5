"""Read-only replay using retained responses, without contacting a provider."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.core.case import SUITES, case_from_dict
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.exposure import case_exposure_proof
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity, message_flow
from ioabench.v5.core.outcome import derive_outcome
from ioabench.v5.dynamic.runner import _resolve_scenario
from ioabench.v5.evaluation import CODE_ROOT, adapter_for, read_results, safe_id
from ioabench.v5.scenario_profiles import scenario_for, validate_profile


class RecordedPort:
    def __init__(self, records: list[dict[str, Any]]):
        self.records, self.consumed = records, 0
        for record in records:
            if canonical_sha256(record["request"]) != record["request_sha256"]:
                raise ValueError("recorded request hash mismatch")

    async def generate(self, profile, request):
        if self.consumed >= len(self.records):
            raise ValueError("replay requested an unrecorded response")
        expected = self.records[self.consumed]
        snapshot = {"messages": list(request.messages), "tools": list(request.tools),
                    "parameters": dict(request.parameters), "role_metadata": dict(request.role_metadata)}
        if canonical_sha256(snapshot) != expected["request_sha256"]:
            raise ValueError(f"replay request/role/order mismatch at record {self.consumed}")
        self.consumed += 1
        response = {key: value for key, value in expected["response"].items() if key != "elapsed_seconds"}
        return ModelResponse(**response)


def replay_case(root: Path, run_id: str, case_id: str) -> dict[str, Any]:
    return _replay_case(root, run_id, case_id, reanalysis=False)


def reanalyse_case(root: Path, run_id: str, case_id: str) -> dict[str, Any]:
    """Re-score retained responses under current code; never call this strict historical replay."""
    return _replay_case(root, run_id, case_id, reanalysis=True)


def _replay_case(root: Path, run_id: str, case_id: str, *, reanalysis: bool) -> dict[str, Any]:
    safe_id(run_id)
    safe_id(case_id)
    directory = root / "artifacts" / "v5" / "evaluations" / run_id
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    current_source = source_tree_hash(CODE_ROOT)
    if not reanalysis and manifest["source_sha256"] != current_source:
        raise ValueError("replay source differs from pinned source; restore recorded version")
    cases = [case_from_dict(json.loads(line), allow_dynamic=True)
             for line in (directory / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    case = next((case for case in cases if case.case_id == case_id), None)
    if case is None:
        raise ValueError("case is absent from pinned inputs")
    pin = next(item for item in manifest["cases"] if item["case_id"] == case_id)
    if case.content_sha256() != pin["case_sha256"]:
        raise ValueError("replay case hash mismatch")
    rows = read_results(directory)
    candidates = [row for row in rows if row["case_id"] == case_id and "trace" in row]
    if not candidates:
        return {"case_id": case_id, "passed": False, "status": "NO_COMPLETE_TRACE"}
    if len(candidates) != 1:
        return {"case_id": case_id, "passed": False, "status": "DUPLICATE_TERMINAL_RESULTS",
                "candidate_count": len(candidates), "provider_calls": 0}
    row = candidates[-1]
    if row["case_sha256"] != case.content_sha256():
        raise ValueError("result case binding mismatch")
    journal = root / row["attempt_journal"]["path"]
    if not journal.resolve().is_relative_to(root.resolve()):
        raise ValueError("journal path escapes workspace")
    if hashlib.sha256(journal.read_bytes()).hexdigest() != row["attempt_journal"]["sha256"]:
        raise ValueError("attempt journal hash mismatch")
    entries = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
    persisted = [entry["record"] for entry in entries if entry.get("kind") == "model_record"]
    for entry in entries:
        if entry.get("kind") == "model_record" and canonical_sha256(entry["record"]) != entry["record_sha256"]:
            raise ValueError("journal record hash mismatch")
    records = row["trace"]["records"]
    if (canonical_sha256(records) != row["trace"]["records_sha256"]
            or canonical_sha256(persisted) != canonical_sha256(records)):
        raise ValueError("trace/journal response evidence mismatch")
    port = RecordedPort(records)
    adapter = adapter_for(case)
    validate_profile(case)
    scenario = (scenario_for(case) if case.suite_id in SUITES
                else _resolve_scenario(adapter))
    auxiliary = adapter.reference_auxiliary() if hasattr(adapter, "reference_auxiliary") else None
    profile = ModelProfile(**manifest["profile"])
    trace = asyncio.run(run_episode(case, scenario, port, profile, parameters=manifest["parameters"], auxiliary=auxiliary))
    proof = case_exposure_proof(trace.records, case, trace.decision_tools)
    score = adapter.score(trace, case) if trace.status == "COMPLETED" else None
    actual = {"status": trace.status, "actions": [action.as_dict() for action in trace.actions],
              "events": trace.events, "final_state": trace.final_state, "exposure": proof,
              "score": score.as_dict() if score else None, "outcome": derive_outcome(trace.status, proof, score)}
    expected = {"status": row["status"], "actions": row["trace"]["actions"], "events": row["trace"]["events"],
                "final_state": row["trace"]["final_state"], "exposure": row["exposure"],
                "score": row["score"], "outcome": row["outcome"]}
    checks = {key: canonical_sha256(value) == canonical_sha256(expected[key]) for key, value in actual.items()}
    checks["all_responses_consumed"] = port.consumed == len(records)
    if "monitor_report" in row:
        flow = message_flow(trace)
        monitor = {"ledger_integrity": ledger_integrity(trace),
                   "timing_properties": evaluate_timing(trace, list(getattr(adapter, "TIMING_RULES", ()))),
                   "message_flow": {"paired": flow["paired"], "undelivered_enqueues": len(flow["undelivered_enqueues"])}}
        checks["monitors"] = all(canonical_sha256(value) == canonical_sha256(row["monitor_report"][key])
                                 for key, value in monitor.items())
    if reanalysis:
        behavior_checks = {key: value for key, value in checks.items() if key not in {"score", "outcome"}}
        if not all(behavior_checks.values()):
            raise ValueError(f"reanalysis changed recorded behavior: {behavior_checks}")
        updated = {**row, "score": actual["score"], "outcome": actual["outcome"],
                   "evidence_class": "RECORDED_RESPONSE_REANALYSIS_NOT_NEW_ONLINE_RUN",
                   "versions": {**row["versions"], "scorer": score.scorer_version if score else None},
                   "scientifically_eligible": actual["outcome"]["eligibility"] == "ELIGIBLE"
                       and not row.get("ineligibility_reasons")
                       and row.get("monitor_report", {}).get("ledger_integrity", {}).get("passed") is True
                       and not row.get("monitor_report", {}).get("timing_properties", {}).get("indeterminate")}
        return {"case_id": case_id, "passed": True, "evidence_class": updated["evidence_class"],
                "original_source_sha256": manifest["source_sha256"], "analysis_source_sha256": current_source,
                "original_row_sha256": canonical_sha256(row), "original_score": row["score"],
                "original_outcome": row["outcome"], "behavior_checks": behavior_checks,
                "score_unchanged": checks["score"], "outcome_unchanged": checks["outcome"],
                "responses_consumed": port.consumed, "provider_calls": 0, "result": updated}
    return {"case_id": case_id, "passed": all(checks.values()), "checks": checks,
            "responses_consumed": port.consumed, "provider_calls": 0}
