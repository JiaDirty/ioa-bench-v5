"""Control-store implementation of the declared RunRepository port."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .stores import LocalStores, StoreRole


class SqliteRunRepository:
    def __init__(self, stores: LocalStores) -> None:
        self._stores = stores

    async def put_manifest(self, manifest: Mapping[str, Any]) -> None:
        payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._stores.connect(StoreRole.CONTROL) as connection:
            connection.execute(
                "INSERT INTO runs(run_id, experiment_id, test_id, case_id, condition_name, "
                "repetition, status, manifest_json, manifest_sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    manifest["run_id"], manifest["experiment_id"], manifest["test_id"],
                    manifest["case_id"], manifest["condition_name"],
                    manifest.get("repetition", 1), "PENDING", payload, digest,
                ),
            )

    async def get_manifest(self, run_id: str) -> Mapping[str, Any] | None:
        with self._stores.connect(StoreRole.CONTROL) as connection:
            row = connection.execute(
                "SELECT manifest_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    async def update_status(self, run_id: str, status: str, *, idempotency_key: str) -> None:
        with self._stores.connect(StoreRole.CONTROL) as connection:
            if connection.execute(
                "SELECT 1 FROM run_transitions WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone():
                return
            row = connection.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            connection.execute(
                "INSERT INTO run_transitions(run_id, from_state, to_state, occurred_at, idempotency_key) "
                "VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)",
                (run_id, row[0], status, idempotency_key),
            )
            connection.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))
