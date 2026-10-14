# Model & Provider Protocol

## AIHubMix 文档

用户已把 AIHubMix 文档爬取到本地。

需要确认模型参数、能力、限流或 endpoint 时：
- 优先读取本地文档；
- 再做小规模 capability probe；
- 文档与实际行为不一致时，记录 discrepancy。

## 辅助模型选择

可自主选择：
- Generator；
- Validator A；
- Validator B；
- Arbitrator；
- Synthetic Human Model。

比较：

- semantic quality；
- structured output；
- tool calling；
- context/output limit；
- median/P95 latency；
- timeout；
- 429/5xx；
- cost；
- agreement/stability。

输出版本化选择 artifact。

## Tested Model Profile

对每个 Tested Model 记录：

- exact model ID；
- provider；
- endpoint family；
- sampling fields；
- temperature；
- top_p if supported；
- max output tokens；
- tool calling；
- response format；
- reasoning fields；
- timeout；
- retry；
- base prompt hash。

同一 Model Campaign 内基础 profile 固定。

## Concurrency

开发阶段阶梯测试，例如：

1 → 2 → 3 → 4 → 6 → ...

记录：
- success rate；
- 429；
- timeout；
- mean/P95 latency；
- throughput。

正式 Campaign前冻结确定的 scheduler profile。

目标是稳定吞吐最高，不是并发数字最大。

## Provider failure

严格区分：

- infrastructure/provider failure；
- invalid model output；
- valid model unsafe/safe outcome。

只有未形成有效模型行为的基础设施失败可以按冻结策略 retry。
