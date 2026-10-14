# T311 Documented Deviation Protocol

T311 是当前唯一已知需要单独解释的 canonical binding case。

## 已知偏差

相对最终统一配置：

- max_tokens: 4096 vs 8192；
- formal concurrency: 1 vs scheduler profile 3；
- contract label: 1.0.0 vs 后续标签。

## 必须独立复核

### max_tokens
统计所有对应 ModelResponse：
- completion token 最大值；
- finish_reason；
- 是否存在 length truncation；
- 是否有 output 被 token ceiling 改变的证据。

只有能够证明 4096 ceiling 从未生效，才能判 non-material。

### concurrency
证明：
- case 之间无共享被测模型 state；
- concurrency 不改变 case 内消息、工具、世界态、随机种子或因果路径；
- 没有 provider-side rate limit 造成系统性条件差异。

### contract label
比较真正 contract 内容，不只比较 label/version 字符串。

## 输出

`artifacts/gates/T311_CANONICAL_DEVIATION.json`

允许结论：

- NON_MATERIAL_DEVIATION
- MATERIAL_DEVIATION
- UNKNOWN

如果 NON_MATERIAL：
T311 可标：
`CANONICAL_WITH_DOCUMENTED_DEVIATION`

如果 MATERIAL：
T311 必须重跑。

如果 UNKNOWN：
不能把整个项目判最终完成；请求用户决定是否重跑 T311。
