"""Unified formal construct dispatcher.

A frozen case enters once and is executed by its suite's causal runtime:
frozen case -> dispatcher -> suite runtime -> tested agents -> real synthetic
state -> evaluator-only oracle join -> causal scorer -> replay -> result.

The dispatcher never regenerates cases and never calls the legacy mock
executor; historical replay remains on the legacy path by design.
"""
from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import Any, Mapping

from ioabench.errors import IoABenchError, ProviderPermanentError, ProviderTransientError
from ioabench.hashing import canonical_json_bytes, canonical_sha256

DISPATCH_VERSION = "construct-dispatch-1.0.2"

# Infrastructure failures are the only class that may ever be re-queued, and
# then only when the attempt produced zero valid model behaviour. Anything else
# (construct/contract bugs, programming errors) is a terminal FAILED.
INFRASTRUCTURE_EXCEPTIONS = (ProviderTransientError, ProviderPermanentError, asyncio.CancelledError, TimeoutError,
                             ConnectionError, OSError)

# suite -> (adapter module, adapter function, executor module, executor function)
RUNNERS: dict[str, tuple[str, str, str, str]] = {
    "T311": ("ioabench.runtime.t311_fixture", "build_t311_case_from_skeleton",
             "ioabench.runtime.t311_construct", "execute_t311"),
    "T312": ("ioabench.runtime.discovery_selection", "build_discovery_case_from_skeleton",
             "ioabench.runtime.discovery_selection", "execute_discovery_selection"),
    "T313": ("ioabench.runtime.delegation_provenance", "build_delegation_case_from_skeleton",
             "ioabench.runtime.delegation_provenance", "execute_delegation"),
    "T321": ("ioabench.runtime.protocol_state_machine", "build_protocol_case_from_skeleton",
             "ioabench.runtime.protocol_state_machine", "execute_protocol"),
    "T322": ("ioabench.runtime.protocol_state_machine", "build_protocol_case_from_skeleton",
             "ioabench.runtime.protocol_state_machine", "execute_protocol"),
    "T323": ("ioabench.runtime.delegation_provenance", "build_delegation_case_from_skeleton",
             "ioabench.runtime.delegation_provenance", "execute_delegation"),
    "T331": ("ioabench.runtime.network_propagation", "build_propagation_case_from_skeleton",
             "ioabench.runtime.network_propagation", "execute_propagation"),
    "T332": ("ioabench.runtime.disclosure_inference", "build_disclosure_case_from_skeleton",
             "ioabench.runtime.disclosure_inference", "execute_disclosure"),
    "T333": ("ioabench.runtime.disclosure_inference", "build_disclosure_case_from_skeleton",
             "ioabench.runtime.disclosure_inference", "execute_disclosure"),
    "T341": ("ioabench.runtime.deliberation_norm", "build_deliberation_case_from_skeleton",
             "ioabench.runtime.deliberation_norm", "execute_deliberation"),
    "T342": ("ioabench.runtime.network_propagation", "build_propagation_case_from_skeleton",
             "ioabench.runtime.network_propagation", "execute_propagation"),
    "T343": ("ioabench.runtime.deliberation_norm", "build_deliberation_case_from_skeleton",
             "ioabench.runtime.deliberation_norm", "execute_deliberation"),
    "T351": ("ioabench.runtime.incentive_reputation", "build_incentive_case_from_skeleton",
             "ioabench.runtime.incentive_reputation", "execute_incentive_reputation"),
    "T352": ("ioabench.runtime.incentive_reputation", "build_incentive_case_from_skeleton",
             "ioabench.runtime.incentive_reputation", "execute_incentive_reputation"),
    "T353": ("ioabench.runtime.discovery_selection", "build_discovery_case_from_skeleton",
             "ioabench.runtime.discovery_selection", "execute_discovery_selection"),
    "T361": ("ioabench.runtime.human_agency_simulation", "build_agency_case_from_skeleton",
             "ioabench.runtime.human_agency_simulation", "execute_agency"),
    "T362": ("ioabench.runtime.human_agency_simulation", "build_agency_case_from_skeleton",
             "ioabench.runtime.human_agency_simulation", "execute_agency"),
    "T363": ("ioabench.runtime.human_agency_simulation", "build_agency_case_from_skeleton",
             "ioabench.runtime.human_agency_simulation", "execute_agency"),
}
SIMULATION_SUITES = {"T361", "T362", "T363"}


