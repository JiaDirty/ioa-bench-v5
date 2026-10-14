import asyncio
from pathlib import Path

import pytest

from ioabench.core import RunState
from ioabench.storage.sqlite import LocalStores, StoreRole
from ioabench.storage.sqlite.run_repo import SqliteRunRepository
from ioabench.runtime import SqliteRunLifecycle


def test_lifecycle_persists_valid_transitions_and_rejects_skips(tmp_path: Path) -> None:
    stores = LocalStores.from_directory(tmp_path / "data")
    stores.migrate()
    with stores.connect(StoreRole.CONTROL) as connection:
        connection.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?)",
            ("experiment-1", "test", "2026-09-23T00:00:00Z", "v1", "PENDING"),
        )
    asyncio.run(SqliteRunRepository(stores).put_manifest({
        "run_id": "run-1", "experiment_id": "experiment-1", "test_id": "T311",
        "case_id": "case-1", "condition_name": "risk",
    }))
    lifecycle = SqliteRunLifecycle(stores)
    asyncio.run(lifecycle.transition("run-1", RunState.PREPARING, idempotency_key="t-1"))
    with pytest.raises(ValueError):
        asyncio.run(lifecycle.transition("run-1", RunState.COMPLETED, idempotency_key="t-2"))
    asyncio.run(lifecycle.transition("run-1", RunState.PREPARING, idempotency_key="t-1"))
    assert asyncio.run(lifecycle.state("run-1")) is RunState.PREPARING
