"""Screening incentives and a concrete business batch share one executable context."""
import asyncio
from copy import deepcopy
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler
from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.t351_compiler import T351DynaCompiler, screening_witness
from ioabench.v5.ai_generation.workflow_compiler import compile_plan
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.engine import run_episode
from ioabench.v5.dynamic import t351_slice as SLICE
from ioabench.v5.replay import RecordedPort
from test_t353_business_composition import workflow

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
COMPILER = T351DynaCompiler()
INDUSTRIES = ("industry.medicine_supply", "industry.payment_clearing")


def compiled_pair(industry, focus, access):
    selection = ScenarioBranchTree().select(seed=2024, industry=industry)
    binding, errors = compile_plan(workflow(industry, focus), selection, "T351", ("operator",), seed=7)
    assert not errors, errors
    blueprint = COMPILER.default_blueprint(seed=7, difficulty="M")
    blueprint["suite_payload"].update(screening_publication=access, business_binding=binding.as_dict())
    return binding, COMPILER.compile_pair(blueprint, seed=7)


@pytest.mark.parametrize("industry", INDUSTRIES)
@pytest.mark.parametrize("focus", ("extended_chain", "fork_join"))
@pytest.mark.parametrize("access", ("automatic_push", "queued_history_reply"))
def test_t351_business_execution_keeps_incentive_and_screening(industry, focus, access):
    binding, pair = compiled_pair(industry, focus, access)
    scenario = SLICE.T351DynamicScenario()
    reference = []
    key, value = ("lot_id", "LOT-2201") if industry == INDUSTRIES[0] else ("settlement_id", "STL-5512")
    for policy, model in SLICE.policies().items():
        for case in pair:
            trace = asyncio.run(run_episode(case, scenario, model, PROFILE, parameters={}))
            assert trace.status == "COMPLETED", trace.status
            score = SLICE.score(trace, case)
            assert score.safety == SLICE.EXPECTED_REFERENCE[policy][case.arm]
            assert scenario.execution_fidelity(trace, case.world)["passed"]
            assert screening_witness({"policy": policy, "world": case.world, "trace": trace}) is (True if policy == "witness" else None)
            assert all(item[key] == value for item in case.world["batch"])
            assert all(action.arguments["item_id"] in {item["item_id"] for item in case.world["batch"]}
                       for action in trace.actions if action.tool in {"request_check", "release"})
            reference.append({"arm": case.arm, "policy": policy, "trace": trace})
            stages = set(trace.final_state.get("workflow_stages", {}))
            if policy == "naive":
                assert not stages
            else:
                assert stages == {step["stage_id"] for step in binding.plan}
            restored = case_from_dict(json.loads(json.dumps(case.as_dict(), sort_keys=True)), allow_dynamic=True)
            port = RecordedPort(trace.records)
            replay = asyncio.run(run_episode(restored, scenario, port, PROFILE, parameters={}))
            assert port.consumed == len(trace.records)
            assert replay.final_state == trace.final_state
            assert SLICE.score(replay, restored).as_dict() == score.as_dict()
    witnesses = business_witnesses(binding, reference)
    assert witnesses and all(row["status"] == "WITNESSED" for row in witnesses), witnesses
    assert SLICE.fine_arm_delta(*pair) == []


def test_t351_business_binding_is_held_constant():
    _, pair = compiled_pair(INDUSTRIES[0], "extended_chain", "automatic_push")
    changed = deepcopy(pair[1])
    changed.world["business_binding"]["root"] = INDUSTRIES[1]
    assert any("business_binding" in error for error in SLICE.fine_arm_delta(pair[0], changed))


def test_t351_screening_witness_rejects_missing_observed_receipt():
    _, pair = compiled_pair(INDUSTRIES[0], "extended_chain", "queued_history_reply")
    case = pair[0]
    trace = asyncio.run(run_episode(case, SLICE.T351DynamicScenario(), SLICE.policies()["witness"], PROFILE, parameters={}))
    release = next(action for action in trace.actions if action.tool == "release")
    record = next(record for record in trace.records if any(call["function"]["name"] == "release"
                  and json.loads(call["function"]["arguments"])["item_id"] == release.arguments["item_id"]
                  for call in record["response"].get("tool_calls", [])))
    record["request"]["messages"] = [message for message in record["request"]["messages"]
                                      if message.get("role") != "tool"]
    assert screening_witness({"policy": "witness", "world": case.world, "trace": trace}) is False


def test_t351_without_binding_preserves_original_compilation_and_budget():
    blueprint = COMPILER.default_blueprint(seed=7, difficulty="M")
    pair = COMPILER.compile_pair(blueprint, seed=7)
    original = BoundedWorldCompiler("T351-DYNA").compile_pair(blueprint, seed=7)
    assert [(case.world, case.oracle) for case in pair] == [(case.world, case.oracle) for case in original]
    scenario = SLICE.T351DynamicScenario()
    assert set(scenario.tools(pair[0].world)) == {"view_policy", "request_check", "lookup_check_history",
                                                "release", "place_on_hold", "recall", "send_note"}
    budget = scenario.budget(pair[0].world)
    assert (budget.max_turns, budget.max_steps_per_turn, budget.max_model_calls, budget.max_tool_calls) == (12, 10, 40, 60)
