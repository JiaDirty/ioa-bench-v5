from itertools import combinations
import importlib.util
from pathlib import Path

import pytest

from ioabench.generation.coverage import CoveragePlanner


def _pairs(rows):
    return {tuple((name, row[name]) for name in names)
            for row in rows for names in combinations(sorted(row), 2)}


def test_constrained_plan_covers_all_feasible_pairs_and_prunes_illegal_cells():
    factors = {"brokers": [2, 3], "visibility": ["initial", "delayed"], "difficulty": ["E", "M", "H"]}
    feasible = lambda row: row["visibility"] != "delayed" or row["brokers"] == 3
    planner = CoveragePlanner()
    plan = planner.plan_factors(factors, feasible=feasible)
    assert len(plan["feasible_rows"]) == 9 and len(plan["infeasible_rows"]) == 3
    assert _pairs(plan["selected_rows"]) == _pairs(plan["feasible_rows"])
    assert len(plan["selected_rows"]) < len(plan["feasible_rows"])
    assert plan == planner.plan_factors(factors, feasible=feasible)
    assert plan["qualified_data_claimed"] is False and plan["shortfall"] > 0
    filled = planner.plan_factors(factors, feasible=feasible, covered=plan["selected_rows"])
    assert filled["selected_rows"] == [] and filled["shortfall"] == 0


def test_critical_three_factor_interaction_has_explicit_coverage():
    factors = {"a": [0, 1], "b": [0, 1], "c": [0, 1]}
    plan = CoveragePlanner().plan_factors(factors, feasible=lambda row: True,
                                          critical_interactions=[("a", "b", "c")])
    assert len(plan["selected_rows"]) == 8
    assert plan["critical_interactions"] == [["a", "b", "c"]]


def test_infeasible_space_is_capability_gap_and_invalid_inputs_fail_closed():
    planner = CoveragePlanner()
    assert planner.plan_factors({"a": [1]}, feasible=lambda row: False)["status"] == "CAPABILITY_GAP"
    for factors in ({}, {"a": []}, {"a": [1, 1]}, {"a": list(range(4097))}, {1: ["invalid"]}):
        with pytest.raises(ValueError):
            planner.plan_factors(factors, feasible=lambda row: True)
    with pytest.raises(ValueError, match="three distinct"):
        planner.plan_factors({"a": [1]}, feasible=lambda row: True, critical_interactions=[("a", "b", "c")])
    with pytest.raises(ValueError, match="outside"):
        planner.plan_factors({"a": [1]}, feasible=lambda row: True, covered=[{"a": 2}])
    with pytest.raises(ValueError, match="outside"):
        planner.plan_factors({"a": [1]}, feasible=lambda row: True, covered=[{"a": True}])


