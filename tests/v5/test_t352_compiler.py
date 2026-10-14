from __future__ import annotations

from copy import deepcopy
import asyncio
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.t352_compiler import CapabilityGap, T352DynaCompiler
from ioabench.v5.core.case import case_from_dict, resolve_pointer
from ioabench.v5.core.engine import run_episode
from ioabench.v5.dynamic import t352_slice as SLICE
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.dynamic.runner import run_dynamic_case

COMPILER = T352DynaCompiler()


def blueprint():
    return deepcopy(COMPILER.generator_constraints(subtype="T352-S1", difficulty="M")["example_blueprint"])


@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("report_access", ["broadcast", "local_receipt_query"])
def test_t352_typed_allocator_count_changes_actual_agents_and_runs(tmp_path, count, report_access):
    bp = blueprint()
    bp["suite_payload"]["allocator_count"] = count
    bp["suite_payload"]["report_access"] = report_access
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
        run_id=f"t352-allocators-{count}-{report_access}", parameters={"temperature": 0.0}, timing_rules=SLICE.TIMING_RULES)
    assert result["status"] == "COMPLETED"
    assert result["scientifically_eligible"] and result["score"]["safety"] == "UNSAFE_RECOVERED"
    assert result["score"]["metrics"]["rounds_allocatable"] == 4


@pytest.mark.parametrize("field,value", [("allocator_count", True), ("allocator_count", 4), ("reputation_rating", True),
    ("reputation_rating", 3), ("reputation_rating", float("nan")),
    ("round_notes", ["one report"]), ("round_notes", [1] * 3), ("round_notes", ["a report"] * 4),
    ("round_count", 6), ("organization", "    "), ("report_access", "secret_network"), ("report_access", True)])
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
