"""Opt-in formal execution entry for dynamic-slice cases (post-audit P1).

The frozen classic ``runner.run_case`` resolves scenarios via the 18-suite registry and stays
byte-compatible with historical data; this module adds a SEPARATE entry for dynamic cases that
explicitly receives the slice's adapter surface (scenario, scorer, policies, timing rules,
fine arm delta, simulation flag) and additionally wires the global monitors into every run:

* mandatory machine-readable ``monitor_report`` (ledger integrity, timing properties,
  message flow) on every episode;
* monitor/integrity failures mark the result ``scientifically_eligible: false`` with a
  versioned ineligibility reason — the result is never presented as a valid scientific sample
  (mapping onto the existing outcome denominator rules; no new outcome enum values);
* exposure/opportunity evidence, scorer verdicts and the attempt journal are produced exactly
  as the classic runner does, so dynamic results are reviewable with the same tooling.

The frozen 18-suite registry, historical datasets, existing scorers and the v1.1.2 online
protocol are untouched.
"""
from __future__ import annotations

import hashlib
import json
from contextvars import copy_context
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.scientific_io import AttemptJournal, attempt_counter
from ioabench.v5.core.case import Case
from ioabench.v5.core.engine import ENGINE_VERSION, run_episode
from ioabench.v5.core.exposure import case_exposure_proof
from ioabench.v5.core.firewall import FIREWALL_VERSION, LeakageViolation
from ioabench.v5.core.monitor import TimingRule, evaluate_timing, ledger_integrity, message_flow
from ioabench.v5.core.outcome import derive_outcome

RUNNER_VERSION = "v5-dynamic-runner-1.1.0"
INFRASTRUCTURE = (ProviderPermanentError, ProviderTransientError, TimeoutError, ConnectionError, OSError)

# monitor failure modes that make a result ineligible for the science denominator; the reason
# strings are versioned here so downstream analysis can map them onto the outcome contract
# without inventing unsupported outcome-enum values (post-audit amendment G2).
INELIGIBILITY_REASONS = {
    "LEDGER_INTEGRITY_FAILED": "event/action 1:1 linkage or ledger structure verification failed",
    "TIMING_INDETERMINATE": "timing evidence could not be ordered in the declared time base",
}


class DynamicAdapter(Protocol):
    """The adapter surface a dynamic slice must expose to the formal runner."""

    suite_id: str
    version: str

    def score(self, trace: Any, case: Case) -> Any: ...
    def policies(self) -> dict[str, Any]: ...
    def reference_auxiliary(self) -> dict[str, Any] | None: ...


def adapter_fingerprint(module: Any) -> dict[str, Any]:
    """The locked adapter identity recorded into every result (amendment: measurement contract)."""
    scenario_cls = None
    module_name = module.__name__.rsplit(".", 1)[-1]
    attr = _SCENARIO_REGISTRY.get(module_name)
    if attr and hasattr(module, attr):
        scenario_cls = getattr(module, attr)
    else:
        for a in dir(module):
            if "Dynamic" in a and "Scenario" in a and not a.startswith("_"):
                scenario_cls = getattr(module, a)
                break
    version = getattr(scenario_cls, "version", "") if scenario_cls else ""
    return {
        "adapter_module": module.__name__,
        "suite_id": getattr(module, "SLICE_ID", ""),
        "scenario_class": scenario_cls.__name__ if scenario_cls else "",
        "scenario_version": version,
        "scorer_version": getattr(module, "SCORER_VERSION", ""),
        "runner_version": RUNNER_VERSION,
        "engine_version": ENGINE_VERSION,
        "firewall_version": FIREWALL_VERSION,
    }


_SCENARIO_REGISTRY = {
    "t321_slice": "T321DynamicAScenario",
    "t321_slice_b": "T321DynamicBScenario",
    "t312_slice": "T312DynamicScenario",
    "t311_slice": "T311DynamicScenario",
    "t313_slice": "T313DynamicScenario",
    "t322_slice": "T322DynamicScenario",
    "t323_slice": "T323DynamicScenario",
    "t331_slice": "T331DynamicScenario",
    "t332_slice": "T332DynamicScenario",
    "t333_slice": "T333DynamicScenario",
    "t341_slice": "T341DynamicScenario",
    "t342_slice": "T342DynamicScenario",
    "t343_slice": "T343DynamicScenario",
    "t351_slice": "T351DynamicScenario",
    "t352_slice": "T352DynamicScenario",
    "t353_slice": "T353DynamicScenario",
    "t361_slice": "T361DynamicScenario",
    "t362_slice": "T362DynamicScenario",
    "t363_slice": "T363DynamicScenario",
}


def _resolve_scenario(adapter_module: Any) -> Any:
    module_name = adapter_module.__name__.rsplit(".", 1)[-1]
    attr = _SCENARIO_REGISTRY.get(module_name)
    if attr and hasattr(adapter_module, attr):
        return getattr(adapter_module, attr)()
    for attr in dir(adapter_module):
        if "Dynamic" in attr and "Scenario" in attr and not attr.startswith("_"):
            return getattr(adapter_module, attr)()
    raise ValueError(f"adapter module {adapter_module.__name__} exposes no DynamicScenario")


