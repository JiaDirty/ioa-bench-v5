"""Deterministic offline fixtures shared by the test suite."""

from pathlib import Path

import pytest

from ioabench.storage.sqlite import LocalStores


@pytest.fixture
def local_stores(tmp_path: Path) -> LocalStores:
    stores = LocalStores.from_directory(tmp_path / "data")
    stores.migrate()
    return stores


@pytest.fixture
def deterministic_world() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "world_id": "W_TEST_DETERMINISTIC",
        "version": "1.0.0",
        "seed": 7,
        "organizations": [{"org_id": "org-a"}, {"org_id": "org-b"}],
        "resources": [],
        "services": [],
    }
