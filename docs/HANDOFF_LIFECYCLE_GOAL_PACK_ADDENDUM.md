# 当前交接增补：全生命周期 Goal Pack

本增补仅描述初次 `IoA-Bench-current-workspace-handoff-20260925.zip` 之后的工作区变化，不代表研发继续推进。项目状态仍是 `construct_remediation_awaiting_t311_review`，队列 235 项；仅 T311 有新的离线构念切片。其余 17 项、正式新数据、在线 pilot、r6 均未发生。

新增目录 `NightGoalDoc/IoA-Bench-Codex-Full-Lifecycle-Goal-Pack/` 包含：

| 文件 | 用途 |
|---|---|
| `00_READ_ME_FIRST.md` | 后续规划资料的读取顺序 |
| `GOAL_FULL_LIFECYCLE_AUTONOMOUS_COMPLETION.md` | 最终完整生命周期目标，**不是当前实现结果** |
| `01_FULL_LIFECYCLE_EXECUTION_PLAYBOOK.md` | 先完成全部构念代码、再逐 suite 试数据与在线评估的步骤 |
| `02_18_SUITE_CONSTRUCT_DATA_ONLINE_SPEC.md` | 18 项下一阶段预期风险机制、数据变化及指标摘要 |
| `03_FULL_LIFECYCLE_SCIENTIFIC_GATES.md` | 代码、试生成、冻结、pilot、正式运行及聚合的分层门禁 |
| `04_FULL_LIFECYCLE_WORK_QUEUE.yaml` | M11–M13 生命周期**草案**，并未合并进现役 `state/WORK_QUEUE.yaml` |
| `05_CODEX_FIRST_MESSAGE.txt` | 启动后续工作时的说明文本，不是现役运行指令 |
| `PACK_MANIFEST.json` | 该资料包自己的文件元数据 |

本次请求优先：暂停功能开发，只读核对与交接。旧 ZIP 和旧 manifest 原样保留；本次使用版本化 Inventory/Manifest 和新的 ZIP。源代码、冻结数据集、历史 run、历史 gate、现役状态/队列均不改。

验证注意：旧交接索引曾建议在原工作区运行排除 integration/v1 gate 的广义 pytest，实际 24 个 M4–M8/suite/generation gate 测试仍写历史 JSON。本次确曾执行后将 24 个文件从旧 ZIP **逐字节恢复**，并对旧 ZIP 全部共享文件进行 SHA-256 复核，差异为零。只在隔离副本中重跑广义测试；原地仅用 construct tests 与 `validate-spec`。Windows 离线：24 construct passed、347 broad passed；Linux `NOT VERIFIED`。未调用 AIHubMix。