def run_dynamic_case(root: Path, case: Case, adapter_module: Any, model: Any, profile: ModelProfile, *,
                     run_id: str, parameters: Mapping[str, Any],
                     timing_rules: Sequence[TimingRule] | None = None) -> dict[str, Any]:
    """Execute one dynamic case with the full evidence + monitor chain.

    Mirrors the classic ``runner.run_case`` contract (attempt journal, exposure/opportunity,
    score axes, derived outcome) and adds the mandatory ``monitor_report``. The dynamic
    scenario/scorer are supplied explicitly by the caller — the frozen 18-suite registry is
    never consulted.
    """
    suite_id = case.suite_id
    if suite_id != getattr(adapter_module, "SLICE_ID", None):
        raise ValueError(f"case suite {suite_id} does not match dynamic adapter {getattr(adapter_module, 'SLICE_ID', None)}")
    if timing_rules is None:
        timing_rules = getattr(adapter_module, "TIMING_RULES", ())
    scenario_instance = _resolve_scenario(adapter_module)
    auxiliary = (adapter_module.reference_auxiliary()
                 if hasattr(adapter_module, "reference_auxiliary") else None)

    attempt_no = attempt_counter(root, run_id, case.case_id)
    base = {"run_id": run_id, "case_id": case.case_id, "suite_id": suite_id,
            "pair_id": case.pair_id, "family_id": case.family_id, "arm": case.arm,
            "subtype": case.subtype, "difficulty": case.difficulty, "domain": case.domain,
            "case_sha256": case.content_sha256(), "model_id": profile.model_id,
            "attempt_no": attempt_no, "simulation_only": case.simulation_only,
            "versions": {"runner": RUNNER_VERSION, "engine": ENGINE_VERSION,
                         "firewall": FIREWALL_VERSION,
                         "scenario": getattr(adapter_module, "SCENARIO_VERSION", ""),
                         "scorer": getattr(adapter_module, "SCORER_VERSION", "")},
            "adapter": adapter_fingerprint(adapter_module)}

    with AttemptJournal(root, run_id, suite_id, case.case_id, attempt_no) as journal:
        try:
            trace = await_run_episode(case, scenario_instance, model, profile, parameters,
                                      auxiliary)
        except LeakageViolation as exc:
            evidence = journal.partial_evidence()
            return _failed_result(base, evidence, "LEAKAGE_BLOCKED", str(exc))
        except INFRASTRUCTURE as exc:
            evidence = journal.partial_evidence()
            status = "INFRA_INTERRUPTED" if evidence["valid_model_behavior_observed"] else "RETRYABLE_INFRA_FAILURE"
            return _failed_result(base, evidence, status, f"{type(exc).__name__}: {exc}")
        evidence = journal.partial_evidence()

    proof = case_exposure_proof(trace.records, case, trace.decision_tools)
    score = adapter_module.score(trace, case) if trace.status == "COMPLETED" else None

    # ---- mandatory global monitors (post-audit P1-B) ----
    integrity = ledger_integrity(trace)
    timing = evaluate_timing(trace, list(timing_rules))
    flow = message_flow(trace)
    monitor_report = {"monitor_version": "v5-dynamic-runner-monitor-1.0.0",
                      "ledger_integrity": integrity,
                      "timing_properties": timing,
                      "message_flow": {"paired": flow["paired"],
                                       "undelivered_enqueues": len(flow["undelivered_enqueues"])}}
    ineligibility = []
    if not integrity["passed"]:
        ineligibility.append("LEDGER_INTEGRITY_FAILED")
    if not timing["passed"] and timing.get("indeterminate"):
        ineligibility.append("TIMING_INDETERMINATE")

    outcome = derive_outcome(trace.status, proof, score)
    if outcome["eligibility"] != "ELIGIBLE" and outcome["eligibility"] not in ineligibility:
        ineligibility.append(outcome["eligibility"])
    result = {**base, "status": trace.status, "error": trace.error_detail,
              "exposure": proof,
              "score": None if score is None else score.as_dict(),
              "outcome": outcome,
              "monitor_report": monitor_report,
              "scientifically_eligible": trace.status == "COMPLETED" and not ineligibility,
              "ineligibility_reasons": ineligibility,
              "malformed_calls": trace.malformed_calls, "model_calls": len(trace.records),
              "attempt_journal": evidence["attempt_journal"],
              "trace": {"actions": [a.as_dict() for a in trace.actions], "events": trace.events,
                        "final_state": trace.final_state, "records": trace.records,
                        "records_sha256": canonical_sha256(trace.records)}}
    return result


def _failed_result(base: Mapping[str, Any], evidence: Mapping[str, Any], status: str, error: str) -> dict[str, Any]:
    # Partial model I/O is durable, but no complete trace exists for global monitor claims.
    return {**base, "status": status, "error": error,
            "attempt_journal": evidence["attempt_journal"],
            "model_calls": evidence["model_records_produced"],
            "outcome": derive_outcome(status, {}, None),
            "monitor_report": {"monitor_version": "v5-dynamic-runner-monitor-1.0.0",
                               "status": "NOT_AVAILABLE", "reason": status,
                               "ledger_integrity": {"passed": None},
                               "timing_properties": {"passed": None},
                               "message_flow": {"paired": None, "undelivered_enqueues": None}},
            "scientifically_eligible": False, "ineligibility_reasons": [status]}


def await_run_episode(case: Case, scenario: Any, model: Any, profile: ModelProfile,
                      parameters: Mapping[str, Any], auxiliary: Mapping[str, Any] | None = None) -> Any:
    """Synchronous wrapper so callers without a running loop can execute one episode."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_episode(case, scenario, model, profile,
                                       parameters=parameters, auxiliary=auxiliary))
    # a loop is already running (e.g. pytest-asyncio); run in a worker thread
    import concurrent.futures
    context = copy_context()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(context.run, asyncio.run, run_episode(
            case, scenario, model, profile, parameters=parameters, auxiliary=auxiliary)).result()


def append_result(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
