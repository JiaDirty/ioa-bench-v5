from copy import deepcopy

import pytest

from scripts.v5.plan_development_coverage import build_plan, executable_cells, history_precheck
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.development import structure_vector
from ioabench.v5.ai_generation.history import HISTORY_VERSION
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.quality import QUALITY_VERSION, dedup_features


def baseline_row(suite, target, number):
    spec = suite_spec(suite, typed=True)
    blueprint = program_proposal(spec, seed=317, difficulty="M", target=target)
    case, _ = spec.adapter.compile_pair(blueprint, seed=317)
    return {"id": f"retained-{suite}-{number}", "suite": suite, "vector": structure_vector(case)}


def test_allocator_uses_actual_structure_and_never_refills_saturated_two_value_grammar():
    census = {"pair_count": 4, "pairs": [
        baseline_row("T311", {"credential_reference_access": "directory"}, 1),
        baseline_row("T311", {"credential_reference_access": "requested_document"}, 2),
        baseline_row("T331", {"fanout_width": 2, "propagation_topology": "fanout"}, 1),
        baseline_row("T331", {"fanout_width": 3, "propagation_topology": "fanout"}, 2)]}
    before = deepcopy(census)
    plan, capacity, allocation = build_plan(census, suites=["T311", "T331", "T362"])
    assert census == before and plan["status"] == "PASS"
    # 2026-10-24 tree factory: T362's compiled lattice adds per-owner staggered
    # release and the mandatory pre-digest relay (12 uncovered cells, was 6).
    assert len(plan["tasks"]) == 13
    assert allocation["tasks_by_suite"] == {"T362": 12, "T331": 1}
    assert all(task["target"]["propagation_topology"] != "fanout" for task in plan["tasks"] if task["suite"] == "T331")
    t311 = next(row for row in allocation["suites"] if row["suite"] == "T311")
    assert t311["compiled_cell_upper_bound"] == t311["baseline_cells"] == 2
    assert t311["goal_unreachable_in_current_finite_grammar"] and t311["planned_fresh_cells"] == 0
    t362 = next(row for row in capacity["suites"] if row["suite"] == "T362")
    assert t362["compiled_cell_upper_bound"] == 14  # Two legacy cells plus twelve consumed new-grammar cells.
    assert len(t362["rejected_combinations"]) == 36  # Grammar-illegal combos fail closed (shared opening, relay-flow deadlocks).
    assert all(row["status"] == "PASS" and len(row["pair_gate"]["runs"]) == 6 for row in plan["preflight"])
    assert plan["provider_calls"] == plan["model_generated_pairs"] == plan["accepted_pairs"] == 0


def test_t322_work_is_explicitly_version_scoped_and_not_claimed_history_valid():
    plan, capacity, allocation = build_plan({"pairs": []}, suites=["T322"])
    assert len(plan["tasks"]) == 2
    assert all(task["history_scope"] == "VERSION_SCOPED" for task in plan["tasks"])
    assert all(row["history_precheck"]["status"] == "NOT_RUN" for row in plan["preflight"])
    assert allocation["suites"][0]["history_scope"] == "VERSION_SCOPED_HISTORY_INDETERMINATE"
    assert capacity["suites"][0]["difficulty"] == {"design_intent": "M", "calibrated": False}


def test_history_precheck_preserves_actual_both_arm_duplicate_failures():
    spec, _ = executable_cells("T362")
    blueprint = program_proposal(spec, seed=317, difficulty="M", target={
        "evidence_access": "record_query", "evidence_flow": "contributor_relay", "evidence_release": "after_alert"})
    pair = spec.adapter.compile_pair(blueprint, seed=317)
    index = {"index_version": HISTORY_VERSION, "feature_version": QUALITY_VERSION,
             "source_sha256": {}, "findings": [], "records": [
                 {"features": dedup_features(case, scenario=spec.scenario_factory())} for case in pair]}
    result = history_precheck(pair, index, spec.scenario_factory())
    assert {row["status"] for row in result["arms"].values()} == {"EXACT_DUPLICATE"}
    assert all(row["new_family"] is False for row in result["arms"].values())
    assert result["status"] == "COMPLETE_PREFLIGHT_ONLY"


def test_changed_retained_pair_is_rejected_before_planning(tmp_path):
    (tmp_path / "PAIR.json").write_text("[]", encoding="utf-8")
    census = {"pairs": [{"id": "retained", "suite": "T331", "source_directory": str(tmp_path),
                         "pair_sha256": "wrong", "vector": {"structural_cell_sha256": "old"}}]}
    with pytest.raises(ValueError, match="retained baseline pair changed"):
        build_plan(census, suites=["T331"])
