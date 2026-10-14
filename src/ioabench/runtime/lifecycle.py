"""Persisted run state machine backed by the control SQLite store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ioabench.core import RunState
from ioabench.storage.sqlite import LocalStores, StoreRole


_NEXT: dict[RunState, frozenset[RunState]] = {
    RunState.PENDING: frozenset({RunState.PREPARING, RunState.CANCELLED}),
    RunState.PREPARING: frozenset({RunState.READY, RunState.INVALID_RUN, RunState.FAILED}),
    RunState.READY: frozenset({RunState.RUNNING, RunState.CANCELLED}),
    RunState.RUNNING: frozenset({RunState.COLLECTING, RunState.RETRYABLE_INFRA_FAILURE, RunState.CANCELLED}),
    RunState.COLLECTING: frozenset({RunState.SCORING, RunState.INVALID_RUN}),
    RunState.SCORING: frozenset({RunState.VALIDATING, RunState.INVALID_RUN}),
    RunState.VALIDATING: frozenset({RunState.COMPLETED, RunState.INVALID_RUN}),
}


class SqliteRunLifecycle:
    def __init__(self, stores: LocalStores) -> None:
        self.stores = stores

    async def state(self, run_id: str) -> RunState:
        with self.stores.connect(StoreRole.CONTROL) as connection:
            row = connection.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RunState(row[0])

    async def transition(
        self,
        run_id: str,
        to_state: RunState,
        *,
        idempotency_key: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        with self.stores.connect(StoreRole.CONTROL) as connection:
            if connection.execute(
                "SELECT 1 FROM run_transitions WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone():
                return
            row = connection.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            current = RunState(row[0])
            if to_state not in _NEXT.get(current, frozenset()):
                raise ValueError(f"invalid run transition: {current} -> {to_state}")
            connection.execute(
                "INSERT INTO run_transitions(run_id, from_state, to_state, occurred_at, idempotency_key, detail_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id, current.value, to_state.value,
                    datetime.now(timezone.utc).isoformat(), idempotency_key,
                    json_detail(details),
                ),
            )
            connection.execute("UPDATE runs SET status = ? WHERE run_id = ?", (to_state.value, run_id))


def json_detail(details: Mapping[str, Any] | None) -> str:
    import json

    return json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
