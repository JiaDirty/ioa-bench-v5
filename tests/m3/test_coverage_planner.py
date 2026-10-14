from ioabench.generation.coverage import CoveragePlanner
from ioabench.generation.recipes import SuiteRecipeRegistry


def test_coverage_plan_targets_90_cases_and_audits_all_dimensions() -> None:
    recipe = SuiteRecipeRegistry.default().get("T311")
    plan = CoveragePlanner().plan(recipe)
    assert plan.qualified_target == 90
    assert plan.candidate_target == 153
    assert plan.difficulty_targets == {"Easy": 30, "Medium": 30, "Hard": 30}
    assert sum(plan.mechanism_targets.values()) == 90
    assert sum(plan.world_targets.values()) == 90
    assert set(plan.mechanism_targets) == {template.mechanism_id for template in recipe.mechanism_templates}
