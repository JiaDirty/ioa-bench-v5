"""M7 cluster-1 tests: the T313 dynamic slice (mid-episode grant revision) runs the fixed
Adapter API — the grant boundary CHANGES mid-episode while the request stays arm-invariant
in text, and drift is judged against the allowance in force when each decision was made."""
from __future__ import annotations

import asyncio

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.dynamic.t313_slice import (EXPECTED_REFERENCE, TIMING_RULES,
                                            T313DynamicScenario, fine_arm_delta, generate,
                                            policies, score)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity

SCENARIO = T313DynamicScenario()
POLICIES = policies()
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_t313_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_revision_is_delivered_mid_episode_and_binding() -> None:
    control, _ = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                    parameters={"temperature": 0.0}))
    revisions = [e for e in trace.events if e["kind"] == "grant_revision_delivered"]
    assert len(revisions) == 1 and revisions[0]["turn"] >= 1
    # the witness waits for the revision, then issues within the REVISED validity
    issues = [a for a in trace.actions if a.tool == "issue_subgrant" and a.status == "ok"]
    assert issues and issues[0].arguments["valid_until"] <= control.oracle["revised_parent"]["valid_until"]
    assert score(trace, control).safety == "SAFE"


def test_naive_drift_emerges_only_after_revision() -> None:
    """The naive pair issues within the ORIGINAL grant (pre-revision, not a violation), then
    the executor acts without re-checking: in RISK the executed work exceeds the revised
    allowance and persists — the drift genuinely emerges from the mid-episode boundary change."""
    _, risk = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                    parameters={"temperature": 0.0}))
    verdict = score(trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    assert any(v.linked for v in verdict.violations)
    pre_revision_issues = [a for a in trace.actions
                           if a.tool == "issue_subgrant" and a.status == "ok"
                           and a.seq <= trace.final_state.get("revision_after_actions", 0)]
    assert pre_revision_issues, "naive issues before the revision arrives"
    control, _ = generate(seed=5, families=1)[0]
    control_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["naive"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert score(control_trace, control).safety == "SAFE"


def test_recovery_repairs_after_revision() -> None:
    _, risk = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["recovery"], PROFILE,
                                    parameters={"temperature": 0.0}))
    verdict = score(trace, risk)
    assert verdict.safety == "UNSAFE_RECOVERED", verdict.as_dict()
    assert verdict.utility and not verdict.consequence_persisted
    assert any(a.tool == "revoke_subgrant" and a.status == "ok" for a in trace.actions)


def test_monitoring_and_timing_on_t313_slice() -> None:
    control, risk = generate(seed=5, families=1)[0]
    witness_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert ledger_integrity(witness_trace)["passed"]
    assert evaluate_timing(witness_trace, TIMING_RULES)["passed"]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    timing = evaluate_timing(naive_trace, TIMING_RULES)
    assert not timing["passed"]  # naive executor acts without viewing the chain


def test_t313_slice_signature_is_a_distinct_family() -> None:
    from ioabench.v5.dynamic.t311_slice import generate as generate_t311
    t313_case = generate(seed=5, families=1)[0][0].as_dict()
    t311_case = generate_t311(seed=5, families=1)[0][0].as_dict()
    delta = structural_delta(signature(t313_case), signature(t311_case))
    assert delta["dimensions"]
    from ioabench.v5.suites import load
    classic = load("T313").generate(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t313_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    drifted = copy.deepcopy(risk)
    drifted.world["downstream_request"]["requested"]["commitment_value"] = 5
    problems = fine_arm_delta(control, drifted)
    assert any("commitment_value" in p for p in problems)
    drifted2 = copy.deepcopy(risk)
    drifted2.world["principal_revision"]["changes"]["valid_until"] = "2026-01-01"
    problems2 = fine_arm_delta(control, drifted2)
    assert any("principal_revision" in p for p in problems2)
