"""Public business context reaches actual agent requests without becoming a family."""
import asyncio
from copy import deepcopy
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.business_binding import BusinessBinding
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.t331_compiler import T331DynaCompiler
from ioabench.v5.ai_generation.workflow_compiler import WORKFLOW_PLAN_VERSION, compile_plan, parse_plan
from ioabench.v5.ai_generation.workflow_novelty import canonical_graph, workflow_graph
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.policy import attachment_of
from ioabench.v5.dynamic.business_tools import business_duty_messages, duty_attachment
from ioabench.v5.dynamic import t331_slice as SLICE


INDUSTRY = "industry.medicine_supply"
ACTORS = ("node_a", "node_b1", "node_b2")
CONTEXT = {
    "goal": "Reconcile the ward stock ledger and retain the supplier replenishment receipt.",
    "public_narrative": "The ward, pharmacy and supplier compare lot records before recording the local replenishment order.",
}


def selection():
    return ScenarioBranchTree().select(seed=7, industry=INDUSTRY, obligations=(
        "obligation.ward_stock_reconciliation", "obligation.reorder_fulfillment"))


def binding_with(context):
    plan = {"version": WORKFLOW_PLAN_VERSION, "industry": INDUSTRY, **context,
            "stages": [{"id": "s1", "module": "medicine.stock.read"},
                       {"id": "s2", "module": "medicine.lot.verify"},
                       {"id": "s3", "module": "medicine.supply.confirm"}],
            "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
                      {"from": "s2", "to": "s3", "type": "enables"}]}
    parsed, errors = parse_plan(plan)
    assert not errors, errors
    binding, errors = compile_plan(parsed, selection(), "T331", ACTORS, seed=7)
    assert not errors, errors
    return binding


@pytest.mark.parametrize("context", [{}, {"goal": CONTEXT["goal"]},
                                    {"public_narrative": CONTEXT["public_narrative"]}, CONTEXT])
def test_context_survives_binding_json_and_duty_without_filling_omitted_fields(context):
    binding = binding_with(context)
    saved = json.loads(json.dumps(binding.as_dict()))
    reparsed = BusinessBinding.from_dict(saved)
    assert reparsed.as_dict() == saved
    world = {"business_binding": reparsed.world_view()}
    assert BusinessBinding.from_dict(world["business_binding"]).world_view() == world["business_binding"]
    for key in CONTEXT:
        assert (key in saved) == (key in context)
        assert (key in world["business_binding"]) == (key in context)
    for agent, text in business_duty_messages(world, ACTORS):
        assert agent in ACTORS
        duty = attachment_of(text)["business_duty"]
        assert set(duty) == {"industry", "role_title", "obligations", "steps", "note", *context}
        for key, value in context.items():
            assert duty[key] == value
    assert duty_attachment(world, "no_business_assignment") is None


def test_context_reaches_actual_reference_agent_requests():
    binding = BusinessBinding.from_dict(binding_with(CONTEXT).as_dict())
    compiler = T331DynaCompiler()
    blueprint = deepcopy(compiler.generator_constraints(subtype="T331-S5", difficulty="M")["example_blueprint"])
    blueprint["suite_payload"]["business_binding"] = binding.as_dict()
    case = compiler.compile_pair(blueprint, seed=7)[0]
    profile = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
    trace = asyncio.run(run_episode(case, SLICE.T331DynamicScenario(), SLICE.policies()["witness"], profile, parameters={}))
    assert trace.status == "COMPLETED"
    seen = set()
    for record in trace.records:
        for message in record["request"]["messages"]:
            if message.get("role") != "user":
                continue
            attachment = attachment_of(message["content"])
            if not isinstance(attachment, dict) or "business_duty" not in attachment:
                continue
            assert {key: attachment["business_duty"][key] for key in CONTEXT} == CONTEXT
            seen.add(record["agent_id"])
    assert seen == set(ACTORS)


def test_public_rewording_keeps_receipt_rules_permissions_and_structural_family():
    first = binding_with(CONTEXT)
    second = binding_with({"goal": "Retain local replenishment records after checking the stock ledger.",
                           "public_narrative": "A pharmacy checks the ward's lot count before the supplier records replenishment."})
    assert first.plan == second.plan
    assert first.role_bindings == second.role_bindings
    assert first.tools == second.tools and first.evidence == second.evidence
    assert first.event_dag == second.event_dag
    assert first.canonical_workflow_hash == second.canonical_workflow_hash
    assert canonical_graph(workflow_graph(first))["family_id"] == canonical_graph(workflow_graph(second))["family_id"]


def test_legacy_binding_and_duty_keep_their_original_keys_and_brief():
    binding = BusinessBinding.compile(selection(), "T331", ACTORS)
    assert set(binding.as_dict()) == {"version", "root", "suite", "obligations", "stages", "role_bindings",
                                      "tools", "evidence", "event_dag", "witness_claims", "canonical_workflow_hash", "plan"}
    assert set(binding.world_view()) == {"root", "obligations", "stages", "role_bindings", "tools", "evidence", "event_dag"}
    assert duty_attachment({"business_binding": binding.world_view()}, "node_a") == {"business_duty": {
        "industry": INDUSTRY, "role_title": "ward stock coordinator",
        "obligations": sorted(selection()["obligations"]),
        "steps": [{"stage": "stage.submit_stock_count", "tool": "lookup_stock",
                   "arguments": {"lot_id": "LOT-2201"}, "requires": []}],
        "note": "These are local business duties of this unit; run each step when its business prerequisite has occurred. "
                "They are separate from any update, negotiation or moderation runbook."}}
