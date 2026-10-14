import asyncio

import pytest

from ioabench.errors import ProviderTransientError
from ioabench.models.retry import RetryPolicy, run_with_retry


def test_retry_is_bounded_and_records_attempt_count() -> None:
    calls = 0
    delays = []

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ProviderTransientError("temporary")
        return "ok"

    async def sleep(delay: float) -> None:
        delays.append(delay)

    result, attempts = asyncio.run(run_with_retry(operation, RetryPolicy(3, 0.1, 0.15), sleep=sleep))
    assert (result, attempts) == ("ok", 3)
    assert delays == [0.1, 0.15]


def test_retry_raises_after_max_attempts() -> None:
    async def operation() -> str:
        raise ProviderTransientError("temporary")

    with pytest.raises(ProviderTransientError):
        asyncio.run(run_with_retry(operation, RetryPolicy(2, 0, 0), sleep=asyncio.sleep))
