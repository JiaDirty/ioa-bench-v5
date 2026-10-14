"""Deterministic task routing with visible candidate-selection evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .registry import AgentRecord, LocalRegistry


@dataclass(frozen=True)
class RoutedCandidate:
    record: AgentRecord
    score: int
    rationale: tuple[str, ...]


class TaskRouter:
    def __init__(self, registry: LocalRegistry, telemetry: Callable[[Mapping[str, Any]], None] | None = None) -> None:
        self.registry = registry
        self._telemetry = telemetry

    def select(self, task: Mapping[str, Any]) -> tuple[RoutedCandidate, ...]:
        required = frozenset(task.get("capabilities", ()))
        requested_org = task.get("org_id")
        discovery = self.registry.discover({"capabilities": required, "org_id": requested_org} if requested_org else {"capabilities": required})
        candidates = tuple(RoutedCandidate(item.record, item.score, item.evidence) for item in discovery)
        self._emit({
            "event_type": "agent.router.selection",
            "task_id": task.get("task_id"),
            "candidate_ids": [item.record.agent_id for item in candidates],
            "rationales": [list(item.rationale) for item in candidates],
        })
        return candidates

    def choose(self, task: Mapping[str, Any]) -> RoutedCandidate | None:
        candidates = self.select(task)
        return candidates[0] if candidates else None

    def _emit(self, event: Mapping[str, Any]) -> None:
        if self._telemetry is not None:
            self._telemetry(event)
