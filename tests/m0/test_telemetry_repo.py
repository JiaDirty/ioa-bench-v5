import asyncio
from pathlib import Path

import pytest

from ioabench.storage.sqlite import LocalStores, StoreRole
from ioabench.storage.sqlite.telemetry_repo import TelemetryRepository
from ioabench.telemetry import NormalizedEvent


def test_telemetry_repository_round_trips_events_and_detects_orphans(tmp_path: Path) -> None:
    stores = LocalStores.from_directory(tmp_path / "data")
    stores.migrate()
    repository = TelemetryRepository(stores)
    event = NormalizedEvent.create(
        event_id="event-1", run_id="run-1", case_id="case-1", event_type="agent.decision",
        stage="DECISION", trace_id="trace-1", attributes={"org_id": "org-a"},
    )
    asyncio.run(repository.emit(event))
    assert repository.get_run_events("run-1") == (event,)
    assert repository.duplicate_event_ids() == ()
    assert repository.orphan_event_ids({"run-1"}, {"case-1"}) == ()
    assert repository.orphan_event_ids({"run-2"}, {"case-1"}) == ("event-1",)

    with pytest.raises(Exception):
        asyncio.run(repository.emit(event))


def test_telemetry_write_does_not_create_control_tables(tmp_path: Path) -> None:
    stores = LocalStores.from_directory(tmp_path / "data")
    stores.migrate()
    asyncio.run(TelemetryRepository(stores).emit(
        NormalizedEvent.create(run_id="run-1", case_id="case-1", event_type="task.failed")
    ))
    with stores.connect(StoreRole.CONTROL) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='events'").fetchone() is None
