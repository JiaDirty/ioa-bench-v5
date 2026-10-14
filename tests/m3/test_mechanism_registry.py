import pytest

from ioabench.generation import SuiteRecipeRegistry


def test_default_registry_covers_all_frozen_suites() -> None:
    registry = SuiteRecipeRegistry.default()
    recipes = registry.all()
    assert len(recipes) == 18
    assert {recipe.test_id for recipe in recipes} == {
        "T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
        "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363",
    }
    for recipe in recipes:
        assert 4 <= len(recipe.mechanism_templates) <= 6
        assert 2 <= len(recipe.world_ids) <= 3
        assert recipe.difficulty_labels == ("Easy", "Medium", "Hard")
        assert all(template.truth_requirements and template.exposure_requirements and template.control_requirements for template in recipe.mechanism_templates)
    assert all(registry.get(test_id).simulation_only for test_id in ("T361", "T362", "T363"))


def test_registry_rejects_duplicate_suite_recipe() -> None:
    registry = SuiteRecipeRegistry.default()
    with pytest.raises(ValueError):
        registry.register(registry.get("T311"))
