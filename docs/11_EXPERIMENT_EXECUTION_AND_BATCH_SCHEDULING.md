# 11 — Experiment Execution and Batch Scheduling

## 1. Command objective

A canonical run should be possible with an interface equivalent to:

`ioabench run --model deepseek-v4.1-flash --suite all --profile local-v1`

Exact CLI syntax may evolve, but one-command full-suite execution is a v1 acceptance requirement.

## 2. Run expansion

Expand a benchmark request into immutable work units:
`model × suite × dataset_version × case × condition × repetition`.

v1 repetition default is 1. Each work unit has a deterministic work id and checkpoint state.

## 3. State machine

`PENDING -> PREPARING -> READY -> RUNNING -> COLLECTING -> SCORING -> VALIDATING -> COMPLETED`

Error/terminal states:
`RETRYABLE_INFRA_FAILURE`, `INVALID_RUN`, `UNSUPPORTED`, `FAILED`, `CANCELLED`.

## 4. Resume

The scheduler MUST persist state after each durable phase. Restarting the computer/process must resume only incomplete/retryable work. Completed frozen work units are not rerun unless explicitly invalidated.

## 5. Failure taxonomy

Separate:
- model unsafe behavior;
- task failure/refusal;
- benchmark invalidity;
- provider/API/infrastructure failure;
- unsupported model capability.

Only valid behavioral runs enter safety statistics.

## 6. Action budgets

Each case defines max rounds, model calls, peer messages and tool calls. Exceeding budget produces task/efficiency outcome according to suite rules; never allow unbounded loops.

## 7. Local concurrency

Default conservative concurrency must protect a single workstation and provider quotas. Concurrency, rate limits and provider backoff are configurable. Formal run manifest records concurrency settings, but concurrency must not change scenario semantics.

## 8. Checkpoint artifacts

Persist after each case:
- final SUT state snapshot/hash;
- telemetry completeness result;
- replay manifest;
- score input bundle;
- provider errors/retries;
- utility result.

## 9. Cancellation/kill path

Stop new work, cancel active agent loops, disarm exposure controllers, stop sandbox mutation, flush telemetry, persist partial evidence, mark affected work cancelled/invalid and release local resources.
