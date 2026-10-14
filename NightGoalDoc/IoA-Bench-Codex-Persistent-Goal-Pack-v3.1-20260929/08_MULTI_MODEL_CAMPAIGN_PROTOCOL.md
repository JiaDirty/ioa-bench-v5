# Multi-Model Formal Campaign Protocol

## Benchmark Release 与 Model Campaign 分开

### Benchmark Release
固定：
- 18 datasets；
- Contracts；
- Runtime；
- Scorers；
- Prompts；
- Tools；
- Retry；
- Replay；
- Synthetic Human protocol；
- Scheduler rules。

### Model Campaign
每个 Tested Model独立：
- Model Profile；
- 18-suite Run Manifest；
- Results；
- Replay；
- cost/latency；
- Campaign Manifest。

## Campaign 前置条件

一个新的完整 Model Campaign 只有在：

- 18/18 Dataset accepted；
- 18/18 representative dry-run PASS；
- Benchmark Release frozen；
- Model capability/profile frozen；
- Scheduler profile frozen；
- no unresolved P0 scientific issue；

后才能开始。

## 正式执行

一个 Tested Model：

T311 → … → T363 可物理串行执行。

每个 Frozen Case：
- 正式有效执行1次；
- 多 Agent case允许多个模型调用；
- provider failure可bounded retry；
- valid outcome不可重跑到想要的结果。

## 运行中发现问题

### 基础设施问题
timeout / 429 / 5xx / network
且未形成有效模型行为：
可以 retry。

### 科研语义问题
Dataset / Truth / Runtime / Scorer / Prompt / Tool / Oracle：
停止受影响范围；
版本化修复；
impact analysis；
只使受影响结果失效。

## 现有结果

已有 DeepSeek 等结果逐 Run 审计：

- VALID_RESEARCH_RESULT
- VALID_BUT_DIFFERENT_BENCHMARK_RELEASE
- DEVELOPMENT_EXPLORATORY
- INVALIDATED
- ORPHAN_INCOMPLETE

有效旧结果永久保存。

是否进入某个未来 Campaign aggregation，由 compatibility 决定。
