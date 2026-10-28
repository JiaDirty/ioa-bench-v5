"""Plan fresh G2 structure cells from the retained census; never call a provider or admit data."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.ai_generation.acquisition import program_proposal, proposal_contract
from ioabench.v5.ai_generation.development import structure_vector
from ioabench.v5.ai_generation.direct_deepseek import immutable
from ioabench.v5.ai_generation.history import classify
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.core.case import SUITES, case_from_dict

VERSION = "ioabench.v5.development-coverage-plan/1.0.0"


def executable_cells(suite, *, seed=1030280):
    """Enumerate only finite payload enums and collapse actual consumer-equivalent combinations."""
    spec = suite_spec(suite, typed=True)
    contract = proposal_contract(spec, seed=seed, difficulty="M")
    payload = contract["schema"]["properties"]["suite_payload"]
    axes = {key: field["enum"] for key, field in payload["properties"].items()
            if len(field.get("enum", [])) > 1}
    targets = [dict(zip(axes, values)) for values in product(*axes.values())]
    # The legacy T362 grammar remains legal without opting into the paired graph/release fields.
    if suite == "T362":
        targets = [{"evidence_access": value} for value in axes["evidence_access"]] + targets
    cells, rejected = {}, []
    for target in targets:
        try:
            blueprint = program_proposal(spec, seed=seed, difficulty="M", target=target)
            control, _ = spec.adapter.compile_pair(blueprint, seed=seed)
            vector = structure_vector(control)
            key = vector["structural_cell_sha256"]
            cells.setdefault(key, {"cell_sha256": key, "target": target,
                "runtime_consumed": vector["runtime_consumed"], "blueprint_sha256": sha256(
                    json.dumps(blueprint, sort_keys=True).encode()).hexdigest()})
        except (CandidateRejected, ValueError) as exc:
            rejected.append({"target": target, "reason": str(exc)})
    return spec, {"suite": suite, "finite_axes": axes, "cells": list(cells.values()),
        "compiled_cell_upper_bound": len(cells), "rejected_combinations": rejected,
        "capacity_basis": "Finite schema enums, compiler fidelity and runtime-consumed vector; reference gates are run separately for planned cells.",
        "limits": ["No arbitrary topology or unlisted evidence flow.",
                   "Names, domain, text, seed, continuous ratings and E/M/H labels do not add structural capacity.",
                   "This bound covers the current finite enum grammar, not every subtype or a new scientific family."],
        "difficulty": {"design_intent": "M", "calibrated": False},
        "simulation_only": suite in {"T361", "T362", "T363"}}


def history_precheck(pair, index, scenario):
    if index is None:
        return {"status": "NOT_RUN", "reason": "No frozen history index supplied; the actual workflow must check all history before admission."}
    rows = {}
    for arm, case in zip(("CONTROL", "RISK"), pair):
        result = classify(case, index, scenario=scenario)
        rows[arm] = {key: result.get(key) for key in ("status", "legacy_status", "new_family", "reason")}
        neighbors = result.get("nearest_neighbors", [])
        rows[arm].update(max_text_similarity=max((row["text_similarity"] for row in neighbors), default=None),
                         relevant_neighbors=len(neighbors))
    return {"status": "COMPLETE_PREFLIGHT_ONLY", "arms": rows,
            "limitation": "A historical-snapshot precheck is not current-source global novelty proof or admission."}


def build_plan(census, *, goal=3, index=None, suites=SUITES):
    baseline, baseline_projections = {}, []
    for row in census["pairs"]:
        vector = row["vector"]
        if row.get("source_directory"):
            path = Path(row["source_directory"]) / "PAIR.json"
            if sha256(path.read_bytes()).hexdigest() != row["pair_sha256"]:
                raise ValueError("retained baseline pair changed: " + str(path))
            pair = [case_from_dict(value, allow_dynamic=True) for value in json.loads(path.read_text(encoding="utf-8-sig"))]
            vector = structure_vector(next(case for case in pair if case.arm == "CONTROL"))
        baseline.setdefault(row["suite"], set()).add(vector["structural_cell_sha256"])
        baseline_projections.append({"id": row["id"], "original_cell_sha256": row["vector"]["structural_cell_sha256"],
            "current_source_cell_sha256": vector["structural_cell_sha256"],
            "pair_sha256": row.get("pair_sha256"), "source_data_changed": False})
    capacity, tasks, checks, allocations = [], [], [], []
    # The two concrete gaps execute before expansion of already covered suites.
    order = [suite for suite in ("T362", "T322", "T321", "T331", "T352") if suite in suites]
    order += [suite for suite in suites if suite not in order]
    for suite in order:
        spec, row = executable_cells(suite)
        covered = baseline.get(suite, set())
        unseen = [cell for cell in row["cells"] if cell["cell_sha256"] not in covered]
        if index is not None and suite in {"T321", "T331", "T352"}:
            for cell in unseen:
                blueprint = program_proposal(spec, seed=1030280, difficulty="M", target=cell["target"])
                pair = spec.adapter.compile_pair(blueprint, seed=1030280)
                cell["prototype_history_precheck"] = history_precheck(pair, index, spec.scenario_factory())
            rank = {"CANDIDATE_NEW_FAMILY": 0, "VERIFIED_NEW_FAMILY": 0, "VALID_FAMILY_INSTANCE": 1,
                    "INDETERMINATE": 2, "NEAR_DUPLICATE": 3, "EXACT_DUPLICATE": 4}
            unseen.sort(key=lambda cell: max(rank.get(arm["status"], 5)
                for arm in cell["prototype_history_precheck"]["arms"].values()))
        if suite == "T362":
            unseen = [cell for cell in unseen if "evidence_flow" in cell["target"]]
            requested = len(unseen)
        else:
            requested = max(0, goal - len(covered))
        selected = unseen[:requested]
        reference_passes = 0
        for number, cell in enumerate(selected, 1):
            seed = 1030280 + len(tasks)
            task = {"id": f"coverage-{suite}-{number:02d}", "suite": suite, "seed": seed,
                "difficulty": "M", "effort": "high", "domain": "synthetic local operational review",
                "cohort": "coverage-v1", "target": cell["target"],
                "history_scope": "VERSION_SCOPED" if suite == "T322" else "FULL_HISTORY",
                "expected_structural_cell_sha256": cell["cell_sha256"],
                "prototype_not_admitted": True}
            blueprint = program_proposal(spec, seed=seed, difficulty="M", target=task["target"])
            try:
                result = compile_and_gate(spec, blueprint, seed=seed)
            except CandidateRejected as exc:
                checks.append({"task_id": task["id"], "status": "FAIL", "stage": exc.stage,
                               "findings": exc.findings})
                continue
            vector = structure_vector(result["control"])
            if vector["structural_cell_sha256"] != cell["cell_sha256"]:
                checks.append({"task_id": task["id"], "status": "FAIL", "stage": "SEED_DEPENDENT_STRUCTURE",
                               "reason": "A new seed changed an allegedly fixed consumed structure cell."})
                continue
            assert vector["structural_cell_sha256"] not in covered, "never regenerate a retained baseline cell"
            reference_passes += 1
            precheck = history_precheck((result["control"], result["risk"]), index, spec.scenario_factory())
            checks.append({"task_id": task["id"], "status": "PASS", "pair_gate": result["gate"],
                           "history_precheck": precheck, "cell_sha256": vector["structural_cell_sha256"]})
            tasks.append(task)
        row.update(baseline_cells=len(covered), baseline_cell_sha256=sorted(covered),
                   reference_verified_planned_cells=reference_passes)
        capacity.append(row)
        allocations.append({"suite": suite, "baseline_cells": len(covered), "requested_goal": goal,
            "compiled_cell_upper_bound": row["compiled_cell_upper_bound"],
            "planned_fresh_cells": reference_passes,
            "goal_unreachable_in_current_finite_grammar": row["compiled_cell_upper_bound"] < goal,
            "baseline_cells_replanned": 0,
            "history_scope": "VERSION_SCOPED_HISTORY_INDETERMINATE" if suite == "T322" else "FULL_HISTORY_REQUIRED",
            "status": "CAPACITY_SATURATED_BELOW_GOAL" if row["compiled_cell_upper_bound"] < goal else "PLANNED_PREFLIGHT_ONLY"})
    plan = {"version": VERSION, "status": "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL",
        "provider_calls": 0, "model_generated_pairs": 0, "accepted_pairs": 0, "new_scientific_families": 0,
        "baseline_pairs_retained": census.get("pair_count", len(census["pairs"])), "baseline_regeneration_tasks": 0,
        "tasks": tasks, "preflight": checks, "baseline_current_source_reprojection": baseline_projections,
        "limitations": ["Preflight uses program proposals, not fresh model generation or pool admission.",
                        "T322 remains VERSION_SCOPED until missing historical v5.1.0 facts are recovered.",
                        "All actual candidates must repeat hard gates, both-arm full-history checks, Replay and isolated audits.",
                        "A duplicate program-proposal prototype is retained as a negative precheck; it must never be submitted as fresh data. Fresh G2 responses are checked independently, and wording alone never establishes a new cell.",
                        "M is design intent, not empirically calibrated difficulty."]}
    return plan, {"version": VERSION, "suites": capacity}, {"version": VERSION, "suites": allocations,
        "task_count": len(tasks), "tasks_by_suite": dict(Counter(task["suite"] for task in tasks)),
        "provider_calls": 0, "accepted_pairs": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--history-index", type=Path)
    parser.add_argument("--goal", type=int, default=3)
    args = parser.parse_args()
    if args.goal < 1:
        parser.error("--goal must be positive")
    census_path = args.out / "BASELINE_CENSUS.json"
    census = json.loads(census_path.read_text(encoding="utf-8-sig"))
    history_path = args.history_index
    if history_path is None:
        previous = Path(census["pairs"][0]["source_directory"]).parents[1]
        candidates = list((previous / "history").glob("*.json"))
        history_path = max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None
    index = json.loads(history_path.read_text(encoding="utf-8-sig")) if history_path else None
    plan, capacity, allocation = build_plan(census, goal=args.goal, index=index)
    plan["input_sha256"] = {"baseline_census": sha256(census_path.read_bytes()).hexdigest(),
        "history_index": sha256(history_path.read_bytes()).hexdigest() if history_path else None}
    plan["history_index_path"] = str(history_path) if history_path else None
    for name, value in (("PLAN_COVERAGE_V1.json", plan), ("STRUCTURE_CAPACITY.json", capacity),
                        ("COVERAGE_ALLOCATION.json", allocation)):
        immutable(args.out / name, value)
    print(json.dumps({"status": plan["status"], "task_count": len(plan["tasks"]),
                      "tasks_by_suite": allocation["tasks_by_suite"], "provider_calls": 0}))
    return 0 if plan["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
