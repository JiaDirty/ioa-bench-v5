"""Bounded retry policy for transient provider failures."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from ioabench.errors import ProviderTransientError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry policy values must be non-negative and max_attempts must be positive")

    def delay(self, attempt: int) -> float:
        return min(self.max_delay_seconds, self.base_delay_seconds * (2 ** max(0, attempt - 1)))


async def run_with_retry(
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[T, int]:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation(), attempt
        except ProviderTransientError:
            if attempt == policy.max_attempts:
                raise
            await sleep(policy.delay(attempt))
    raise AssertionError("retry loop is unreachable")
