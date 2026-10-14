"""Finite action budgets for bounded local runs."""

from __future__ import annotations

from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    """A case exceeded one of its declared action budgets."""


@dataclass
class ActionBudget:
    max_rounds: int
    max_model_calls: int
    max_peer_messages: int
    max_tool_calls: int
    rounds: int = 0
    model_calls: int = 0
    peer_messages: int = 0
    tool_calls: int = 0

    def _consume(self, name: str, limit: int) -> None:
        value = getattr(self, name) + 1
        if value > limit:
            raise BudgetExceeded(f"{name} budget exceeded: {value}>{limit}")
        setattr(self, name, value)

    def consume_round(self) -> None:
        self._consume("rounds", self.max_rounds)

    def consume_model_call(self) -> None:
        self._consume("model_calls", self.max_model_calls)

    def consume_peer_message(self) -> None:
        self._consume("peer_messages", self.max_peer_messages)

    def consume_tool_call(self) -> None:
        self._consume("tool_calls", self.max_tool_calls)
