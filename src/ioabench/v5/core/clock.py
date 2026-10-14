"""Logical clock for the dynamic IoA world (dynamic-world phase M2, DW-021).

Episode-relative time: the engine's turn counter is the single clock. Validity windows
(grants, exceptions, TTLs) and deadlines are decided by deterministic inclusive comparison at
action time, so replay reproduces every time-dependent decision (02_RUNTIME §6 item 8).
Suites keep their ISO-date worlds; this component is for worlds that need in-episode time
(multi-round horizons, mid-episode corrections, deadline pressure) without wall-clock noise.
"""
from __future__ import annotations

from typing import Any

CLOCK_VERSION = "v5-logical-clock-1.0.0"


class LogicalClock:
    """Turn-based clock. ``now`` is advanced by the engine; components read, never write."""

    VERSION = CLOCK_VERSION

    def __init__(self) -> None:
        self._now = 0

    @property
    def now(self) -> int:
        return self._now

    def advance(self, to: int) -> None:
        if to < self._now:
            raise ValueError(f"clock cannot move backwards: {to} < {self._now}")
        self._now = to

    def within(self, window: tuple[int | None, int | None], *, at: int | None = None) -> bool:
        """Inclusive validity check against a (valid_from, valid_until) window; None = open."""
        start, end = window
        current = self._now if at is None else at
        if start is not None and current < start:
            return False
        if end is not None and current > end:
            return False
        return True

    def deadline_passed(self, deadline: int, *, at: int | None = None) -> bool:
        current = self._now if at is None else at
        return current > deadline

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.VERSION, "now": self._now}
