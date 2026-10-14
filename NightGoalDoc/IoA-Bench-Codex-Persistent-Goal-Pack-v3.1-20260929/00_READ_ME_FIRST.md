# IoA-Bench Codex Goal Pack v3.1

本包基于两类依据重新制作：

1. 当前 IoA-Bench 项目事实与 2026-09-29 只读审计；
2. Codex 官方 Goals 使用说明。

这版与 v3 的最大差别：

- **主 Goal 更短、更像真正的 Goal 完成合同**；
- 详细执行方法全部放到配套文档；
- 主 Goal 明确“每次收到都从当前证据状态继续，不重新初始化”；
- 完成条件完全证据化；
- 明确区分“长期目标”和“下一步动作”；
- 不再把大量一次性执行顺序塞进主 Goal。

## 使用方法

建议复制到：

`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-Codex-Goal-Pack-v3.1-20260929`

在 Codex / Zcode Goal 中直接使用：

`GOAL_PROMPT_REENTRANT_V3_1.md`

这个 Goal 可以被系统周期性原样重新发送。

每次重新收到时，Codex/Zcode 应：

- 从当前工作区事实继续；
- 不重复已经通过的 Gate；
- 不重新生成已接受的 Dataset；
- 不重新执行已证明有效且无需重跑的 Run；
- 只推进当前尚未满足的完成条件。

## 配套文档

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

主 Goal 只规定：
- 最终要达到什么；
- 用什么证据证明；
- 哪些边界不能破坏；
- 每次迭代怎么继续；
- 什么情况才允许停下来要求用户决定。

具体怎么做，以配套文档和当前工作区证据为准。
