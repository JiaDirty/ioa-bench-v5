# IoA-Bench — Persistent Research Goal v3.1

将当前工作区中的 IoA-Bench 持续推进到一个**可冻结、可复现、可审计、可支持多个被测模型完成全部 18 项测评的正式 Benchmark Release**，并完成可靠结果保存、正式 Campaign、Dashboard/Report/Replay 与最终科研验收。

这是一个**持续存在的 Goal**。每次本 Goal 再次出现时，都从当前工作区的真实状态继续；不得因为 Goal 被重新发送而重复初始化、重复已完成任务或从头开始。

当前工作区：`D:\Project\ioa_codex_spec`
本 Goal 的配套规范目录：
`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-Codex-Goal-Pack-v3.1-20260929`

每次继续本 Goal 时，应结合当前工作区状态，按需读取该目录中的配套规范。至少包括：

- `01_OUTCOME_AND_COMPLETION_CONTRACT.md`
- `02_FROZEN_RESEARCH_DECISIONS.md`
- `03_CURRENT_STATE_AND_EVIDENCE_PRIORITY.md`
- `04_BENCHMARK_STABILIZATION_PLAN.md`
- `05_DATASET_GOVERNANCE.md`
- `06_MODEL_AND_PROVIDER_PROTOCOL.md`
- `07_SYNTHETIC_HUMAN_PROTOCOL.md`
- `08_MULTI_MODEL_CAMPAIGN_PROTOCOL.md`
- `09_STATE_RECONCILIATION_AND_CHECKPOINTS.md`
- `10_SCIENTIFIC_GATES_AND_ACCEPTANCE.md`
- `11_WORK_QUEUE_OVERLAY_V3_1.yaml`
- `12_CHECKPOINT_TEMPLATE.md`

不要求每次 Goal 被重新发送时机械重读全部文件；应根据当前任务和已有上下文读取必要文档。但涉及研究边界、验收标准或当前任务状态时，应以这些配套文档和当前工作区证据为准。
若配套文档中的历史状态描述与当前工作区实际证据冲突，以当前可验证证据为准；但 `02_FROZEN_RESEARCH_DECISIONS.md` 中的用户研究决策、canonical taxonomy 和本 Goal 的科研约束不得被状态变化自动覆盖。

## Outcome

最终状态必须同时满足：

- 18 项 canonical IoA 测评均实现、验证并可正式执行；
- 18 套 Dataset 均通过统一质量标准并被冻结到一个明确的 Benchmark Dataset Pack；
- Runtime、Scorer、Prompt、Tool Schema、Replay、Manifest、Provider/Retry/Concurrency 规则均被冻结到一个版本化 Benchmark Release；
- T361–T363 使用明确、冻结的 model-based Synthetic Human protocol，并始终标记 `SIMULATION_ONLY`；
- Benchmark 可被多个用户选定的 Tested Model 在同一冻结 Benchmark Release 上公平执行；
- 每个 Frozen Case 对每个 Tested Model 正式执行 1 次有效运行；
- 已有历史 Dataset/Run 按科学有效性分类并保留，不因“旧”而自动废弃；
- 正式结果都能追溯到 Dataset、Source、Contract、Runtime、Scorer、Prompt、Tool、Model Profile、Replay 与 Run Manifest；
- Dashboard、Report、Case Drilldown、Reproducibility Bundle 只使用明确分类和可追溯证据；
- 最终科研验收能够明确区分：已确认、有效但属于不同 Benchmark Release、探索性、失效、未完成和仍有不确定性的结果。

## Verification surface

任何“完成”声明都必须由当前工作区中的实际证据证明，而不是仅由状态文件、总结文本或既有 PASS 标签证明。

优先使用：

- Frozen Dataset + Manifest + Hash；
- Source / Contract / Runtime / Scorer / Prompt / Tool Schema Hash；
- Tests / Gate artifacts；
- Pilot / Formal Run Manifest；
- Results / Replay / Checkpoint；
- State reconciliation output；
- Dashboard / Report / Reproducibility artifacts。

完成判断以 `10_SCIENTIFIC_GATES_AND_ACCEPTANCE.md` 中的最终 Gate 为准。

## Constraints

持续保持：

- 18 项 canonical taxonomy 与含义不变；
- 评估对象是模型在 IoA 场景中的内生安全行为，不是 Reference IoA 基础设施本身；
- Oracle / SUT / Telemetry 隔离；
- Ground Truth 程序化定义优先，AI 不得成为 truth 唯一权威；
- Safety 与 Task Utility 分离；
- Frozen Dataset 不原地修改；
- 无 benchmark leakage；
- 有效 unsafe 结果不得重跑到 safe；
- Provider / 网络故障与模型安全结果分离；
- T361–T363 永远 `SIMULATION_ONLY`；
- 不因缺数量而降低数据质量门槛；
- 历史科研资产保留并版本化，不静默覆盖。

## Boundaries

允许自主完成普通工程与研究实现，包括：

- Generator / Validator / Runtime / Scorer / Replay / Scheduler；
- Windows 调试；
- Provider adapter；
- AIHubMix capability probe；
- 辅助模型选择；
- 并发校准；
- Dataset 审计与必要的新版本生成；
- 状态自动重建；
- Dashboard / Report / Packaging。

需要用户决定的仅限：

- 修改 18 项 canonical 含义；
- 修改核心科研解释；
- 最终 Tested Model roster；
- 重大预算 / Provider 范围变化；
- 会改变 Benchmark 科研定义的重大方法变更。

## Iteration policy

每次 Goal 继续时：

1. 读取当前 Project State / Work Queue / Checkpoint 和相关证据；
2. 判断哪些 Gate 已经真正由证据满足；
3. 找到**依赖已满足但尚未通过的最早任务/Gate**；
4. 推进该项工作；
5. 每完成真实任务立即同步 Gate、State、Checkpoint、Changelog；
6. 如果状态文件与实际证据冲突，先做 reconciliation，不重复执行已完成工作；
7. 不以“重新跑一遍”代替证据审计；
8. 不以“有代码/有目录/有结果文件”代替科研验收。

具体执行规则以本 Goal Pack 的配套文档为准。

## Blocked stop condition

只有当没有任何可继续推进的工作，并且确实需要用户科研决策、凭证、预算或外部状态变化时，才报告 blocker。

普通 bug、测试失败、API 兼容问题、状态不一致、Windows 故障、Dataset 质量问题、Provider 限流都不是自动停下来的理由；应继续调查、修复或形成证据。

如果暂时不能完成整个长期目标，保持 Goal active，留下可恢复的证据化 Checkpoint，不得把部分进展重新定义为完成。

## Completion condition

只有当最终 Scientific Acceptance 明确证明：

- Benchmark Release 已冻结；
- 18 项 Dataset/Runtime/Scorer/Replay/Manifest 全部通过；
- 所有用户选定 Tested Model 的目标 Campaign 已完成或被用户明确排除；
- 结果、Dashboard、Report、Reproducibility Bundle 可追溯且一致；
- 所有已知科研限制被明确披露；

才可以将本 Goal 视为完成。
