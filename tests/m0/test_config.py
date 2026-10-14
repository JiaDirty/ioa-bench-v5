from pathlib import Path

import pytest

from ioabench.config import BenchmarkConfig
from ioabench.errors import ConfigurationError


ROOT = Path(__file__).parents[2]
CONFIG_PATH = ROOT / "config" / "benchmark.default.yaml"


def test_local_config_resolves_paths_and_enforces_formal_profile() -> None:
    config = BenchmarkConfig.load(CONFIG_PATH)

    assert config.profile == "local-v1"
    assert config.public_internet is False
    assert config.docker_required is False
    assert config.storage["oracle"] == (ROOT / "data" / "oracle.db").resolve()
    assert config.artifacts_root == (ROOT / "data" / "artifacts").resolve()


def test_public_internet_cannot_be_enabled(tmp_path: Path) -> None:
    invalid_config = tmp_path / "benchmark.yaml"
    invalid_config.write_text(CONFIG_PATH.read_text(encoding="utf-8").replace("public_internet: false", "public_internet: true"), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="public_internet=false"):
        BenchmarkConfig.load(invalid_config)
