from pathlib import Path
import asyncio

from ioabench.storage.sqlite import LocalStores, SqliteRunRepository, StoreRole


def test_stores_are_separate_and_agent_paths_exclude_oracle(tmp_path: Path) -> None:
    stores = LocalStores.from_directory(tmp_path / "data")
    stores.migrate()

    assert len({path.resolve() for path in stores.paths.values()}) == 4
    visible = stores.agent_visible_paths()
    assert visible == {"sut": str(stores.paths[StoreRole.SUT])}
    assert "oracle" not in visible
    assert str(stores.paths[StoreRole.ORACLE]) not in visible.values()


def test_run_repository_uses_only_control_store(tmp_path: Path) -> None:
    stores = LocalStores.from_directory(tmp_path / "data")
    stores.migrate()
    with stores.connect(StoreRole.CONTROL) as connection:
        connection.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?)",
            ("experiment-1", "test", "2026-09-23T00:00:00Z", "v1", "PENDING"),
        )
    repository = SqliteRunRepository(stores)
    manifest = {
        "run_id": "run-1", "experiment_id": "experiment-1", "test_id": "T311",
        "case_id": "case-1", "condition_name": "risk",
    }
    asyncio.run(repository.put_manifest(manifest))
    assert asyncio.run(repository.get_manifest("run-1")) == manifest
    asyncio.run(repository.update_status("run-1", "RUNNING", idempotency_key="transition-1"))
    asyncio.run(repository.update_status("run-1", "RUNNING", idempotency_key="transition-1"))
    with stores.connect(StoreRole.ORACLE) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='runs'").fetchone() is None
    with stores.connect(StoreRole.CONTROL) as connection:
        assert connection.execute("SELECT COUNT(*) FROM run_transitions").fetchone() == (1,)
