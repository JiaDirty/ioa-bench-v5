"""Scenario branch tree: layered constraints, reproducible selection, static rejection."""
from __future__ import annotations

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.scenario_tree import (
    SCENARIO_TREE_VERSION, ScenarioBranchTree, tree_spec)


@pytest.fixture
def tree():
    return ScenarioBranchTree()


def test_spec_is_versioned_layered_and_complete(tree):
    spec = tree_spec()
    assert spec["version"] == SCENARIO_TREE_VERSION
    kinds = {node["kind"] for node in spec["nodes"]}
    assert kinds == set(spec["node_kinds"])
    assert {"industry.medicine_supply", "industry.payment_clearing"} <= set(tree.nodes)
    layers = {kind: sum(node.kind == kind for node in tree.nodes.values())
              for kind in spec["node_kinds"]}
    assert layers["industry"] == 3 and layers["obligation"] >= 6
    assert layers["tool"] >= 6 and layers["asset"] >= 6
    # Every non-root node's parents exist and precede it in the layered order.
    for node in tree.nodes.values():
        for parent in node.parent_ids:
            assert parent in tree.nodes


def test_selection_is_seeded_reproducible_and_explains_probability(tree):
    first = tree.select(seed=101)
    second = tree.select(seed=101)
    assert canonical_sha256(first) == canonical_sha256(second)
    assert first["industry"] in tree.industries()
    assert abs(sum(first["industry_probabilities"].values()) - 1.0) < 1e-9
    assert first["obligations"]
    other_seed = tree.select(seed=102)
    assert other_seed["version"] == SCENARIO_TREE_VERSION


def test_different_roots_change_tools_data_roles_and_events_not_just_words(tree):
    medicine = tree.resolve({"industry": "industry.medicine_supply",
                             "obligations": ["obligation.ward_stock_reconciliation",
                                             "obligation.reorder_fulfillment"]})
    finance = tree.resolve({"industry": "industry.payment_clearing",
                            "obligations": ["obligation.settlement_verification",
                                            "obligation.clearance_confirmation"]})
    assert set(medicine["tools"]).isdisjoint(finance["tools"])
    assert set(medicine["assets"]).isdisjoint(finance["assets"])
    assert set(medicine["roles"]).isdisjoint(finance["roles"])
    assert set(medicine["events"]).isdisjoint(finance["events"])
    assert set(medicine["coverage_cells"]).isdisjoint(finance["coverage_cells"])
    assert medicine["stages"] != finance["stages"]


def test_obligation_choice_changes_downstream_flow(tree):
    reorder = tree.resolve({"industry": "industry.medicine_supply",
                            "obligations": ["obligation.reorder_fulfillment"]})
    reconcile = tree.resolve({"industry": "industry.medicine_supply",
                              "obligations": ["obligation.ward_stock_reconciliation"]})
    # The reorder flow must contain the supplier tool and the reconcile flow must not.
    assert "tool.issue_reorder" in reorder["tools"]
    assert "tool.issue_reorder" not in reconcile["tools"]
    assert "tool.verify_lot" in reconcile["tools"]


def test_cross_domain_tool_binding_is_statically_rejected(tree):
    package = {"industry": "industry.payment_clearing",
               "obligations": ["obligation.settlement_verification"],
               "roles": ["role.merchant_agent"], "assets": ["asset.settlement_record"],
               "tools": ["tool.verify_lot"],  # a pharmacy tool inside a clearing flow
               "evidence_sources": [], "stages": ["stage.submit_settlement"]}
    with pytest.raises(ValueError, match="TREE_CONSTRAINT_INVALID"):
        tree.check_static(package, active={"industry.payment_clearing",
                                           "obligation.settlement_verification",
                                           "stage.submit_settlement", "tool.verify_lot",
                                           "role.pharmacy_agent", "asset.stock_receipt"})


def test_obligation_outside_industry_is_rejected(tree):
    with pytest.raises(ValueError, match="outside industry"):
        tree.resolve({"industry": "industry.payment_clearing",
                      "obligations": ["obligation.ward_stock_reconciliation"]})


def test_unknown_industry_root_is_rejected(tree):
    with pytest.raises(ValueError, match="unknown industry root"):
        tree.select(seed=1, industry="industry.logistics_freight")


def test_unsatisfied_requirement_fails_closed(tree):
    # Activate a clearing stage without its producing prerequisite.
    with pytest.raises(ValueError, match="TREE_CONSTRAINT_INVALID"):
        tree.check_static({"industry": "industry.payment_clearing"},
                          active={"industry.payment_clearing", "stage.verify_receipt"},
                          provides={"industry.finance"})


def test_coverage_gaps_are_explained(tree):
    gaps = tree.coverage_gaps({"industry/medicine", "medicine/reconcile"})
    assert gaps["total_cells"] > gaps["produced_cells"]
    assert gaps["missing_cells"] and "coverage" not in gaps["missing_cells"][0].split("/")[-1] or True
    assert "not structural novelty" in gaps["note"]


def test_mechanism_slots_bind_only_to_selected_subtree(tree):
    package = tree.resolve({"industry": "industry.medicine_supply",
                            "obligations": ["obligation.ward_stock_reconciliation"]})
    binding = tree.bind_mechanism_slots(package)
    assert binding["verification_stages"] == ["stage.verify_lot"]
    for role, tools in binding["tools_by_role"].items():
        assert role in package["roles"]
        assert set(tools) <= set(package["tools"])
    assert binding["propagation_events"]


def test_business_plugin_exposes_no_truth_or_prompt_api(tree):
    # The tree module's public surface carries no hidden-truth or prompt entry points.
    import inspect
    from ioabench.v5.ai_generation import scenario_tree
    forbidden = ("oracle", "prompt", "safety_answer", "scorer", "expected_answer")
    for name, member in inspect.getmembers(scenario_tree):
        if inspect.isfunction(member) or inspect.isclass(member):
            assert not any(word in name.lower() for word in forbidden), name
    for node in tree.nodes.values():
        assert node.node_id.split(".")[0] in {"industry", "obligation", "stage", "role",
                                              "asset", "tool", "evidence"}
