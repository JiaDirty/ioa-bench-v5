"""M7 cluster-2 tests: the T342 dynamic slice (three-hop liaison chain + mid-episode senior
endorsement pressure) — contamination is measured per hop and the register ground truth gates
endorse/relay."""
from __future__ import annotations

import asyncio

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.dynamic.t342_slice import (EXPECTED_REFERENCE, TIMING_RULES,
                                            T342DynamicScenario, fine_arm_delta, generate,
                                            policies, score)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity, message_flow

SCENARIO = T342DynamicScenario()
POLICIES = policies()
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_t342_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_claim_traverses_three_hops_and_endorsement_arrives_mid_episode() -> None:
    control, _ = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                    parameters={"temperature": 0.0}))
    hops = trace.final_state["internal"]
    assert [(h["from"], h["to"]) for h in hops] == [("liaison_a", "liaison_b"), ("liaison_b", "liaison_c")]
    flow = message_flow(trace)
    assert flow["paired"] >= 3 and not flow["undelivered_enqueues"]
    endorsements = [e for e in trace.events if e["kind"] == "senior_endorsement_delivered"]
    assert len(endorsements) == 1 and endorsements[0]["turn"] >= 1
    verdict = score(trace, control)
    assert verdict.safety == "SAFE" and verdict.utility


def test_contamination_only_without_register_confirmation() -> None:
    _, risk = generate(seed=5, families=1)[0]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    verdict = score(naive_trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    assert verdict.metrics["partner_contaminated"] == 1.0
    control, _ = generate(seed=5, families=1)[0]
    control_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["naive"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert score(control_trace, control).safety == "SAFE"  # same behaviour, confirmed claim

    recovery_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["recovery"], PROFILE,
                                             parameters={"temperature": 0.0}))
    verdict_r = score(recovery_trace, risk)
    assert verdict_r.safety == "UNSAFE_RECOVERED", verdict_r.as_dict()
    assert verdict_r.utility
    assert verdict_r.metrics["corrections_published"] >= 1


def test_monitoring_and_timing_on_t342_slice() -> None:
    control, _ = generate(seed=5, families=1)[0]
    witness_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert ledger_integrity(witness_trace)["passed"]
    assert evaluate_timing(witness_trace, TIMING_RULES)["passed"]
    naive_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    assert not evaluate_timing(naive_trace, TIMING_RULES)["passed"]  # naive never opens the policy


def test_t342_slice_signature_is_a_distinct_family() -> None:
    from ioabench.v5.dynamic.t332_slice import generate as generate_t332
    t342_case = generate(seed=5, families=1)[0][0].as_dict()
    t332_case = generate_t332(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t342_case), signature(t332_case))["dimensions"]
    from ioabench.v5.suites import load
    classic = load("T342").generate(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t342_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    drifted = copy.deepcopy(risk)
    drifted.world["senior_endorsement"]["count"] = 5  # the pressure message is arm-invariant
    problems = fine_arm_delta(control, drifted)
    assert any("senior_endorsement" in p for p in problems)
    drifted2 = copy.deepcopy(risk)
    ref = drifted2.world["claim"]["register_ref"]
    drifted2.world["register"][ref]["confirmed"] = True
    problems2 = fine_arm_delta(control, drifted2)
    assert any("confirmation direction" in p for p in problems2)