def frozen_case_to_runtime_input(case: Mapping[str, Any]) -> dict[str, Any]:
    """Present a frozen CandidateCase in the skeleton view the adapters consume.

    The oracle payload is re-encoded exactly as the programmatic ground truth
    it was frozen from; no field is regenerated or recomputed.
    """
    provenance = case.get("provenance", {})
    truth = case["oracle_payload"]
    encoded = truth.get("_content") if isinstance(truth, Mapping) and "_content" in truth else canonical_json_bytes(truth)
    return {"candidate_id": case["candidate_id"], "test_id": case["test_id"],
            "mechanism_id": case.get("mechanism_id"), "world_id": case.get("world_id"),
            "difficulty": case.get("difficulty"), "seed": provenance.get("seed", 1),
            "condition": provenance.get("condition", "RISK"),
            "sut_payload": case["sut_payload"],
            "ground_truth": {"_content": encoded}}


async def execute_construct_case(root: Path, suite: str, case: Mapping[str, Any], model: Any, profile: Any, *, run_id: str,
                                 auxiliary_models: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if suite not in RUNNERS:
        raise ValueError(f"no construct runtime registered for suite {suite}")
    adapter_module, adapter_name, executor_module, executor_name = RUNNERS[suite]
    adapter = getattr(importlib.import_module(adapter_module), adapter_name)
    executor = getattr(importlib.import_module(executor_module), executor_name)
    runtime_case = adapter(frozen_case_to_runtime_input(case))
    if suite in SIMULATION_SUITES:
        result = await executor(root, runtime_case, model, profile, run_id=run_id, auxiliary_models=auxiliary_models)
    else:
        result = await executor(root, runtime_case, model, profile, run_id=run_id)
    result.setdefault("dispatch", {
        "dispatch_version": DISPATCH_VERSION,
        "suite_id": suite,
        "case_id": case["candidate_id"],
        "case_sha256": canonical_sha256(case),
        "runtime_version": result.get("replay", {}).get("scenario", {}).get("manifest", {}).get("runtime_version"),
        "frozen_case_executed_directly": True,
    })
    if suite in SIMULATION_SUITES:
        result["eligibility"] = "SIMULATION_ONLY"
    return result


async def execute_construct_case_strict(root: Path, suite: str, case: Mapping[str, Any], model: Any, profile: Any, *,
                                        run_id: str, auxiliary_models: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Execute one case under the strict retry contract.

    Every execution runs inside an AttemptJournal. If an infrastructure failure
    occurs after at least one valid model record has been produced, the result
    is the terminal INFRA_INTERRUPTED with the partial evidence preserved; if no
    valid behaviour was produced, the result is the resumable
    RETRYABLE_INFRA_FAILURE; non-infrastructure exceptions become terminal
    FAILED. No branch ever re-executes a case that already produced behaviour.

    This is a coroutine because the batch runner already owns an event loop;
    importing a nested ``asyncio.run`` here would fail on Windows.
    """
    from ioabench.runtime.scientific_io import AttemptJournal, attempt_counter

    case_id = str(case["candidate_id"])
    attempt_no = attempt_counter(root, run_id, case_id)
    with AttemptJournal(root, run_id, suite, case_id, attempt_no) as journal:
        try:
            result = await execute_construct_case(root, suite, case, model, profile, run_id=run_id,
                                                  auxiliary_models=auxiliary_models)
        except BaseException as exc:  # noqa: BLE001 - classification is deliberate
            evidence = journal.partial_evidence()
            infrastructure = isinstance(exc, INFRASTRUCTURE_EXCEPTIONS)
            common = {"suite": suite, "case_id": case_id, "run_id": run_id,
                      "error_class": type(exc).__name__, "error_detail": str(exc),
                      "model_records_produced": evidence["model_records_produced"],
                      "valid_model_behavior_observed": evidence["valid_model_behavior_observed"],
                      "attempt_journal": evidence["attempt_journal"],
                      "attempt_no": attempt_no}
            if infrastructure and evidence["valid_model_behavior_observed"]:
                status = "INFRA_INTERRUPTED"
            elif infrastructure:
                status = "RETRYABLE_INFRA_FAILURE"
            else:
                status = "FAILED"
            return {**common, "status": status, "eligibility": status,
                    "infrastructure_failure": infrastructure,
                    "partial_evidence_retained": evidence["model_records_produced"] > 0}
        value = dict(result)
        value.setdefault("infrastructure_failure", False)
        evidence = journal.partial_evidence()
        value["attempt_journal"] = evidence["attempt_journal"]
        value["model_records_produced"] = evidence["model_records_produced"]
        value["valid_model_behavior_observed"] = evidence["valid_model_behavior_observed"]
        value["attempt_no"] = attempt_no
        return value


def execute_construct_case_sync(root: Path, suite: str, case: Mapping[str, Any], model: Any, profile: Any, *, run_id: str,
                                auxiliary_models: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Synchronous facade for callers that are not already inside an event loop."""
    return asyncio.run(execute_construct_case_strict(root, suite, case, model, profile, run_id=run_id,
                                                     auxiliary_models=auxiliary_models))


# Deterministic per-suite baseline models used ONLY for offline dispatcher E2E
# runs; formal campaigns bind the tested model through ModelPort instead.
BASELINES: dict[str, tuple[str, str]] = {
    "T311": ("ioabench.runtime.t311_baselines", "T311Baseline"),
    "T312": ("ioabench.runtime.discovery_selection", "DiscoverySelectionBaseline"),
    "T313": ("ioabench.runtime.delegation_provenance", "DelegationBaseline"),
    "T321": ("ioabench.runtime.protocol_state_machine", "ProtocolBaseline"),
    "T322": ("ioabench.runtime.protocol_state_machine", "ProtocolBaseline"),
    "T323": ("ioabench.runtime.delegation_provenance", "DelegationBaseline"),
    "T331": ("ioabench.runtime.network_propagation", "PropagationBaseline"),
    "T332": ("ioabench.runtime.disclosure_inference", "DisclosureBaseline"),
    "T333": ("ioabench.runtime.disclosure_inference", "DisclosureBaseline"),
    "T341": ("ioabench.runtime.deliberation_norm", "DeliberationBaseline"),
    "T342": ("ioabench.runtime.network_propagation", "PropagationBaseline"),
    "T343": ("ioabench.runtime.deliberation_norm", "DeliberationBaseline"),
    "T351": ("ioabench.runtime.incentive_reputation", "IncentiveReputationBaseline"),
    "T352": ("ioabench.runtime.incentive_reputation", "IncentiveReputationBaseline"),
    "T353": ("ioabench.runtime.discovery_selection", "DiscoverySelectionBaseline"),
    "T361": ("ioabench.runtime.human_agency_simulation", "AgencyBaseline"),
    "T362": ("ioabench.runtime.human_agency_simulation", "AgencyBaseline"),
    "T363": ("ioabench.runtime.human_agency_simulation", "AgencyBaseline"),
}


def resolve_mock_model(suite: str, policy: str = "safe") -> Any:
    if suite not in BASELINES:
        raise ValueError(f"no deterministic baseline registered for suite {suite}")
    module_name, class_name = BASELINES[suite]
    baseline_type = getattr(importlib.import_module(module_name), class_name)
    if suite == "T311":
        return baseline_type({"unsafe": "naive"}.get(policy, policy))
    return baseline_type(policy)
