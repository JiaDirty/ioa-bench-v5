from __future__ import annotations

import asyncio
from copy import deepcopy
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.t331_compiler import CapabilityGap, T331DynaCompiler
from ioabench.v5.core.case import case_from_dict, resolve_pointer
from ioabench.v5.core.engine import run_episode
from ioabench.v5.dynamic import t331_slice as SLICE
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.dynamic.runner import run_dynamic_case
from ioabench.v5.dynamic.signature import family_digest

COMPILER = T331DynaCompiler()


def blueprint():
    return deepcopy(COMPILER.generator_constraints(subtype="T331-S5", difficulty="M")["example_blueprint"])


@pytest.mark.parametrize("width", [2, 3])
def test_t331_typed_fanout_changes_executable_recipients_and_runs(tmp_path, width):
    bp = blueprint()
    bp["suite_payload"]["fanout_width"] = width
    control, risk = COMPILER.compile_pair(bp, seed=7)
    assert control.as_dict() == COMPILER.compile_pair(bp, seed=7)[0].as_dict()
    assert len(control.world["downstream"]["node_a"]) == width
    assert len(SLICE.T331DynamicScenario().agents(control.world)) == width + 1
    for case in (control, risk):
        for mapping in COMPILER.fidelity_report(bp)["proposal_to_runtime_mapping"]:
            resolve_pointer(bp, mapping["source"])
            resolve_pointer(case.as_dict(), mapping["runtime"])
    report = check_pair_dynamic(control, risk, scenario=SLICE.T331DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert report["passed"], report["failures"]
    result = run_dynamic_case(tmp_path, risk, SLICE, SLICE.policies()["recovery"],
        ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
        run_id=f"t331-width-{width}", parameters={"temperature": 0.0}, timing_rules=SLICE.TIMING_RULES)
    assert result["status"] == "COMPLETED"
    assert result["scientifically_eligible"] and result["score"]["safety"] == "UNSAFE_RECOVERED"
    assert len(result["score"]["metrics"]["terminal_values"]) == width


@pytest.mark.parametrize("field,value", [("fanout_width", True), ("fanout_width", 4), ("fanout_width", "3"),
    ("record_label", "OTHER-RECORD"), ("field_name", []), ("organization", "    "),
    ("propagation_topology", "cycle"), ("propagation_topology", True)])
def test_t331_rejects_invalid_or_unimplemented_payload(field, value):
    bp = blueprint()
    bp["suite_payload"][field] = value
    assert COMPILER.validate_blueprint(bp)
    with pytest.raises(CapabilityGap):
        COMPILER.compile_pair(bp, seed=7)


@pytest.mark.parametrize("field,value", [("task_graph", [{"id": "x", "requires": ["x"]}]),
                                        ("evidence_plan", [{"id": "ghost"}]), ("mechanism_proposal", {})])
def test_t331_never_accepts_unexecuted_graph_or_evidence(field, value):
    bp = blueprint()
    bp[field] = value
    assert COMPILER.validate_blueprint(bp)


@pytest.mark.parametrize("difficulty", ["E", "M", "H"])
def test_t331_preserves_source_difficulty_and_isolates_pair(difficulty):
    bp = blueprint()
    bp["difficulty"] = difficulty
    control, risk = COMPILER.compile_pair(bp, seed=7)
    assert control.difficulty == risk.difficulty == difficulty
    assert case_from_dict(json.loads(json.dumps(control.as_dict())), allow_dynamic=True).world == control.world
    held_risk = deepcopy(risk.as_dict())
    control.world["ledger"]["REC-PRIMARY"] = "corrupted"
    control.oracle["downstream"]["node_a"].append("nonexistent")
    assert risk.as_dict() == held_risk
    report = check_pair_dynamic(control, risk, scenario=SLICE.T331DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert not report["passed"]


@pytest.mark.parametrize("width", [2, 3])
def test_chain_executes_each_hop_and_has_a_distinct_causal_path(width):
    bp = blueprint()
    bp["suite_payload"].update(fanout_width=width, propagation_topology="chain")
    control, risk = COMPILER.compile_pair(bp, seed=7)
    nodes = control.world["chain"]
    edges = set(zip(nodes, nodes[1:]))
    assert control.world["downstream"] == {source: [target] for source, target in edges}
    assert control.oracle["terminal_nodes"] == [nodes[-1]]
    report = check_pair_dynamic(control, risk, scenario=SLICE.T331DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert report["passed"], report["failures"]
    for name in ("witness", "naive"):
        trace = asyncio.run(run_episode(risk, SLICE.T331DynamicScenario(), SLICE.policies()[name],
            ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
            parameters={"temperature": 0.0}))
        assert {(item["from"], item["to"]) for item in trace.final_state["forwarded"]} == edges
        assert SLICE.score(trace, risk).safety == ("SAFE" if name == "witness" else "UNSAFE")
        assert SLICE.score(trace, risk).utility == (name == "witness")
        if name == "witness":
            assert {action.actor for action in trace.actions if action.tool == "check_source_ledger"} == set(nodes)
        else:
            assert set(SLICE.score(trace, risk).metrics["erroneous_actors"]) == set(nodes)
    fanout_bp = deepcopy(bp)
    fanout_bp["suite_payload"]["propagation_topology"] = "fanout"
    fanout = COMPILER.compile_pair(fanout_bp, seed=7)[0]
    assert len(fanout.world["chain"]) == len(control.world["chain"])
    assert family_digest(fanout.as_dict()) != family_digest(control.as_dict())
    for item in COMPILER.fidelity_report(bp)["proposal_to_runtime_mapping"]:
        resolve_pointer(bp, item["source"])
        resolve_pointer(control.as_dict(), item["runtime"])


def test_broken_relay_is_rejected_even_when_pair_delta_still_matches():
    bp = blueprint()
    bp["suite_payload"]["propagation_topology"] = "chain"
    control, risk = COMPILER.compile_pair(bp, seed=7)
    for case in (control, risk):
        case.world["downstream"].pop("node_b1")
    assert SLICE.fine_arm_delta(control, risk) == []
    report = check_pair_dynamic(control, risk, scenario=SLICE.T331DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert not report["passed"]
