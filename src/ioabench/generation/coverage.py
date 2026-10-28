"""Auditable mechanism/world/difficulty quota planning."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
import json
from math import prod
from typing import Any, Callable, Iterable, Mapping, Sequence

from ioabench.hashing import canonical_sha256

from .recipes import SuiteRecipe


@dataclass(frozen=True)
class CoveragePlan:
    test_id: str
    qualified_target: int
    difficulty_targets: dict[str, int]
    mechanism_targets: dict[str, int]
    world_targets: dict[str, int]
    candidate_target: int


class CoveragePlanner:
    def plan(self, recipe: SuiteRecipe, *, qualified_target: int = 90, oversample_factor: float = 1.7) -> CoveragePlan:
        if qualified_target < 1 or oversample_factor < 1:
            raise ValueError("qualified_target must be positive and oversample_factor must be >= 1")
        difficulty_targets = _balanced(recipe.difficulty_labels, qualified_target)
        mechanism_targets = _balanced(tuple(template.mechanism_id for template in recipe.mechanism_templates), qualified_target)
        world_targets = _balanced(recipe.world_ids, qualified_target)
        return CoveragePlan(recipe.test_id, qualified_target, difficulty_targets, mechanism_targets, world_targets, int(qualified_target * oversample_factor + 0.999))

    def plan_factors(self, factors: Mapping[str, Sequence[Any]], *,
                     feasible: Callable[[Mapping[str, Any]], bool],
                     critical_interactions: Iterable[Sequence[str]] = (),
                     covered: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
        """Deterministic constrained pairwise coverage over declared executable capabilities.

        The caller supplies the compiler's feasibility check. Labels and business wording must
        not be passed as executable factors; selected rows are acquisition targets, not data.
        """
        if any(not isinstance(name, str) or not name for name in factors):
            raise ValueError("executable factor names must be nonempty strings")
        names = sorted(factors)
        if not names or any(not factors[name] for name in names):
            raise ValueError("executable factors must have nonempty finite domains")
        if prod(len(factors[name]) for name in names) > 4096:
            raise ValueError("factor space exceeds the bounded planner; split by construct or subtype")
        for name in names:
            values = [json.dumps(value, sort_keys=True, allow_nan=False) for value in factors[name]]
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate capability value: {name}")
        groups = list(combinations(names, min(2, len(names))))
        for interaction in critical_interactions:
            group = tuple(sorted(interaction))
            if len(group) != 3 or len(set(group)) != 3 or not set(group) <= set(names):
                raise ValueError("critical interactions must name three distinct declared factors")
            if group not in groups:
                groups.append(group)

        def tokens(row: Mapping[str, Any]) -> set[tuple[str, ...]]:
            return {tuple(f"{name}={json.dumps(row[name], sort_keys=True, allow_nan=False)}" for name in group)
                    for group in groups}

        candidates, rejected = [], []
        for values in product(*(factors[name] for name in names)):
            row = dict(zip(names, values))
            (candidates if feasible(row) else rejected).append(row)
        required = set().union(*(tokens(row) for row in candidates)) if candidates else set()
        observed = set()
        covered_rows = [dict(row) for row in covered]
        for row in covered_rows:
            if (set(row) != set(names) or any(canonical_sha256(row[name]) not in
                    {canonical_sha256(value) for value in factors[name]} for name in names) or not feasible(row)):
                raise ValueError("covered row is outside the current executable capability space")
            observed.update(tokens(row))
        uncovered = required - observed
        selected = []
        remaining = list(candidates)
        while uncovered:
            row = max(remaining, key=lambda candidate: len(tokens(candidate) & uncovered))
            selected.append(row)
            uncovered -= tokens(row)
            remaining.remove(row)
        return {"schema_version": "ioabench.constraint-coverage/1.1.0",
                "factors": {name: list(factors[name]) for name in names},
                "feasible_rows": candidates, "infeasible_rows": rejected, "selected_rows": selected,
                "observed_rows": covered_rows, "outcomes": [],
                "target_interactions": len(required), "already_covered_interactions": len(required & observed),
                "planned_interactions": len(required), "critical_interactions": [list(group) for group in groups if len(group) == 3],
                "qualified_data_claimed": False, "shortfall": len(required - observed),
                "status": "PLANNED" if candidates else "CAPABILITY_GAP"}

    def next_target(self, plan: Mapping[str, Any]) -> dict[str, Any] | None:
        """Return each selected cell once; rejected attempts remain explicit shortfalls."""
        attempted = {_cell_id(item["factors"]) for item in plan["outcomes"]}
        for row in plan["selected_rows"]:
            if _cell_id(row) not in attempted:
                return {"cell_id": _cell_id(row), "factors": dict(row),
                        "sampling": "EXPLORATORY_ACQUISITION_ONLY"}
        return None

    def record_outcome(self, plan: dict[str, Any], factors: Mapping[str, Any],
                       outcome: Mapping[str, Any]) -> dict[str, Any]:
        """Attach an immutable terminal result, without promoting machine quality to science."""
        if not any(_same_row(factors, row) for row in plan["feasible_rows"]):
            raise ValueError("outcome cell is outside the executable capability space")
        proposal_id, status = outcome.get("proposal_id"), outcome.get("status")
        evidence_hash = outcome.get("evidence_sha256")
        if not isinstance(proposal_id, str) or not proposal_id:
            raise ValueError("outcome requires a nonempty proposal_id")
        if status not in {"MACHINE_ACCEPTED", "REJECTED", "PROVIDER_FAILED", "REQUEST_UNRESOLVED", "PIPELINE_FAILED"}:
            raise ValueError("outcome must have a recognized terminal factory status")
        if (not isinstance(evidence_hash, str) or len(evidence_hash) != 64
                or any(char not in "0123456789abcdef" for char in evidence_hash)):
            raise ValueError("outcome requires its persisted evidence_sha256")
        if any(key in outcome and not isinstance(outcome[key], str) for key in ("rejection_code", "verified_family_id")):
            raise ValueError("outcome rejection_code and verified_family_id must be strings when supplied")
        if "diversity" in outcome and not isinstance(outcome["diversity"], Mapping):
            raise ValueError("outcome diversity must be an evidence mapping")
        value = json.loads(json.dumps({"factors": dict(factors), "outcome": dict(outcome)},
                                      sort_keys=True, allow_nan=False))
        for recorded in plan["outcomes"]:
            if recorded["outcome"]["proposal_id"] == proposal_id:
                if recorded != value:
                    raise ValueError("recorded proposal outcome is immutable")
                return plan
        plan["outcomes"].append(value)
        return plan

    def report_coverage(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        """Report real acquisition results separately from the combinatorial target plan."""
        cells, accepted_rows = [], []
        for row in [*plan["feasible_rows"], *plan["infeasible_rows"]]:
            records = [item["outcome"] for item in plan["outcomes"] if _same_row(item["factors"], row)]
            accepted = [item for item in records if item["status"] == "MACHINE_ACCEPTED"]
            if accepted:
                accepted_rows.append(row)
            families = {item["verified_family_id"] for item in accepted
                        if item.get("verified_family_id") and
                        item.get("diversity", {}).get("status") == "VERIFIED_NEW_FAMILY"}
            rejections: dict[str, int] = {}
            for item in records:
                if item["status"] != "MACHINE_ACCEPTED":
                    reason = item.get("rejection_code", item["status"])
                    rejections[reason] = rejections.get(reason, 0) + 1
            cells.append({"cell_id": _cell_id(row), "factors": dict(row),
                "compilable": any(_same_row(row, candidate) for candidate in plan["feasible_rows"]),
                "sample_count": len(records), "machine_qualified_instances": len(accepted),
                "verified_executable_families": len(families), "rejection_reasons": rejections,
                "difficulty_empirical": [item.get("difficulty_empirical", "NOT_RUN") for item in accepted] or "NOT_RUN",
                "scientific_qualification": "NOT_ESTABLISHED_BY_COVERAGE"})
        groups = list(combinations(sorted(plan["factors"]), min(2, len(plan["factors"]))))
        groups.extend(tuple(group) for group in plan["critical_interactions"])
        def interactions(rows):
            return {canonical_sha256({name: row[name] for name in group}) for row in rows for group in groups}
        required, accepted = interactions(plan["feasible_rows"]), interactions(accepted_rows)
        return {"schema_version": "ioabench.constraint-coverage-report/1.0.0", "cells": cells,
                "target_interactions": len(required), "machine_covered_interactions": len(required & accepted),
                "shortfall": len(required - accepted), "unattempted_selected_cells": sum(
                    not any(_same_row(item["factors"], row) for item in plan["outcomes"])
                    for row in plan["selected_rows"]),
                "sampling": "EXPLORATORY_ACQUISITION_ONLY", "formal_accepted": False}

    def explain_unreachable_cell(self, plan: Mapping[str, Any], factors: Mapping[str, Any]) -> dict[str, Any]:
        if any(_same_row(factors, row) for row in plan["feasible_rows"]):
            return {"cell_id": _cell_id(factors), "status": "REACHABLE", "factors": dict(factors)}
        declared = any(_same_row(factors, row) for row in plan["infeasible_rows"])
        return {"cell_id": _cell_id(factors), "status": "CAPABILITY_GAP", "factors": dict(factors),
                "reason": "Compiler feasibility predicate rejected this combination." if declared else
                          "Cell is outside the declared executable factor domains.",
                "qualified_data_claimed": False}


def _cell_id(row: Mapping[str, Any]) -> str:
    return "cell-" + canonical_sha256(dict(row))


def _same_row(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return canonical_sha256(dict(left)) == canonical_sha256(dict(right))


def _balanced(labels: tuple[str, ...], total: int) -> dict[str, int]:
    base, remainder = divmod(total, len(labels))
    return {label: base + (index < remainder) for index, label in enumerate(labels)}
