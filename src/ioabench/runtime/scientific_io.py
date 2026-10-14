"""Immutable tested-agent requests and record snapshots for new construct runs."""
from __future__ import annotations

from copy import deepcopy
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelRequest, ModelResponse
from ioabench.sandbox import ActionBudget


class InvalidModelOutput(ValueError):
    pass


class ProtocolViolation(RuntimeError):
    """Construction/contract violation that must never be retried as infrastructure."""


@dataclass
class TestedAgentSession:
    agent_id: str
    organization: str
    role: str
    prompt: str
    permitted_tools: tuple[str, ...]
    budget: ActionBudget
    messages: list[dict[str, Any]] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.messages:
            self.messages = [{"role": "system", "content": self.prompt}]

    def request(self, tools: tuple[Mapping[str, Any], ...], parameters: Mapping[str, Any]) -> ModelRequest:
        names = {item["function"]["name"] for item in tools}
        if not names <= set(self.permitted_tools):
            raise ValueError("tool permissions do not match agent role")
        self.budget.consume_round()
        self.budget.consume_model_call()
        return ModelRequest(tuple(deepcopy(self.messages)), deepcopy(dict(parameters)), tuple(deepcopy(tools)),
                            {"agent_id": self.agent_id, "role": self.role, "organization": self.organization})


def record_model_io(session: TestedAgentSession, request_snapshot: Mapping[str, Any], response: ModelResponse) -> dict[str, Any]:
    snapshot = deepcopy(dict(request_snapshot))
    record = {"agent_id": session.agent_id, "request": snapshot, "request_sha256": canonical_sha256(snapshot),
              "response": {"text": response.text, "tool_calls": deepcopy(list(response.tool_calls)),
                           "finish_reason": response.finish_reason, "model_id": response.model_id,
                           "usage": deepcopy(dict(response.usage)), "provider_metadata": deepcopy(dict(response.provider_metadata))}}
    # Strict-retry evidence retention: an attempt that is interrupted by an
    # infrastructure failure after this point must leave the record behind, so
    # the case can never be silently re-executed as if it had produced nothing.
    active = AttemptJournal.current()
    if active is not None:
        active.record(record)
    return record


def require_effective_output(response: ModelResponse) -> None:
    if response.finish_reason == "length" or not ((response.text or "").strip() or response.tool_calls or response.structured):
        raise InvalidModelOutput("truncated or empty cooperating agent output")


class AttemptJournal:
    """Append-only per-attempt evidence journal, one line per model record.

    Writes are flushed and fsynced at record granularity so that a process that
    dies mid-attempt still leaves every already-produced model record on disk.
    Attempts are never overwritten: a later attempt appends a new file.
    """

    _active: ContextVar["AttemptJournal | None"] = ContextVar(
        "ioabench_attempt_journal", default=None)

    def __init__(self, root: Path, run_id: str, suite: str, case_id: str, attempt_no: int) -> None:
        self.root = Path(root)
        self.run_id = run_id
        self.suite = suite
        self.case_id = case_id
        self.attempt_no = attempt_no
        self.records = 0
        self.directory = self.root / "data" / "runs" / run_id / "attempts" / case_id
        self.path = self.directory / f"attempt-{attempt_no}.jsonl"

    # ---- context management -------------------------------------------------
    def __enter__(self) -> "AttemptJournal":
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(f"attempt journal already exists: {self.path}")
        # create exclusively and leave a header line carrying the identity
        header = {"kind": "attempt", "run_id": self.run_id, "suite_id": self.suite,
                  "case_id": self.case_id, "attempt_no": self.attempt_no}
        with self.path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(header, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._active_token: Token[AttemptJournal | None] = AttemptJournal._active.set(self)
        return self

    def __exit__(self, *_exc) -> None:
        AttemptJournal._active.reset(self._active_token)

    @classmethod
    def current(cls) -> "AttemptJournal | None":
        return cls._active.get()

    # ---- recording ----------------------------------------------------------
    def record(self, record: Mapping[str, Any]) -> None:
        entry = {"kind": "model_record", "record": dict(record),
                 "record_sha256": canonical_sha256(dict(record))}
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.records += 1

    # ---- evidence -----------------------------------------------------------
    def partial_evidence(self) -> dict[str, Any]:
        """Describe what this attempt already produced, so an interruption is
        never mistaken for 'no model behaviour observed'."""
        observed = self.records >= 1
        return {"attempt_no": self.attempt_no,
                "attempt_journal": {"path": self.path.relative_to(self.root).as_posix(),
                                    "sha256": _file_sha256(self.path)} if self.path.exists() else None,
                "model_records_produced": self.records,
                "valid_model_behavior_observed": observed}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def attempt_counter(root: Path, run_id: str, case_id: str) -> int:
    """Next attempt number for a case; existing attempts are never reused."""
    directory = Path(root) / "data" / "runs" / run_id / "attempts" / case_id
    if not directory.is_dir():
        return 1
    numbers = []
    for item in directory.glob("attempt-*.jsonl"):
        try:
            numbers.append(int(item.stem.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return (max(numbers) + 1) if numbers else 1


__all__ = ["AttemptJournal", "InvalidModelOutput", "ProtocolViolation",
           "TestedAgentSession", "attempt_counter", "record_model_io",
           "require_effective_output", "uuid4"]

