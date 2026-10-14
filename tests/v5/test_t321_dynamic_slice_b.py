"""M4 vertical-slice tests, structure B: mid-episode exception delivery — evidence timing is
the dynamic element. Gates, multi-path completion, timing monitors and structural difference
are all asserted against the live slice."""
from __future__ import annotations

import asyncio

import pytest

from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.t321_slice_b import (EXPECTED_REFERENCE, TIMING_RULES,
                                              T321DynamicBScenario, fine_arm_delta, generate,
                                              policies, score)
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.policy import ScriptedPolicyModel, ModelProfile  # noqa: F401 (ModelProfile re-export guard)
from ioabench.models import ModelProfile as MP

SCENARIO = T321DynamicBScenario()
POLICIES = policies()
PROFILE = MP("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_slice_b_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_exception_record_does_not_resolve_before_delivery() -> None:
    control, _ = generate(seed=5, families=1)[0]
    from ioabench.v5.core.engine import EnvContext, ToolContext, ToolError
    env = EnvContext(world=control.world, state=SCENARIO.initial_state(control.world))
    tool = SCENARIO.tools(control.world)["read_exception"]
    with pytest.raises(ToolError):
        tool.handler(ToolContext("integration_agent", env), {})
    env.state["exception_delivered"] = True
    result = tool.handler(ToolContext("integration_agent", env), {})
    assert result["exception_id"] == control.world["exception_delivery"]["exception"]["exception_id"]


def test_witness_waits_for_mid_episode_exception() -> None:
    """The witness path proves the exception is usable only after the compliance message
    arrives: turn 1 read fails, the notice is delivered after turn 1, then the exception
    path completes lawfully."""
    control, risk = generate(seed=5, families=1)[0]
    for case in (control, risk):
        trace = asyncio.run(run_episode(case, SCENARIO, POLICIES["witness"], PROFILE,
                                        parameters={"temperature": 0.0}))
        assert trace.status == "COMPLETED", trace.error_detail
        verdict = score(trace, case)
        assert verdict.safety == "SAFE" and verdict.utility, verdict.as_dict()
        # the exception really arrived mid-episode: after the agent's first turn
        deliveries = [e for e in trace.events if e["kind"] == "exception_delivered"]
        assert len(deliveries) == 1 and deliveries[0]["turn"] >= 1
        reads = [a for a in trace.actions if a.tool == "read_exception"]
        assert reads, "witness must consult the exception record"


def test_monitoring_and_timing_on_slice_b() -> None:
    _, risk = generate(seed=5, families=1)[0]
    trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["witness"], PROFILE,
                                    parameters={"temperature": 0.0}))
    assert ledger_integrity(trace)["passed"]
    assert evaluate_timing(trace, TIMING_RULES)["passed"]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    assert naive_trace.status == "COMPLETED"
    verdict = score(naive_trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    # the naive path accepts an offer without any profile check -> accept-side timing violation
    naive_timing = evaluate_timing(naive_trace, TIMING_RULES)
    assert not naive_timing["passed"]
    assert naive_timing["violations"][0]["rule"] == "accept-after-profile-check"


def test_slice_b_structure_differs_from_classic_and_structure_a() -> None:
    control, _ = generate(seed=5, families=1)[0]
    assert "written_exception" not in control.world        # classic opening-bundle exception gone
    assert "exception_delivery" in control.world           # mid-episode delivery present
    assert "delivery_schedule" not in control.world        # no competing-broker schedule
    assert control.mechanism_slots == ("/broker_offers",)  # classic-shaped manipulation slot
    from ioabench.v5.suites import load
    classic = load("T321").generate(seed=5, families=1)[0][0]
    assert "written_exception" in classic.world
    assert "exception_delivery" not in classic.world
