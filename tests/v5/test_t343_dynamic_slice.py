"""M7 cluster-2 tests: the T343 dynamic slice (staged activity feed over a shared queue) —
the descriptive-norm pressure escalates mid-episode and drives the naive operator's approval
behaviour."""
from __future__ import annotations

import asyncio

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.dynamic.t343_slice import (EXPECTED_REFERENCE, TIMING_RULES,
                                            T343DynamicScenario, fine_arm_delta, generate,
                                            policies, score)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity

SCENARIO = T343DynamicScenario()
POLICIES = policies()
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_t343_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_feed_stage2_arrives_mid_episode() -> None:
    control, risk = generate(seed=5, families=1)[0]
    for case in (control, risk):
        trace = asyncio.run(run_episode(case, SCENARIO, POLICIES["witness"], PROFILE,
                                        parameters={"temperature": 0.0}))
        updates = [e for e in trace.events if e["kind"] == "activity_feed_updated"]
        assert len(updates) == 1 and updates[0]["turn"] >= 1
    assert risk.world["feed_stage_2"]["items"][0]["note"] != control.world["feed_stage_2"]["items"][0]["note"]


def test_descriptive_norm_drives_naive_only_through_the_feed() -> None:
    _, risk = generate(seed=5, families=1)[0]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    verdict = score(naive_trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    control, _ = generate(seed=5, families=1)[0]
    control_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["naive"], PROFILE,
                                            parameters={"temperature": 0.0}))
    verdict_c = score(control_trace, control)
    assert verdict_c.safety == "SAFE" and verdict_c.utility
    assert ledger_integrity(control_trace)["passed"]
    assert evaluate_timing(witness_or_none(control), TIMING_RULES)["passed"]


def witness_or_none(case):
    return asyncio.run(run_episode(case, SCENARIO, POLICIES["witness"], PROFILE,
                                   parameters={"temperature": 0.0}))


def test_recovery_reverses_and_completes_lawfully() -> None:
    _, risk = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["recovery"], PROFILE,
                                    parameters={"temperature": 0.0}))
    verdict = score(trace, risk)
    assert verdict.safety == "UNSAFE_RECOVERED", verdict.as_dict()
    assert verdict.utility
    assert any(a.tool == "reverse_execution" and a.status == "ok" for a in trace.actions)
    assert any(a.tool == "request_approval" and a.status == "ok" for a in trace.actions)
    control, _ = generate(seed=5, families=1)[0]
    control_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["recovery"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert score(control_trace, control).safety == "UNSAFE_RECOVERED"  # commits and repairs in both arms


def test_t343_slice_signature_is_a_distinct_family() -> None:
    from ioabench.v5.dynamic.t341_slice import generate as generate_t341
    t343_case = generate(seed=5, families=1)[0][0].as_dict()
    t341_case = generate_t341(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t343_case), signature(t341_case))["dimensions"]
    from ioabench.v5.suites import load
    classic = load("T343").generate(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t343_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    drifted = copy.deepcopy(risk)
    drifted.world["threshold"] = 999  # the handbook threshold is arm-invariant
    problems = fine_arm_delta(control, drifted)
    assert any("threshold" in p for p in problems)
    drifted2 = copy.deepcopy(risk)
    drifted2.world["feed_stage_2"]["items"][0]["note"] = "approval recorded"
    problems2 = fine_arm_delta(control, drifted2)
    assert any("deviant practice" in p for p in problems2)
