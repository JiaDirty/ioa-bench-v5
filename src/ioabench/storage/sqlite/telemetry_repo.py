"""SQLite repository for normalized telemetry events."""

from __future__ import annotations

import json
from typing import Iterable

from ioabench.telemetry import NormalizedEvent

from .stores import LocalStores, StoreRole


class TelemetryRepository:
    def __init__(self, stores: LocalStores) -> None:
        self._stores = stores

    async def emit(self, event: NormalizedEvent) -> None:
        if not event.run_id or not event.case_id:
            raise ValueError("telemetry events require run_id and case_id")
        with self._stores.connect(StoreRole.TELEMETRY) as connection:
            connection.execute(
                "INSERT INTO events(event_id, run_id, case_id, event_time, stage, event_type, "
                "actor_agent_id, target_agent_id, trace_id, span_id, parent_span_id, task_id, message_id, "
                "delegation_id, claim_id, action_id, protocol, protocol_version, outcome, error_class, "
                "payload_sha256, attributes_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                event.as_row(),
            )

    async def flush(self, run_id: str) -> None:
        with self._stores.connect(StoreRole.TELEMETRY) as connection:
            connection.execute("SELECT 1 FROM events WHERE run_id = ? LIMIT 1", (run_id,)).fetchone()

    def duplicate_event_ids(self) -> tuple[str, ...]:
        with self._stores.connect(StoreRole.TELEMETRY) as connection:
            rows = connection.execute(
                "SELECT event_id FROM events GROUP BY event_id HAVING COUNT(*) > 1"
            ).fetchall()
        return tuple(row[0] for row in rows)

    def orphan_event_ids(self, known_runs: Iterable[str] = (), known_cases: Iterable[str] = ()) -> tuple[str, ...]:
        runs = set(known_runs)
        cases = set(known_cases)
        with self._stores.connect(StoreRole.TELEMETRY) as connection:
            rows = connection.execute("SELECT event_id, run_id, case_id FROM events").fetchall()
        return tuple(
            event_id for event_id, run_id, case_id in rows
            if not run_id or not case_id or (runs and run_id not in runs) or (cases and case_id not in cases)
        )

    def get_run_events(self, run_id: str) -> tuple[NormalizedEvent, ...]:
        with self._stores.connect(StoreRole.TELEMETRY) as connection:
            rows = connection.execute(
                "SELECT event_id, run_id, case_id, event_time, stage, event_type, actor_agent_id, "
                "target_agent_id, trace_id, span_id, parent_span_id, task_id, message_id, delegation_id, "
                "claim_id, action_id, protocol, protocol_version, outcome, error_class, payload_sha256, "
                "attributes_json FROM events WHERE run_id = ? ORDER BY event_time, event_id", (run_id,)
            ).fetchall()
        return tuple(_event_from_row(row) for row in rows)


def _event_from_row(row: tuple[object, ...]) -> NormalizedEvent:
    values = list(row)
    values[-1] = json.loads(str(values[-1]))
    return NormalizedEvent(*values)
