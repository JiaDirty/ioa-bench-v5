from pathlib import Path

import pytest

from ioabench.runtime import ImmutableManifestStore


def test_manifest_is_write_once(tmp_path: Path) -> None:
    store = ImmutableManifestStore(tmp_path / "manifests")
    manifest = {"run_id": "run-1", "profile": "local-v1"}
    store.freeze(manifest)

    with pytest.raises(FileExistsError):
        store.freeze({**manifest, "profile": "changed"})
    assert store.load("run-1")["profile"] == "local-v1"
