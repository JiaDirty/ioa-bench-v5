"""Local and global utility signals kept separate from safety scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IncentiveSignal:
    recipient_id: str
    amount: float
    scope: str
    reason: str
    metadata: dict[str, Any]


class IncentiveLedger:
    def __init__(self) -> None:
        self._signals: list[IncentiveSignal] = []

    def add(self, signal: IncentiveSignal) -> None:
        self._signals.append(signal)

    def utility(self, recipient_id: str, scope: str = "global") -> float:
        return sum(signal.amount for signal in self._signals if signal.recipient_id == recipient_id and signal.scope == scope)

    def signals(self, recipient_id: str | None = None) -> tuple[IncentiveSignal, ...]:
        return tuple(signal for signal in self._signals if recipient_id is None or signal.recipient_id == recipient_id)
