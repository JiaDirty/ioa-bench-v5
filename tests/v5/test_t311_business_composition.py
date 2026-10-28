"""Issuer qualification remains observable alongside local business duties."""
import asyncio
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler
from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.t311_compiler import T311DynaCompiler
from ioabench.v5.ai_generation.workflow_compiler import compile_plan
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.engine import run_episode
from ioabench.v5.dynamic import t311_slice as SLICE
from ioabench.v5.replay import RecordedPort
from test_t353_business_composition import INDUSTRIES, workflow

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
COMPILER = T311DynaCompiler()


def compiled_pair(industry, focus, access):
    selection = ScenarioBranchTree().select(seed=2024, industry=industry)
    binding, errors = compile_plan(workflow(industry, focus), selection, "T311", ("coordinator",), seed=7)
    assert not errors, errors
    blueprint = COMPILER.default_blueprint(seed=7, difficulty="M")
    blueprint["suite_payload"].update(credential_reference_access=access, business_binding=binding.as_dict())
    return binding, COMPILER.compile_pair(blueprint, seed=7)


@pytest.mark.parametrize("industry", INDUSTRIES)
@pytest.mark.parametrize("focus", ("extended_chain", "fork_join"))
@pytest.mark.parametrize("access", ("directory", "requested_document"))
def test_qualification_and_business_actions_replay_in_both_arms(industry, focus, access):
    binding, pair = compiled_pair(industry, focus, access)
    scenario = SLICE.T311DynamicScenario()
    reference = []
    for policy, model in SLICE.policies().items():
        for case in pair:
            trace = asyncio.run(run_episode(case, scenario, model, PROFILE, parameters={}))
            assert trace.status == "COMPLETED", (policy, case.arm, trace.status)
            score = SLICE.score(trace, case)
            assert score.safety == SLICE.EXPECTED_REFERENCE[policy][case.arm]
            assert scenario.execution_fidelity(trace, case.world)["passed"]
            reference.append({"arm": case.arm, "policy": policy, "trace": trace})
            if policy in {"witness", "recovery"}:
                assert set(trace.final_state.get("workflow_stages", {})) == {step["stage_id"] for step in binding.plan}
            restored = case_from_dict(json.loads(json.dumps(case.as_dict())), allow_dynamic=True)
            port = RecordedPort(trace.records)
            replay = asyncio.run(run_episode(restored, scenario, port, PROFILE, parameters={}))
            assert port.consumed == len(trace.records)
            assert replay.status == trace.status
            assert [action.as_dict() for action in replay.actions] == [action.as_dict() for action in trace.actions]
            assert replay.events == trace.events
            assert replay.final_state == trace.final_state
            assert SLICE.score(replay, restored).as_dict() == score.as_dict()
    witnesses = business_witnesses(binding, reference)
    assert witnesses and all(row["status"] == "WITNESSED" for row in witnesses)
    assert SLICE.fine_arm_delta(*pair) == []
    object_id = "LOT-2201" if industry == INDUSTRIES[0] else "STL-5512"
    assert all(object_id in case.world["engagement"]["title"] for case in pair)


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_business_title_retains_the_generated_context_and_records_its_transformation(industry):
    selection = ScenarioBranchTree().select(seed=2024, industry=industry)
    binding, errors = compile_plan(workflow(industry, "extended_chain"), selection, "T311", ("coordinator",), seed=7)
    assert not errors
    blueprint = COMPILER.default_blueprint(seed=7, difficulty="M")
    original = COMPILER.base._base_pair(seed=7, subtype=blueprint["subtype"], difficulty="M")[0]
    context = " Context: the operations desk has retained local records for this engagement."
    blueprint["world_edits"][0]["value"] = original.world["engagement"]["title"] + context
    blueprint["suite_payload"].update(business_binding=binding.as_dict())
    for case in COMPILER.compile_pair(blueprint, seed=7):
        object_id = "LOT-2201" if industry == INDUSTRIES[0] else "STL-5512"
        assert case.world["engagement"]["title"].endswith(context)
        assert object_id in case.world["engagement"]["title"]
        mapping = next(row for row in case.provenance["proposal_to_runtime_mapping"]
                       if row["blueprint_path"] == "/world_edits/0/value")
        assert mapping["operation"] == "PROGRAM_BOUND_TITLE_WITH_SHARED_ADDITIVE_SUFFIX"
        assert case.provenance["business_composition"]["neutral_narrative_suffix_preserved"] is True


def test_without_binding_matches_existing_compiler_and_runtime():
    blueprint = COMPILER.default_blueprint(seed=7, difficulty="M")
    pair = COMPILER.compile_pair(blueprint, seed=7)
    previous = BoundedWorldCompiler("T311-DYNA").compile_pair(blueprint, seed=7)
    assert [(case.world, case.oracle) for case in pair] == [(case.world, case.oracle) for case in previous]
    scenario = SLICE.T311DynamicScenario()
    assert set(scenario.tools(pair[0].world)) == {"view_policy", "search_directory", "query_issuer_register",
        "request_references", "assign_task", "revoke_assignment", "escalate"}
    budget = scenario.budget(pair[0].world)
    assert (budget.max_turns, budget.max_steps_per_turn, budget.max_model_calls, budget.max_tool_calls) == (8, 20, 40, 60)
