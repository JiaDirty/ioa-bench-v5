# Final Delivery Contract

最终交付不是单个 ZIP，而是一套**可以被科研复核的 Benchmark 状态**。

## 最终交付应至少包含

### Scientific definition
- 18 项 taxonomy / contracts
- benchmark methodology
- dataset governance
- scoring definitions
- model/provider profile
- SIMULATION_ONLY disclosure

### Executable benchmark
- source/runtime
- configuration
- environment/dependency instructions
- one-command or clearly documented execution path
- tests / validators

### Dataset
- authoritative pack
- versions / hashes
- manifests
- validation evidence
- rejected provenance where required

### Frozen release
- release manifest
- source/config/contract/prompt/tool/scorer/runtime/model/scheduler provenance
- supersedes/version history

### Formal campaign evidence
- canonical Run IDs
- per-run manifests
- results
- Replay
- attempts / provider failures / invalid outputs
- post-run validation

### Acceptance
- per-suite acceptance
- binding/provenance audit
- canonical aggregation
- final project acceptance

### Human-readable outputs
- report
- dashboard
- limitations/deviations
- reproducibility guide

### Integrity
- inventory
- SHA-256
- ZIP CRC or equivalent archive verification
- secret scan
- no secret in Goal/log/replay/manifest/delivery

## Final self-audit

在宣布 Goal 完成前，Codex 应从最终目标反向审计：

> 如果另一个研究者拿到最终交付，他能否知道“测了什么、用什么数据和代码、怎样运行、哪次正式实验产生这些结果、结果怎样评分、哪些是限制、哪些是模拟、文件是否被篡改”？

如果答案不是清楚的 YES，则 Goal 还没有完成。
