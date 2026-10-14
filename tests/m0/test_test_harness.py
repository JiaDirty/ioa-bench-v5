from pathlib import Path

import pytest


def test_deterministic_world_fixture(deterministic_world: dict[str, object]) -> None:
    assert deterministic_world["seed"] == 7
    assert len(deterministic_world["organizations"]) == 2


def test_integration_marker_is_registered() -> None:
    marker = pytest.Config.fromdictargs({}, []).getini("markers")
    assert any(str(entry).startswith("integration:") for entry in marker)


def test_regression_test_naming_convention_is_documented() -> None:
    document = Path(__file__).parents[2] / "docs" / "TESTING.md"
    assert "test_regression_" in document.read_text(encoding="utf-8")
