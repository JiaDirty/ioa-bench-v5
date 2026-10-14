from pathlib import Path

from ioabench.models import load_model_profile


def test_tested_model_profile_is_explicit_and_schema_valid() -> None:
    root = Path(__file__).parents[2]
    profile = load_model_profile(root / "config" / "models" / "deepseek-v4.1-flash.yaml")

    assert profile.provider == "aihubmix"
    assert profile.model_id == "deepseek-v4.1-flash"
    assert profile.role == "TESTED"
    assert profile.default_parameters["temperature"] == 0.0
    assert "tools" in profile.capabilities
