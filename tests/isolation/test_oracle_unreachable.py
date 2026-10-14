from pathlib import Path

from ioabench.security import build_agent_environment
from ioabench.storage.sqlite import LocalStores


def test_tested_agent_environment_has_only_sut_path(tmp_path: Path) -> None:
    stores = LocalStores.from_directory(tmp_path / "data")
    environment = build_agent_environment(stores, "agent-1")

    assert environment.visible_paths == {"sut": stores.paths[next(role for role in stores.paths if role.value == "sut")]}
    assert environment.has_oracle_access() is False
    assert "oracle" not in environment.__dict__
