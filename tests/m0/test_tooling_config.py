from pathlib import Path
import tomllib


ROOT = Path(__file__).parents[2]


def test_pyproject_configures_build_and_quality_tools() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert config["build-system"]["build-backend"] == "setuptools.build_meta"
    assert config["project"]["requires-python"] == ">=3.12"
    dev_dependencies = config["project"]["optional-dependencies"]["dev"]
    assert any(dependency.startswith("pytest") for dependency in dev_dependencies)
    assert any(dependency.startswith("ruff") for dependency in dev_dependencies)
    assert any(dependency.startswith("mypy") for dependency in dev_dependencies)
    assert config["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert config["tool"]["mypy"]["strict"] is True
