# Strict Retry Contract v4

- `COMPLETED`: 正常终态。
- `INVALID_MODEL_OUTPUT`: 模型终态；记录；不计 safe；禁止重试。
- `RETRYABLE_INFRA_FAILURE`: 只有 `valid_model_behavior_observed == false` 且为明确 transient infra/provider failure 时允许有界 resume。
- `INFRA_INTERRUPTED`: 已产生 ≥1 条有效模型行为后发生 infra failure；终态；保留 partial evidence；禁止重试；进入 provider/interrupted denominator。
- `FAILED`: 非基础设施异常/代码 bug；终态；禁止自动重试。

Attempt provenance 至少记录：
run_id, suite_id, case_id, attempt_no, timestamps, status, error class/detail, model_records_produced, valid_model_behavior_observed, request/response hashes, actions/state refs, partial journal path/hash。

resume 永不覆盖历史 attempt。

科研 single-execution 语义：
一个 case 最多只有一个产生科研有效模型行为的 attempt；零行为 infra attempt 可有限重试；一旦已有有效行为，不再重新执行。
