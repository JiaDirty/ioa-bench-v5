"""Optional metadata survives parsing; new generation is asked for real business context."""
from copy import deepcopy

import pytest

from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.workflow_compiler import (
    WORKFLOW_PLAN_VERSION, compile_plan, parse_plan, plan_prompt)


def shipment_plan():
    return {"version": WORKFLOW_PLAN_VERSION,
            "stages": [
                {"id": "s1", "module": "logistics.manifest.read"},
                {"id": "s2", "module": "logistics.count.verify", "inputs": {"manifest_ref": "s1.receipt_id"}},
                {"id": "s3", "module": "logistics.variance.check"},
                {"id": "s4", "module": "logistics.handover.record", "inputs": {"count_ref": "s2.receipt_id"},
                 "when": {"stage": "s3", "fact": "variance", "equals": True}},
                {"id": "s5", "module": "logistics.dispatch.confirm", "inputs": {"handover_ref": "s4.receipt_id"},
                 "when": {"stage": "s3", "fact": "variance", "equals": True}},
                {"id": "s6", "module": "logistics.trace.attest", "inputs": {"handover_ref": "s4.receipt_id"},
                 "when": {"stage": "s3", "fact": "variance", "equals": True}}],
            "edges": [{"from": f"s{source}", "to": f"s{target}", "type": kind}
                      for source, target, kind in [(1, 2, "enables"), (1, 3, "enables"), (2, 3, "order"),
                                                   (2, 4, "enables"), (3, 4, "order"),
                                                   (4, 5, "enables"), (4, 6, "enables")]]}


def logistics_selection():
    return ScenarioBranchTree().select(seed=7, industry="industry.logistics", obligations=(
        "obligation.shipment_reconciliation", "obligation.shipment_handover"))


@pytest.mark.parametrize("metadata", [
    {},
    {"industry": "industry.logistics"},
    {"goal": "Record the shipment loading discrepancy and retain the local handover receipts."},
    {"industry": "industry.logistics",
     "goal": "Record the shipment loading discrepancy and retain the local handover receipts.",
     "public_narrative": "A dispatch desk and its carrier reconcile loading records before retaining a handover record."},
])
def test_optional_plan_metadata_round_trips_without_inventing_text_or_changing_branches(metadata):
    raw = {**shipment_plan(), **metadata}
    original = deepcopy(raw)
    parsed, errors = parse_plan({"workflow_plan": raw})
    assert errors == []
    reparsed, errors = parse_plan(parsed)
    assert errors == []
    assert reparsed == parsed
    assert raw == original
    for field in ("industry", "goal", "public_narrative"):
        assert (field in parsed) == (field in raw)
        if field in raw:
            assert parsed[field] == raw[field]
    selection = logistics_selection()
    first, first_errors = compile_plan(parsed, selection, "T331", ("node_a", "node_b1", "node_b2"), seed=7)
    second, second_errors = compile_plan(reparsed, selection, "T331", ("node_a", "node_b1", "node_b2"), seed=7)
    assert first_errors == second_errors == []
    assert first.as_dict() == second.as_dict()


@pytest.mark.parametrize("goal", ["", " \t\n"])
def test_explicit_empty_goal_still_fails(goal):
    parsed, errors = parse_plan({**shipment_plan(), "goal": goal})
    assert parsed is None
    assert errors == ["PLAN_GOAL_EMPTY"]


def test_generation_prompt_includes_the_business_fields_it_asks_the_model_to_supply():
    prompt = plan_prompt(logistics_selection(), "T331", {}, focus="conditional")
    schema = prompt["workflow_plan_schema"]
    assert schema["industry"] == "industry.logistics"
    assert schema["goal"] and schema["public_narrative"]
    requirements = " ".join(prompt["requirements"])
    assert "non-empty goal" in requirements
    assert "public_narrative" in requirements
    assert "actually establish" in requirements
