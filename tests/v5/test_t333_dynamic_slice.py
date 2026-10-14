"""M7 cluster-2 tests: the T333 dynamic slice (staged metadata revelation + mid-episode partner
pressure). Scoring is delegated verbatim to the classic pre-registered T333 scorer — the tests
must therefore show identical abstain/safety semantics with zero drift."""
from __future__ import annotations

import asyncio

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.dynamic.t333_slice import (EXPECTED_REFERENCE, TIMING_RULES,
                                            T333DynamicScenario, fine_arm_delta, generate,
                                            policies, score)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity

SCENARIO = T333DynamicScenario()
POLICIES = policies()
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_t333_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_stage2_pressure_arrives_mid_episode() -> None:
    _, risk = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["witness"], PROFILE,
                                    parameters={"temperature": 0.0}))
    stage2 = [e for e in trace.events if e["kind"] == "stage2_delivered"]
    assert len(stage2) == 1 and stage2[0]["turn"] >= 1
    # the witness reports aggregates only when no shareable disclosure exists
    final_report = trace.final_state["reports"][-1]
    assert final_report["driver"] == "unknown"
    verdict = score(trace, risk)
    assert verdict.safety == "SAFE" and verdict.utility


def test_naive_discloses_only_in_risk_and_recovery_withdraws() -> None:
    _, risk = generate(seed=5, families=1)[0]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    verdict = score(naive_trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    control, _ = generate(seed=5, families=1)[0]
    control_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["naive"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert score(control_trace, control).safety == "SAFE"

    recovery_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["recovery"], PROFILE,
                                             parameters={"temperature": 0.0}))
    verdict_r = score(recovery_trace, risk)
    assert verdict_r.safety == "UNSAFE_RECOVERED", verdict_r.as_dict()
    assert verdict_r.utility
    assert any(a.tool == "amend_report" and a.status == "ok" for a in recovery_trace.actions)


def test_scorer_delegation_preserves_pre_registered_semantics() -> None:
    """The slice's score() must produce the same verdict objects as the classic scorer for the
    same trace/case — no semantics drift through the slice layer."""
    from ioabench.v5.suites import load
    classic = load("T333")
    _, risk = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                    parameters={"temperature": 0.0}))
    slice_score = score(trace, risk)
    classic_score = classic.score(trace, risk)
    assert slice_score.safety == classic_score.safety
    assert slice_score.utility == classic_score.utility
    assert slice_score.abstain == classic_score.abstain
    assert len(slice_score.violations) == len(classic_score.violations)
    assert ledger_integrity(trace)["passed"]
    assert evaluate_timing(trace, TIMING_RULES)["passed"]


def test_t333_slice_signature_is_a_distinct_family() -> None:
    from ioabench.v5.dynamic.t343_slice import generate as generate_t343
    t333_case = generate(seed=5, families=1)[0][0].as_dict()
    t343_case = generate_t343(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t333_case), signature(t343_case))["dimensions"]
    from ioabench.v5.suites import load
    classic = load("T333").generate(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t333_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    drifted = copy.deepcopy(risk)
    drifted.world["metadata"]["aggregates"]["payment_total"] = 1  # aggregates are arm-invariant
    problems = fine_arm_delta(control, drifted)
    assert any("metadata" in p for p in problems)
    drifted2 = copy.deepcopy(risk)
    drifted2.world["client_notice"]["shareable"] = True
    problems2 = fine_arm_delta(control, drifted2)
    assert any("shareable direction" in p for p in problems2)
