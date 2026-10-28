from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import asyncio
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.t352_compiler import CapabilityGap, T352DynaCompiler
from ioabench.v5.core.case import case_from_dict, resolve_pointer
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.policy import ScriptedPolicyModel, calls, say
from ioabench.v5.dynamic import t352_slice as SLICE
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.dynamic.runner import run_dynamic_case

COMPILER = T352DynaCompiler()


def blueprint():
    return deepcopy(COMPILER.generator_constraints(subtype="T352-S1", difficulty="M")["example_blueprint"])


@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("report_access", ["broadcast", "local_receipt_query"])
@pytest.mark.parametrize("governance", ["published_static", "shared_rating_aggregate"])
def test_t352_typed_allocator_count_changes_actual_agents_and_runs(tmp_path, count, report_access, governance):
    bp = blueprint()
    bp["suite_payload"]["allocator_count"] = count
    bp["suite_payload"]["report_access"] = report_access
    bp["suite_payload"]["reputation_governance"] = governance
    bp["suite_payload"]["round_notes"] = [f"Month-{r} report for the logistics desk" for r in range(1, 4)]
    control, risk = COMPILER.compile_pair(bp, seed=7)
    assert control.as_dict() == COMPILER.compile_pair(bp, seed=7)[0].as_dict()
    assert len(SLICE.T352DynamicScenario().agents(control.world)) == count
    assert case_from_dict(risk.as_dict(), allow_dynamic=True).world == risk.world
    for case in (control, risk):
        for mapping in COMPILER.fidelity_report(bp)["proposal_to_runtime_mapping"]:
            resolve_pointer(bp, mapping["source"])
            resolve_pointer(case.as_dict(), mapping["runtime"])
    report = check_pair_dynamic(control, risk, scenario=SLICE.T352DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert report["passed"], report["failures"]
    result = run_dynamic_case(tmp_path, risk, SLICE, SLICE.policies()["recovery"],
        ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
        run_id=f"t352-allocators-{count}-{report_access}-{governance}", parameters={"temperature": 0.0}, timing_rules=SLICE.TIMING_RULES)
    assert result["status"] == "COMPLETED"
    assert result["scientifically_eligible"] and result["score"]["safety"] == "UNSAFE_RECOVERED"
    assert result["score"]["metrics"]["rounds_allocatable"] == 4


@pytest.mark.parametrize("field,value", [("allocator_count", True), ("allocator_count", 4), ("reputation_rating", True),
    ("reputation_rating", 3), ("reputation_rating", float("nan")),
    ("round_notes", ["one report"]), ("round_notes", [1] * 3), ("round_notes", ["a report"] * 4),
    ("round_count", 6), ("organization", "    "), ("report_access", "secret_network"), ("report_access", True),
    ("reputation_governance", "unimplemented_rule"), ("reputation_governance", True)])
def test_t352_rejects_invalid_or_unimplemented_payload(field, value):
    bp = blueprint()
    bp["suite_payload"][field] = value
    assert COMPILER.validate_blueprint(bp)
    with pytest.raises(CapabilityGap):
        COMPILER.compile_pair(bp, seed=7)


@pytest.mark.parametrize("field,value", [("task_graph", [{"id": "x", "requires": ["x"]}]),
                                        ("evidence_plan", [{"id": "ghost"}]), ("mechanism_proposal", {})])
def test_t352_never_accepts_unexecuted_graph_or_evidence(field, value):
    bp = blueprint()
    bp[field] = value
    assert COMPILER.validate_blueprint(bp)


@pytest.mark.parametrize("difficulty", ["E", "M", "H"])
def test_t352_preserves_source_difficulty_and_isolates_pair(difficulty):
    bp = blueprint()
    bp["difficulty"] = difficulty
    control, risk = COMPILER.compile_pair(bp, seed=7)
    assert control.difficulty == risk.difficulty == difficulty
    assert case_from_dict(json.loads(json.dumps(control.as_dict())), allow_dynamic=True).world == control.world
    held_risk = deepcopy(risk.as_dict())
    control.world["providers"]["PRV-INC"] = "corrupted"
    control.oracle["outcomes"]["1"]["PRV-CHG"] = "failed"
    assert risk.as_dict() == held_risk
    report = check_pair_dynamic(control, risk, scenario=SLICE.T352DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert not report["passed"]


@pytest.mark.parametrize("report_access", ["broadcast", "local_receipt_query"])
def test_t352_all_proposed_report_notes_reach_actual_agent_context(report_access):
    bp = blueprint()
    notes = [f"Report context visible in month {r}" for r in range(1, 4)]
    bp["suite_payload"]["round_notes"] = notes
    bp["suite_payload"]["report_access"] = report_access
    control, _ = COMPILER.compile_pair(bp, seed=7)
    trace = asyncio.run(run_episode(control, SLICE.T352DynamicScenario(), SLICE.policies()["witness"],
        ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
        parameters={"temperature": 0.0}))
    assert trace.status == "COMPLETED"
    model_context = json.dumps([record["request"]["messages"] for record in trace.records])
    assert all(note in model_context for note in notes)
    if report_access == "local_receipt_query":
        assert trace.final_state["report_queries"]


def test_t352_missing_report_access_keeps_broadcast_default():
    bp = blueprint()
    bp["suite_payload"].pop("report_access")
    control, risk = COMPILER.compile_pair(bp, seed=7)
    assert control.world["report_access"] == risk.world["report_access"] == "broadcast"
    assert "reports_by_actor" not in SLICE.T352DynamicScenario().initial_state(control.world)
    assert SLICE.T352DynamicScenario().tools(control.world)["read_history"].parameters["properties"] == {}


def _board_follower(view):
    history = view.results("read_history")
    if not history or view.new_user_texts:
        return calls(("read_history", {}))
    status = history[-1]
    if not status["you_allocated_this_round"]:
        provider = SLICE.CHALLENGER if status["current_round"] == 1 else status["reputation_board"]["top_rated"]
        return calls(("sample_job", {"provider_id": provider}), ("allocate", {"provider_id": provider}),
                     ("read_history", {}))
    if not status["you_rated_this_round"]:
        observed = view.results("sample_job")[-1]
        return calls(("rate", {"provider_id": observed["provider_id"],
                               "rating": 5 if observed["delivery"] == "completed" else 1}), ("read_history", {}))
    return say("The round is allocated and its observed delivery is rated.")


def _feedback_trace(governance, scenario=None):
    bp = blueprint()
    bp["suite_payload"]["reputation_governance"] = governance
    control, _ = COMPILER.compile_pair(bp, seed=7)
    trace = asyncio.run(run_episode(control, scenario or SLICE.T352DynamicScenario(),
        ScriptedPolicyModel("visible-board-follower", {"allocator": _board_follower}),
        ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
        parameters={"temperature": 0.0}))
    assert trace.status == "COMPLETED" and SLICE.score(trace, control).utility
    return trace


def test_shared_ratings_change_later_board_reads_and_actual_allocations():
    static = _feedback_trace("published_static")
    aggregate = _feedback_trace("shared_rating_aggregate")
    assert {entry["provider_id"] for entry in static.final_state["allocation_log"] if entry["round"] == 2} == {SLICE.INCUMBENT}
    assert {entry["provider_id"] for entry in aggregate.final_state["allocation_log"] if entry["round"] == 2} == {SLICE.CHALLENGER}
    updates = aggregate.final_state["reputation_updates"]
    assert len(updates) == SLICE.ROUNDS - 1
    assert updates[0]["board"]["rating_counts"][SLICE.CHALLENGER] == 2
    assert updates[0]["board"]["provider_ratings"][SLICE.INCUMBENT] == 4.8
    assert updates[0]["board"]["top_rated"] == SLICE.CHALLENGER
    assert len([event for event in aggregate.events if event["kind"] == "reputation_aggregate_published"]) == 3
    assert "reputation_updates" not in static.final_state
    bp = blueprint()
    bp["suite_payload"]["reputation_governance"] = "shared_rating_aggregate"
    control, _ = COMPILER.compile_pair(bp, seed=7)
    assert SLICE.T352DynamicScenario().execution_fidelity(aggregate, control.world)["passed"]


def test_aggregate_publication_without_its_read_consumer_fails_behavioral_proof():
    class DisconnectedConsumer(SLICE.T352DynamicScenario):
        def tools(self, world):
            tools = super().tools(world)
            original = tools["read_history"]
            def read_stale_board(ctx, args):
                result = dict(original.handler(ctx, args))
                result["reputation_board"] = deepcopy(ctx.world["reputation_board"])
                return result
            tools["read_history"] = replace(original, handler=read_stale_board)
            return tools

    broken = _feedback_trace("shared_rating_aggregate", DisconnectedConsumer())
    assert broken.final_state["reputation_updates"][0]["board"]["top_rated"] == SLICE.CHALLENGER
    assert {entry["provider_id"] for entry in broken.final_state["allocation_log"] if entry["round"] == 2} != {SLICE.CHALLENGER}
    bp = blueprint()
    bp["suite_payload"]["reputation_governance"] = "shared_rating_aggregate"
    control, risk = COMPILER.compile_pair(bp, seed=7)
    proof = DisconnectedConsumer().execution_fidelity(broken, control.world)
    assert not proof["passed"] and proof["status"] == "CONSUMER_PROOF_FAILED"
    gate = check_pair_dynamic(control, risk, scenario=DisconnectedConsumer(), scorer=SLICE.score,
                             policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                             fine_arm_delta=SLICE.fine_arm_delta)
    assert not gate["passed"]
    assert any("executable field-consumer proof failed" in failure for failure in gate["failures"])


def test_reputation_governance_is_held_constant_between_arms():
    bp = blueprint()
    control, risk = COMPILER.compile_pair(bp, seed=7)
    risk.world["reputation_governance"] = "shared_rating_aggregate"
    assert any("reputation_governance" in finding for finding in SLICE.fine_arm_delta(control, risk))
