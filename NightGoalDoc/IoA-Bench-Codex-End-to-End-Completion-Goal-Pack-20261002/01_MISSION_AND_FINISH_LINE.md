# Mission & Finish Line

## Mission

把 IoA-Bench 从“已经有大量实现、数据、历史运行和审计材料的研究工程”，推进成一个真正可作为科研 Benchmark 使用和交付的最终系统。

Codex 的职责不是完成某一轮补丁，也不是让某个 Gate 变绿，而是负责让整个系统最终达到：

`18项定义清楚 → 实现可运行 → 数据可信 → 运行时稳定 → 科学版本冻结 → 正式实验完成 → 结果可追溯 → 验收成立 → 报告与交付完整`

## Canonical scope

18 项 canonical risk：

- T311 资格伪装 / Qualification Spoofing
- T312 注册失真 / Registry Distortion
- T313 代表资格漂移 / Representation/Delegation Drift
- T321 协商污染 / Negotiation Pollution
- T322 互操作失配 / Interoperability Mismatch
- T323 责任链断裂 / Accountability Chain Break
- T331 跨系统级联扩散 / Cross-System Cascade
- T332 结构暴露 / Structural Exposure
- T333 行为推断 / Behavioral Inference
- T341 生态错误共识 / Ecosystem False Consensus
- T342 谣言扩散 / Rumor Propagation
- T343 规范漂移 / Norm Drift
- T351 激励错配 / Incentive Misalignment
- T352 声誉垄断 / Reputation Monopoly
- T353 节点操纵 / Node Manipulation
- T361 判断让渡 / Judgment Delegation
- T362 讨论扭曲 / Discussion Distortion
- T363 能动性弱化 / Agency Weakening

这些是研究对象，不是普通 feature list。

## High-level lifecycle

Codex 可以自主改变具体路径，但最终生命周期应覆盖这些能力层：

1. **Reconcile**：从当前工作区真实证据理解现在做到哪；
2. **Build/Stabilize**：补齐、修复、重构必要实现；
3. **Verify**：以测试、mock、replay、hash、contract 等证明实现可靠；
4. **Freeze**：建立科学一致、可复现的正式版本边界；
5. **Run**：执行被授权的正式 Benchmark Campaign；
6. **Validate**：逐 suite 检查结果、provenance、replay、scoring 与异常；
7. **Aggregate**：只聚合真正 canonical 的结果；
8. **Deliver**：生成科研报告、Dashboard、复现材料、清单和最终交付包。

这些不是必须机械依次执行的 checklist；Codex 应根据当前状态选择最高价值的下一步。

## Finish line

最终完成不是“程序能跑”，也不是“18 个目录都存在”。

最终完成意味着：

- 18/18 canonical 测评均达到项目定义的正式验收标准；
- authoritative datasets、runtime、scorers、prompts、tools、model profiles 和 releases 有明确版本关系；
- 正式结果可从输入到行为、Replay、评分、聚合完整追溯；
- 报告中 Safety、Task Utility、异常、限制和 `SIMULATION_ONLY` 均诚实呈现；
- 最终交付可由第三方根据材料复核；
- 不存在仍然会改变 canonical 解释的 required blocker。
