# M0–M10 完成审计：快照状态与需要新增的验收

本表记录**2026-10-11 快照**，只凭已看到的源码、ZCode 会话/工作队列，不承诺 Windows 上此刻状态不变。ZCode 应主动重核并补充证据，不可直接覆盖原队列为“全部失败”。

| 阶段 | 已有的真实成果 | 不能代表的事情 | 下一步验收 |
|---|---|---|---|
| M0 | 原 Goal 整合、基线与 PI-V5-007 | 源码未来变动都已覆盖 | 锚定此审计的版本和工作区变更摘要 |
| M1 | 18 Suite/14 component 能力图、验证器 | DRAFT 能力映射等于14项实际执行能力 | 完成或显式标记未实现/拟实现组件；科学语义原样 |
| M2 | 引擎1.3.0、事件/授权/证据/时钟组件 | 组件已对缺省约束安全封闭、每种副作用可追溯 | P0-A/B/C 修复通过 + 兼容测试 |
| M3 | `monitor.py` 账本/时序/消息流 | 正式 Runner 已全面调用；T331/T333审计完成 | P1 强制动态接线 + `DW-033` 待办；范围清楚时再 `VALIDATED` |
| M4 | T321两种动态结构 + 离线 Gates | MiMo 能随机组合更多任务 family | 真动态 Runner 与家族判定小试跑 |
| M5 | Codex 原型存在、主线无合流 | 主线已经有 AI 自动数据生产 | 快照签收、选择性集成、真实端到端 MiMo/GLM |
| M6 | T312复用通用离线 Gate 和 TimingRule | 第二 Suite 的AI生产全链已经成立 | T312 在统一 Runner + MiMo/GLM 验证 |
| M7 | 18项19个动态切片，ZCode报告216 tests PASS | 18个自由组合生产 adapter均完成 | 每项可执行/可编译/可评分/可监测/可审计矩阵；DW-070当前IN_PROGRESS |
| M8 | 覆盖分析、目标文档、6对离线实验、CAPABILITY_GAP | 结构 family 目标达成，已获扩大生成授权 | P2去重、P3合流、质量反例、独立审核、PI 扩量授权 |
| M9 | 旧在线 Smoke、未批准确认 Pilot | 新动态数据已经完成 Gate E/F | Gate A–F/外部 Gate D + PI Pilot 授权 |
| M10 | 既有报告/脚本与正式测评经验 | 新架构已完成正式18项测评 | 完整冻结、PI Campaign 授权后执行 |

## 状态冲突核对

- `state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml` 中 M1 `VALIDATED` 但 `DW-013 NOT_STARTED`（可以记录“无冲突触发”，但不应模糊这个状态）。
- M2 `VALIDATED` 但 `DW-022 DEFERRED_TO_M4_M5`；需要查实际 Blueprint contract 是否已合并，而不是把延期当已交付。
- M3 `VALIDATED` 但 `DW-033 NOT_STARTED`（T331/T333 科研审计仍悬而未决）。
- M7 `VALIDATED` 但 `DW-070 IN_PROGRESS`；可写 `slice coverage validated`，不能写 `full data-factory readiness`。
- M8 `IN_PROGRESS` 合理；M5 `BLOCKED` 仅对尚未拿到稳定 Codex 快照的阶段有效。

## 统计与资格边界

试验用 mock/离线 Gate、在线 Smoke、确认 Pilot、正式 Campaign 彼此不能互相替代；单个 PASS 不能证成 publication-ready；对动态 Runner 的不可观测/无机会/基础设施失败保持原 outcome 的科学分母规则。所有新人工审核按双盲真实人类专家处理，GLM 仅为机器质量审阅。
