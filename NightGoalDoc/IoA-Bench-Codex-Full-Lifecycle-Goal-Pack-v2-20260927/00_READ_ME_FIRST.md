# IoA-Bench Codex Full-Lifecycle Goal Pack v2

本包基于 2026-09-27 最新源码快照与历史 Goal 会话重新制定，**替代此前 NightGoalDoc 中旧版 Full-Lifecycle Goal Pack 的执行口径**。

## 使用方式

把本目录复制到：

`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-Codex-Full-Lifecycle-Goal-Pack-v2`

然后在新的 Codex Goal 会话中，**直接把 `GOAL_PROMPT_DIRECT_PASTE.md` 全文粘贴到 Goal 输入框并发送**。

发送后 Goal 立即开始工作，不需要第二条启动消息。

## 本版修正的核心问题

1. 不再把“18 个专用 Runtime + baseline 通过”直接等同于“18 项 construct-valid 完成”。
2. 明确重新打开 Phase A，先补齐 Contract conformance、mechanism/difficulty 因果多样性、复杂 suite 的真实机制和正式 runner。
3. `CIG-OFFLINE-GATE=done`、`CIG-REST-16=done` 仅作为历史状态，不能阻止重新验收。
4. T311 已冻结的 `2.0.0` 和已有 pilot 先按 `PROVISIONAL / EXPLORATORY` 处理，保留但不自动视为正式科研资产。
5. 新 Phase A gate 真正通过后，Goal **继续**逐 suite 数据生成、在线 pilot、正式运行，直至最终科研 DoD，而不是停在代码阶段。
6. 数据阶段严格执行“小试 -> 改生成/验证流程 -> 再试 -> recipe 稳定 -> 批量生成 -> freeze -> online pilot -> formal run”。
7. 不一次性生成 18 套正式数据。

## 文件

- `GOAL_PROMPT_DIRECT_PASTE.md`：直接粘贴到 Codex Goal 输入框。
- `01_CURRENT_STATE_AUDIT_BASELINE.md`：当前源码真实状态与已知偏离。
- `02_PHASE_A_REOPEN_IMPLEMENTATION_PLAN.md`：重新打开 Phase A 后的执行计划。
- `03_PER_SUITE_CONSTRUCT_ACCEPTANCE.md`：18 项逐项验收要求。
- `04_FORMAL_RUNNER_MIGRATION.md`：正式执行链从 legacy runtime 迁移到 construct runtimes。
- `05_DATA_AND_ONLINE_LIFECYCLE.md`：Phase A 后逐 suite 数据与在线评测流程。
- `06_SCIENTIFIC_GATES_V2.md`：全生命周期 Gate。
- `07_WORK_QUEUE_OVERLAY.yaml`：建议新增任务 DAG；用于合并，不覆盖旧队列。
- `08_CHECKPOINT_AND_FINAL_REPORT_TEMPLATE.md`：长 Goal 的状态与最终报告格式。

原则：历史证据保留，新的事实用新任务/新版本覆盖认知，不篡改历史。
