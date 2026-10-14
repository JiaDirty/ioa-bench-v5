"""Auditable mechanism/world/difficulty quota planning."""

from __future__ import annotations

from dataclasses import dataclass

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


def _balanced(labels: tuple[str, ...], total: int) -> dict[str, int]:
    base, remainder = divmod(total, len(labels))
    return {label: base + (index < remainder) for index, label in enumerate(labels)}
