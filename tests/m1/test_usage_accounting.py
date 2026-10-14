from time import perf_counter

from ioabench.models.usage import UsageRecord


def test_usage_records_tokens_latency_and_provider_failure_separately() -> None:
    started = perf_counter() - 0.01
    success = UsageRecord.from_response("model", started, {"prompt_tokens": 2, "completion_tokens": 3}, retries=1)
    failure = UsageRecord.failure("model", started, "ProviderTransientError", retries=2)

    assert success.total_tokens == 5
    assert success.retries == 1
    assert success.latency_seconds >= 0
    assert failure.status == "PROVIDER_FAILURE"
    assert failure.error_class == "ProviderTransientError"