def test_t321_seed_and_declared_axes_are_validated_by_the_real_compiler():
    root = Path(__file__).resolve().parents[2]
    module_spec = importlib.util.spec_from_file_location("coverage_command", root / "scripts/v5/plan_factory_coverage.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    spec = module._spec("T321")
    constraints = module._constraints(spec)
    for count, delivery, valid in ((2, "initial", True), (3, "initial", True),
                                    (3, "broker_gamma", True), (2, "broker_gamma", False)):
        blueprint = module._blueprint(spec, constraints, {"broker_count": count, "peer_profile_delivery": delivery}, "M")
        assert (not spec.adapter.validate_blueprint(blueprint)) == valid
        assert (not spec.adapter.validate_blueprint(blueprint)
                and not spec.adapter.fidelity_report(blueprint)["gaps"]) == valid


def test_coverage_executes_legal_cells_when_other_factor_combinations_are_impossible(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    module_spec = importlib.util.spec_from_file_location("coverage_pruning_command", root / "scripts/v5/plan_factory_coverage.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    monkeypatch.setattr(module, "SUITES", ["T321", "T331"])
    report = module.run(tmp_path)
    assert report["case_count"] > 0
    for suite in report["suites"].values():
        assert suite["status"] == "SUPPORTED", suite
        assert suite["plan"]["infeasible_rows"]
        assert {row["difficulty_target"] for row in suite["executions"]} == {"E", "M", "H"}
        assert all(row["gate"]["passed"] for row in suite["executions"])


def test_acquisition_feedback_is_durable_idempotent_and_does_not_manufacture_coverage():
    import json

    planner = CoveragePlanner()
    plan = planner.plan_factors({"brokers": [2, 3], "visibility": ["initial", "delayed"]},
        feasible=lambda row: row["visibility"] != "delayed" or row["brokers"] == 3)
    target = planner.next_target(plan)
    outcome = {"proposal_id": "proposal-1", "status": "REJECTED", "rejection_code": "FIDELITY",
               "evidence_sha256": "a" * 64}
    planner.record_outcome(plan, target["factors"], outcome)
    planner.record_outcome(plan, target["factors"], outcome)
    restored = json.loads(json.dumps(plan))
    assert planner.next_target(restored) == planner.next_target(plan)
    report = planner.report_coverage(restored)
    rejected = next(row for row in report["cells"] if row["cell_id"] == target["cell_id"])
    assert rejected["sample_count"] == 1 and rejected["rejection_reasons"] == {"FIDELITY": 1}
    assert report["machine_covered_interactions"] == 0
    assert report["shortfall"] == plan["target_interactions"]
    assert report["formal_accepted"] is False
    with pytest.raises(ValueError, match="immutable"):
        planner.record_outcome(plan, target["factors"], {**outcome, "status": "MACHINE_ACCEPTED"})


def test_machine_acceptance_needs_evidence_and_static_novelty_is_not_a_verified_family():
    planner = CoveragePlanner()
    plan = planner.plan_factors({"topology": ["chain", "fanout"]}, feasible=lambda row: True)
    target = planner.next_target(plan)
    outcome = {"proposal_id": "proposal-1", "status": "MACHINE_ACCEPTED", "evidence_sha256": "b" * 64,
               "verified_family_id": "family-one", "diversity": {"status": "CANDIDATE_NEW_FAMILY"}}
    with pytest.raises(ValueError, match="persisted"):
        planner.record_outcome(plan, target["factors"], {**outcome, "evidence_sha256": ""})
    planner.record_outcome(plan, target["factors"], outcome)
    report = planner.report_coverage(plan)
    cell = next(row for row in report["cells"] if row["cell_id"] == target["cell_id"])
    assert cell["machine_qualified_instances"] == 1 and cell["verified_executable_families"] == 0
    assert report["machine_covered_interactions"] == 1 and report["shortfall"] == 1
    next_target = planner.next_target(plan)
    planner.record_outcome(plan, next_target["factors"], {**outcome, "proposal_id": "proposal-2",
        "diversity": {"status": "VERIFIED_NEW_FAMILY"}})
    assert planner.next_target(plan) is None
    assert planner.report_coverage(plan)["shortfall"] == 0
    assert sum(row["verified_executable_families"] for row in planner.report_coverage(plan)["cells"]) == 1


def test_unreachable_cells_explain_compiler_pruning_and_outside_domains():
    planner = CoveragePlanner()
    plan = planner.plan_factors({"nodes": [2, 3]}, feasible=lambda row: row["nodes"] == 3,
                                covered=iter([{"nodes": 3}]))
    assert plan["observed_rows"] == [{"nodes": 3}]
    assert planner.explain_unreachable_cell(plan, {"nodes": 3})["status"] == "REACHABLE"
    assert "predicate" in planner.explain_unreachable_cell(plan, {"nodes": 2})["reason"]
    assert "domains" in planner.explain_unreachable_cell(plan, {"nodes": 4})["reason"]
    with pytest.raises(ValueError, match="outside"):
        planner.record_outcome(plan, {"nodes": 2}, {"proposal_id": "p", "status": "REJECTED", "evidence_sha256": "c" * 64})
