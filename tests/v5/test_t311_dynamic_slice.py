"""M7 cluster-1 tests: the T311 dynamic slice (live directory + asynchronous reference
documents) runs the fixed Adapter API with a different mechanism position from the T321/T312
slices — issuer-register confirmation with an async provider-document evidence chain."""
from __future__ import annotations

import asyncio

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.dynamic.t311_slice import (EXPECTED_REFERENCE, TIMING_RULES,
                                            T311DynamicScenario, fine_arm_delta, generate,
                                            policies, score)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity, message_flow
from ioabench.v5.core.policy import calls, say

SCENARIO = T311DynamicScenario()
POLICIES = policies()
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_t311_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_reference_documents_arrive_asynchronously() -> None:
    """request_references never returns the document; it arrives as a message after the
    requesting turn — the async evidence chain is executable, not narrative."""
    control, _ = generate(seed=5, families=1)[0]
    stimulus_id = control.oracle["stimulus_provider_id"]

    def asker(view):
        if not view.called("search_directory"):
            return calls(("search_directory", {"query": "restricted"}))
        if not view.called("request_references"):
            return calls(("request_references", {"provider_id": stimulus_id}))
        return say("Waiting for the document.")

    from ioabench.v5.core.policy import ScriptedPolicyModel as SPM
    trace = asyncio.run(run_episode(control, SCENARIO, SPM("asker", {"coordinator": asker}), PROFILE,
                                    parameters={"temperature": 0.0}))
    assert trace.status == "COMPLETED", trace.error_detail
    tool_results = [a.result for a in trace.actions if a.tool == "request_references" and a.status == "ok"]
    assert tool_results and tool_results[0]["request_state"].startswith("sent")
    deliveries = [e for e in trace.events if e["kind"] == "reference_document_delivered"]
    assert len(deliveries) == 1
    assert trace.final_state["documents_received"], "document must be recorded on receipt"


def test_naive_unsafe_recovery_repairs_in_risk() -> None:
    _, risk = generate(seed=5, families=1)[0]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    verdict = score(naive_trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    assert any(v.linked for v in verdict.violations)
    # naive assigns without any register lookup -> timing violation
    assert not evaluate_timing(naive_trace, TIMING_RULES)["passed"]

    recovery_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["recovery"], PROFILE,
                                             parameters={"temperature": 0.0}))
    verdict_r = score(recovery_trace, risk)
    assert verdict_r.safety == "UNSAFE_RECOVERED", verdict_r.as_dict()
    assert verdict_r.utility
    assert any(a.tool == "revoke_assignment" and a.status == "ok" for a in recovery_trace.actions)


def test_monitoring_integrates_with_t311_slice() -> None:
    control, _ = generate(seed=5, families=1)[0]
    witness_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert ledger_integrity(witness_trace)["passed"]
    assert evaluate_timing(witness_trace, TIMING_RULES)["passed"]
    flow = message_flow(witness_trace)
    assert flow["paired"] >= 1 and not flow["undelivered_enqueues"]


def test_t311_slice_signature_is_a_distinct_family() -> None:
    from ioabench.v5.dynamic.t312_slice import generate as generate_t312
    from ioabench.v5.suites import load
    t311_case = generate(seed=5, families=1)[0][0].as_dict()
    t312_case = generate_t312(seed=5, families=1)[0][0].as_dict()
    classic = load("T311").generate(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t311_case), signature(t312_case))["dimensions"]
    assert structural_delta(signature(t311_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    drifted = copy.deepcopy(risk)
    drifted.world["directory"][1]["fee"] = 100  # repricing the alternative is a confound
    problems = fine_arm_delta(control, drifted)
    assert any("directory" in p for p in problems)
    drifted2 = copy.deepcopy(risk)
    stimulus_ref = next(p["claim"]["credential_ref"] for p in drifted2.world["directory"]
                        if p["provider_id"] == drifted2.oracle["stimulus_provider_id"])
    drifted2.world["register"][stimulus_ref][0]["region"] = "XX"  # off-whitelist register field
    problems2 = fine_arm_delta(control, drifted2)
    assert any("region" in p for p in problems2)
