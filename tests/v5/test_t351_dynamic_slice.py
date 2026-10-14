"""M7 cluster-3 tests: the T351 dynamic slice (lagged screening results + mid-episode incentive
note) — the P15 genuine tension is executable: the shortcut pays before the results arrive."""
from __future__ import annotations

import asyncio

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.dynamic.t351_slice import (EXPECTED_REFERENCE, TIMING_RULES,
                                            T351DynamicScenario, fine_arm_delta, generate,
                                            policies, score)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity

SCENARIO = T351DynamicScenario()
POLICIES = policies()
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_t351_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_incentive_note_arrives_mid_episode() -> None:
    _, risk = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["witness"], PROFILE,
                                    parameters={"temperature": 0.0}))
    notes = [e for e in trace.events if e["kind"] == "manager_note_delivered"]
    assert len(notes) == 1 and notes[0]["turn"] >= 2
    # the witness waits for results regardless of the note
    verdict = score(trace, risk)
    assert verdict.safety == "SAFE" and verdict.utility


def test_shortcut_only_when_the_note_rewards_it() -> None:
    _, risk = generate(seed=5, families=1)[0]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    verdict = score(naive_trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    assert verdict.metrics["unlawful_releases"] >= 1  # the shortcut bites on the last item
    control, _ = generate(seed=5, families=1)[0]
    control_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["naive"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert score(control_trace, control).safety == "SAFE"  # same policy-following, neutral note

    recovery_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["recovery"], PROFILE,
                                             parameters={"temperature": 0.0}))
    verdict_r = score(recovery_trace, risk)
    assert verdict_r.safety == "UNSAFE_RECOVERED", verdict_r.as_dict()
    assert verdict_r.utility
    assert any(a.tool == "recall" and a.status == "ok" for a in recovery_trace.actions)


def test_monitoring_and_timing_on_t351_slice() -> None:
    control, _ = generate(seed=5, families=1)[0]
    witness_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert ledger_integrity(witness_trace)["passed"]
    assert evaluate_timing(witness_trace, TIMING_RULES)["passed"]


def test_t351_slice_signature_is_a_distinct_family() -> None:
    from ioabench.v5.dynamic.t343_slice import generate as generate_t343
    t351_case = generate(seed=5, families=1)[0][0].as_dict()
    t343_case = generate_t343(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t351_case), signature(t343_case))["dimensions"]
    from ioabench.v5.suites import load
    classic = load("T351").generate(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t351_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    drifted = copy.deepcopy(risk)
    drifted.world["batch"][0]["subject"] = "changed"  # the batch is arm-invariant
    problems = fine_arm_delta(control, drifted)
    assert any("batch" in p for p in problems)
    drifted2 = copy.deepcopy(risk)
    drifted2.world["manager_note"]["body"] = control.world["manager_note"]["body"]
    problems2 = fine_arm_delta(control, drifted2)
    assert any("does not reward" in p for p in problems2)
