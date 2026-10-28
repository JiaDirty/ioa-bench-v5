from copy import deepcopy

from ioabench.v5.ai_generation.workflow_novelty import canonical_graph, isomorphism, workflow_graph
from tests.v5.test_workflow_composition_r3 import (
    FINANCE_LINEAR3, MEDICINE_FORK_JOIN, MEDICINE_LINEAR3, MEDICINE_LINEAR4, _compile)


def test_exact_mapping_ignores_ids_and_independent_array_order():
    binding, errors = _compile(MEDICINE_FORK_JOIN, "T321", ("integration_agent",))
    assert not errors
    graph = workflow_graph(binding)
    renamed = {"version": graph["version"],
               "nodes": {"renamed_" + sid: label for sid, label in reversed(list(graph["nodes"].items()))},
               "edges": [("renamed_" + a, "renamed_" + b, kind) for a, b, kind in reversed(graph["edges"])]}
    mapping = isomorphism(graph, renamed)
    assert mapping is not None
    assert {(mapping[a], mapping[b], kind) for a, b, kind in graph["edges"]} == set(renamed["edges"])
    assert canonical_graph(graph)["family_id"] == canonical_graph(renamed)["family_id"]


def test_equivalent_industry_tools_do_not_create_a_family():
    medicine, _ = _compile(MEDICINE_LINEAR3, "T321", ("integration_agent",))
    finance, _ = _compile(FINANCE_LINEAR3, "T321", ("integration_agent",))
    assert isomorphism(workflow_graph(medicine), workflow_graph(finance)) is not None


def test_causal_receipt_permission_condition_and_new_action_are_distinct():
    binding, _ = _compile(MEDICINE_LINEAR3, "T321", ("integration_agent",))
    graph = workflow_graph(binding)
    for kind in ("receipt", "granted", "evidence_visible"):
        changed = deepcopy(graph)
        changed["edges"] = [edge for edge in graph["edges"] if edge[2] != kind]
        assert isomorphism(graph, changed) is None
    changed = deepcopy(graph)
    changed["nodes"]["s3"]["optional"] = True
    changed["edges"].append(("s2", "s3", "condition:True"))
    assert isomorphism(graph, changed) is None
    extended, _ = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))
    assert isomorphism(graph, workflow_graph(extended)) is None


def test_declared_join_edge_is_a_real_runtime_prerequisite():
    binding, errors = _compile(MEDICINE_FORK_JOIN, "T321", ("integration_agent",))
    assert not errors
    commit = next(step for step in binding.plan if step["capability"] == "commit")
    assert "s4" in commit["requires"]
    assert ("s4", commit["stage_id"], "precedes") in workflow_graph(binding)["edges"]


def test_annotation_only_edge_type_is_not_an_executable_difference():
    plan = deepcopy(MEDICINE_LINEAR3)
    plan["edges"][0]["type"] = "order"
    first, _ = _compile(MEDICINE_LINEAR3, "T321", ("integration_agent",))
    second, _ = _compile(plan, "T321", ("integration_agent",))
    assert isomorphism(workflow_graph(first), workflow_graph(second)) is not None


def test_hash_collision_and_branch_truth_do_not_manufacture_families(monkeypatch):
    binding, _ = _compile(MEDICINE_LINEAR3, "T321", ("integration_agent",))
    graph = workflow_graph(binding)
    changed = deepcopy(graph)
    changed["nodes"]["s3"]["capability"] = "attest"
    monkeypatch.setattr("ioabench.v5.ai_generation.workflow_novelty.canonical_sha256", lambda value: "collision")
    assert canonical_graph(graph)["family_id"] == canonical_graph(changed)["family_id"]
    assert isomorphism(graph, changed) is None
    from tests.v5.test_workflow_composition_r3 import MEDICINE_CONDITIONAL
    first, _ = _compile(MEDICINE_CONDITIONAL, "T321", ("integration_agent",), seed=7)
    second, _ = _compile(MEDICINE_CONDITIONAL, "T321", ("integration_agent",), seed=14)
    assert isomorphism(workflow_graph(first), workflow_graph(second)) is not None
