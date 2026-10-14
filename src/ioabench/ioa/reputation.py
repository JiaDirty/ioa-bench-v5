"""Reputation observations with explicit local/global scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReputationEvent:
    agent_id: str
    delta: float
    scope: str
    source: str
    metadata: dict[str, Any]


class ReputationStore:
    def __init__(self) -> None:
        self._values: dict[tuple[str, str], float] = {}
        self._events: list[ReputationEvent] = []

    def record(self, event: ReputationEvent) -> None:
        key = (event.scope, event.agent_id)
        self._values[key] = self._values.get(key, 0.0) + event.delta
        self._events.append(event)

    def value(self, agent_id: str, scope: str = "global") -> float:
        return self._values.get((scope, agent_id), 0.0)

    def events(self, agent_id: str | None = None) -> tuple[ReputationEvent, ...]:
        return tuple(event for event in self._events if agent_id is None or event.agent_id == agent_id)
