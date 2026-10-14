"""Execute v5 cases against a model and persist case-level results (strict attempt contract).

Every execution runs inside an AttemptJournal (reused from v4 infrastructure), so partial model I/O
survives interruptions. The result carries the trace, exposure proof, score axes and derived
eligibility/legacy class; nothing is retried after behavior has been produced.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.scientific_io import AttemptJournal, attempt_counter
from ioabench.v5 import V5_LAYER_VERSION
from ioabench.v5.core.case import Case
from ioabench.v5.core.engine import ENGINE_VERSION, run_episode
from ioabench.v5.core.exposure import case_exposure_proof
from ioabench.v5.core.firewall import FIREWALL_VERSION, LeakageViolation
from ioabench.v5.core.outcome import derive_outcome
from ioabench.v5.suites import load
from ioabench.v5.scenario_profiles import scenario_for

RUNNER_VERSION = "v5-runner-1.3.0"
INFRASTRUCTURE = (ProviderTransientError, ProviderPermanentError, TimeoutError, ConnectionError, OSError)


async def run_case(root: Path, case: Case, model: Any, profile: ModelProfile, *, run_id: str,
                   parameters: Mapping[str, Any], auxiliary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    module = load(case.suite_id)
    scenario = scenario_for(case)
    attempt_no = attempt_counter(root, run_id, case.case_id)
    base = {"run_id": run_id, "case_id": case.case_id, "suite_id": case.suite_id, "pair_id": case.pair_id,
            "family_id": case.family_id, "arm": case.arm, "subtype": case.subtype, "difficulty": case.difficulty,
            "domain": case.domain, "case_sha256": case.content_sha256(), "model_id": profile.model_id,
            "attempt_no": attempt_no, "simulation_only": case.simulation_only,
            "versions": {"layer": V5_LAYER_VERSION, "runner": RUNNER_VERSION, "engine": ENGINE_VERSION,
                         "firewall": FIREWALL_VERSION, "scenario": scenario.version,
                         "scorer": module.SCORER_VERSION}}
    with AttemptJournal(root, run_id, case.suite_id, case.case_id, attempt_no) as journal:
        try:
            trace = await run_episode(case, scenario, model, profile, parameters=parameters, auxiliary=auxiliary)
        except LeakageViolation as exc:
            # The firewall raised before the observation reached the model, so the
            # episode ends unscored for this attempt instead of aborting the batch;
            # the offending observation is named in the error for follow-up.
            evidence = journal.partial_evidence()
            return {**base, "status": "LEAKAGE_BLOCKED", "error": str(exc), "attempt_journal": evidence["attempt_journal"],
                    "outcome": derive_outcome("LEAKAGE_BLOCKED", {}, None)}
        except INFRASTRUCTURE as exc:
            evidence = journal.partial_evidence()
            status = "INFRA_INTERRUPTED" if evidence["valid_model_behavior_observed"] else "RETRYABLE_INFRA_FAILURE"
            return {**base, "status": status, "error": f"{type(exc).__name__}: {exc}",
                    "attempt_journal": evidence["attempt_journal"], "outcome": derive_outcome(status, {}, None)}
        evidence = journal.partial_evidence()
    proof = case_exposure_proof(trace.records, case, trace.decision_tools)
    score = module.score(trace, case) if trace.status == "COMPLETED" else None
    return {**base, "status": trace.status, "error": trace.error_detail, "exposure": proof,
            "score": None if score is None else score.as_dict(), "outcome": derive_outcome(trace.status, proof, score),
            "malformed_calls": trace.malformed_calls, "model_calls": len(trace.records),
            "attempt_journal": evidence["attempt_journal"],
            "trace": {"actions": [a.as_dict() for a in trace.actions], "events": trace.events,
                      "final_state": trace.final_state, "records": trace.records,
                      "records_sha256": canonical_sha256(trace.records)}}


def append_result(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
