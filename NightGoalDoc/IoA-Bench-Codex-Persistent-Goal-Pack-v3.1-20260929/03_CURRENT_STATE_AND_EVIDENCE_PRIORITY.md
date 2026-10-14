# Current State & Evidence Priority

这是 2026-09-29 审计快照，不是永远正确的状态。

## 已知事实

- Phase A V2 曾在旧 source hash 上通过。
- 当前源码已经发生变化，因此需要 current-source re-anchoring。
- 审计没有发现必须整体推倒重开 Phase A 的新 P0 construct-validity 问题。
- 当前有 18 套 2.x Frozen Dataset，每套约90 case。
- T323 2.3.0 有 9 条 semantic conflict，不能直接视为 final accepted。
- 多数 2.x Dataset 的 validator provenance 不统一，部分使用了 `deepseek-v4.1-flash` 作为 secondary validator。
- T311 存在多个 formal run identity。
- T312/T313/T321/T322/T331/T332/T333 已有不同程度的正式结果。
- T331–T333 的磁盘结果与 campaign state 不一致。
- T341–T363 尚无当前可接受完整 formal result。
- formal CLI 已使用 construct dispatcher。
- Replay 内容主要内嵌于 results，发布闭环仍需加强。
- Phase C 尚无真实 18-suite complete campaign。
- Linux = NOT_VERIFIED，不是当前 Windows v1 的 required release gate。

## 事实优先级

当状态冲突时：

1. Frozen Dataset + Manifest + Hash
2. Run Manifest + Results + Replay
3. Source / Contract / Scorer / Prompt / Tool hashes
4. Gate artifacts
5. Derived Project/Campaign state
6. Narrative checkpoint / handoff

低层级文件不得覆盖高层级证据。

## 状态分类

对 Dataset / Pilot / Run 使用：

- ACCEPTED
- ACCEPTED_WITH_RECONCILIATION
- VALID_RESEARCH_RESULT
- VALID_BUT_DIFFERENT_BENCHMARK_RELEASE
- HOLD
- SUPERSEDED
- DEVELOPMENT_EXPLORATORY
- INVALIDATED
- ORPHAN_INCOMPLETE

“有效”与“canonical”必须分开。
