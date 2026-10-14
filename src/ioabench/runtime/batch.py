"""Small bounded batch runner with durable per-work-unit resume state."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import time
from typing import Any, Awaitable, Callable, Mapping
from uuid import uuid4

from .scheduler import WorkUnit


Executor = Callable[[WorkUnit], Mapping[str, Any] | Awaitable[Mapping[str, Any]]]

# Strict retry contract: these statuses are scientific/publication terminal.
# Only RETRYABLE_INFRA_FAILURE (zero valid model behaviour observed) may be
# re-queued by a later resume pass.
TERMINAL_STATUSES = frozenset({
    "COMPLETED", "INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED",
    "BUDGET_EXCEEDED",
    "INVALID_RUN", "UNSUPPORTED", "FAILED", "CANCELLED",
})
RESUMABLE_STATUSES = frozenset({"RETRYABLE_INFRA_FAILURE"})


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class BatchRunner:
    def __init__(self, state_path: str | Path, *, concurrency: int = 1) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self.state_path = Path(state_path)
        self.concurrency = concurrency

    @staticmethod
    def _attempt_no(entry: Mapping[str, Any]) -> int:
        attempts = entry.get("attempts")
        return len(attempts) if isinstance(attempts, list) else 0

    @staticmethod
    def _next_attempt_no(entry: Mapping[str, Any]) -> int:
        attempts = entry.get("attempts")
        if not isinstance(attempts, list):
            return 1
        numbers = [a.get("attempt_no", 0) for a in attempts if isinstance(a, Mapping)]
        return (max(numbers) if numbers else 0) + 1

    def is_resumable(self, entry: Mapping[str, Any]) -> bool:
        """A unit is re-queued only when its last attempt is a spec-clean
        zero-behaviour infrastructure failure. Everything else is terminal."""
        status = entry.get("status")
        if status in TERMINAL_STATUSES:
            return False
        if status not in RESUMABLE_STATUSES:
            return False
        if entry.get("valid_model_behavior_observed") is True:
            return False
        if int(entry.get("model_records_produced") or 0) > 0:
            return False
        if entry.get("infrastructure_failure") is not True:
            return False
        return True

    def run(self, units: tuple[WorkUnit, ...], execute: Executor, *, resume: bool = True) -> dict[str, dict[str, Any]]:
        state = self._load() if resume else {}
        self._recover_stale_running(state)
        pending = [unit for unit in units
                   if not (state.get(unit.work_id) and (state[unit.work_id].get("status") in TERMINAL_STATUSES
                                                        or not self.is_resumable(state[unit.work_id])))]
        try:
            asyncio.run(self._run_pending(pending, execute, state))
        except KeyboardInterrupt:
            for unit in pending:
                if state.get(unit.work_id, {}).get("status") == "RUNNING":
                    state[unit.work_id] = {"status": "CANCELLED", "attempts": state[unit.work_id].get("attempts", [])}
            self._save(state)
            raise
        return state

    def _recover_stale_running(self, state: dict[str, dict[str, Any]]) -> None:
        """Classify a checkpoint left behind by a killed worker before re-queueing."""
        changed = False
        for work_id, entry in state.items():
            if entry.get("status") != "RUNNING":
                continue
            changed = True
            case_id = str(entry.get("case_id") or work_id)
            attempt_dir = self.state_path.parent / "attempts" / case_id
            journals = sorted(attempt_dir.glob("attempt-*.jsonl")) if attempt_dir.is_dir() else []
            journal = journals[-1] if journals else None
            records = 0
            if journal is not None:
                try:
                    for line in journal.read_text(encoding="utf-8").splitlines():
                        if json.loads(line).get("kind") == "model_record":
                            records += 1
                except (OSError, ValueError, json.JSONDecodeError):
                    journal = None
                    records = 0
            if journal is not None and records:
                digest = hashlib.sha256(journal.read_bytes()).hexdigest()
                try:
                    journal_path = journal.relative_to(Path.cwd()).as_posix()
                except ValueError:
                    journal_path = str(journal)
                attempt_no = int(journal.stem.rsplit("-", 1)[-1])
                attempt = {"attempt_no": attempt_no,
                           "status": "INFRA_INTERRUPTED", "model_records_produced": records,
                           "valid_model_behavior_observed": True, "infrastructure_failure": True,
                           "attempt_journal": {"path": journal_path,
                                               "sha256": digest}}
                state[work_id] = {**entry, "status": "INFRA_INTERRUPTED",
                                  "model_records_produced": records,
                                  "valid_model_behavior_observed": True,
                                  "infrastructure_failure": True,
                                  "partial_evidence_retained": True,
                                  "attempts": [*(entry.get("attempts") or []), attempt]}
            else:
                state[work_id] = {**entry, "status": "RETRYABLE_INFRA_FAILURE",
                                  "model_records_produced": 0,
                                  "valid_model_behavior_observed": False,
                                  "infrastructure_failure": True}
        if changed:
            self._save(state)

    async def _run_pending(self, units: list[WorkUnit], execute: Executor, state: dict[str, dict[str, Any]]) -> None:
        semaphore = asyncio.Semaphore(self.concurrency)
        save_lock = asyncio.Lock()

        async def save_state() -> None:
            async with save_lock:
                self._save(state)

        async def one(unit: WorkUnit) -> None:
            async with semaphore:
                entry = dict(state.get(unit.work_id) or {})
                previous = entry.get("attempts") if isinstance(entry.get("attempts"), list) else []
                attempt_no = BatchRunner._next_attempt_no(entry)
                started = _now()
                entry.update({"status": "RUNNING", "suite": unit.suite, "case_id": unit.case_id})
                state[unit.work_id] = entry
                await save_state()
                try:
                    result = execute(unit)
                    if inspect.isawaitable(result):
                        result = await result
                    value = dict(result)
                    status = value.get("status", "COMPLETED")
                    model_records = max(
                        int(value.get("model_records_produced") or 0),
                        _records_of(value),
                    )
                    record = {"attempt_no": attempt_no, "started_utc": started, "ended_utc": _now(),
                              "status": status,
                              "error_class": None, "error_detail": None,
                              "model_records_produced": model_records,
                              "valid_model_behavior_observed": status == "COMPLETED"
                              or value.get("valid_model_behavior_observed") is True,
                              "infrastructure_failure": value.get("infrastructure_failure") is True,
                              "attempt_journal": value.get("attempt_journal")}
                    state[unit.work_id] = {**value, "status": status, "suite": unit.suite,
                                           "case_id": unit.case_id, "attempts": [*previous, record]}
                except Exception as exc:  # classification happens in the dispatcher
                    record = {"attempt_no": attempt_no, "started_utc": started, "ended_utc": _now(),
                              # Exceptions escaping the strict dispatcher are not
                              # classified infrastructure failures and must be
                              # terminal rather than a misleading retry marker.
                              "status": "FAILED",
                              "error_class": type(exc).__name__, "error_detail": str(exc),
                              "model_records_produced": 0, "valid_model_behavior_observed": False,
                              "infrastructure_failure": False, "attempt_journal": None}
                    state[unit.work_id] = {"status": "FAILED", "error": type(exc).__name__,
                                           "detail": str(exc), "suite": unit.suite, "case_id": unit.case_id,
                                           "model_records_produced": 0, "valid_model_behavior_observed": False,
                                           "infrastructure_failure": False,
                                           "attempts": [*previous, record]}
                await save_state()

        await asyncio.gather(*(one(unit) for unit in units))

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.state_path.exists():
            return {}
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("batch checkpoint must be an object")
        return {str(key): dict(item) for key, item in value.items() if isinstance(item, dict)}

    def _save(self, state: Mapping[str, Mapping[str, Any]]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(f".{self.state_path.name}.{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        try:
            os.replace(temporary, self.state_path)
        finally:
            temporary.unlink(missing_ok=True)


def _records_of(value: Mapping[str, Any]) -> int:
    replay = value.get("replay")
    if isinstance(replay, Mapping):
        records = replay.get("model_records")
        if isinstance(records, list):
            return len(records)
    records = value.get("model_records")
    return len(records) if isinstance(records, list) else 0

