# IoA-Bench v5 动态世界 Goal：源码审计后的增量修订（2026-10-11）

## 定位与适用范围

本目录不是新 Goal、不是 v6、不是新的 Gate 体系，也不撤销 ZCode 已完成的 M0–M4、M6–M7 动态切片成果。它是现有唯一 Publication-Grade v5 Goal 和 `NightGoalDoc/IoA-Bench-v5-Dynamic-World-Goal-20261011` 的**补充执行契约**，用于更严格地核验动态世界的正确性、端到端接线、数据质量与 M5–M10 解锁条件。

基于截至 **2026-10-11 17:34** 的 ZCode 会话与 **09:41 UTC 源码打包快照**。最新 Windows 工作树可能已继续变化，执行前必须复核，不得把本审计当作已自动修复问题。

## 安装与使用

把 `08_POST_AUDIT_AMENDMENT_20261011/` 整个目录解压到：
`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-v5-Dynamic-World-Goal-20261011\`

原 00–07 设计文档不需要被覆盖。给 ZCode 发送 `06_ZCODE_RESUME_PROMPT.md` 的全文，令其对照源码进行整改；**只有 ZCode 审核后才写回**现有 `state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml`、`state/PROJECT_STATE.yaml` 和 `docs/v5/V5_PROGRESS.md`。

执行优先级：P0 正确性 → P1 统一监测与可执行动态 Runner → P2 结构 family 与去重 → P3 Codex 快照集成 → P4 多样性/跨 Suite 真实闭环 → P5 科研 Gate。允许互不冲突的工作并行；不把所有阶段人为串行化，也不要跳过前置门槛。

## 内容

- `01_GOAL_ACCEPTANCE_AMENDMENT.md`：补充长期 Goal 的真实完成标准。
- `02_PRIORITIZED_REMEDIATION_QUEUE.md`：明确任务/依赖/测试/阻塞。
- `03_P0_DEFECTS_AND_NEGATIVE_CONTROLS.md`：已定位边界问题与负控矩阵。
- `04_GLOBAL_EXECUTION_AND_MONITOR_CONTRACT.md`：动态 Runner + 全局监测接线与溯源验收。
- `05_DATA_FACTORY_AND_DIVERSITY_CONTRACT.md`：真实数据工厂和 family 质量门槛。
- `06_ZCODE_RESUME_PROMPT.md`：可直接发送 ZCode 的完整执行任务。
- `07_COMPLETION_EVIDENCE_MATRIX.md`：M0–M10 验收状态如何重新认定。
- `08_SOURCE_AUDIT_BASIS.md`：审核范围、时间点、代码证据与局限。
- `09_TASK_OVERLAY.yaml`：新增的**待审核任务建议**，不作为工作队列的替代文件。
- `MANIFEST.json`：包内文件 SHA-256。

## 绝不可混淆

`19个动态结构通过离线 Gate` ≠ `18项自由动态世界、在线运行与 AI 生成均成熟`；`monitor.py 可导入` ≠ `正式 Runner 全程监测`；`离线 build_dynamic_dataset.py 可执行` ≠ `MiMo/GLM 数据工厂已合流`；`家族 digest 不同` ≠ `可执行结构真新颖`；`216 tests passed（ZCode 完整工作区）` ≠ `本次删减源码包也独立跑通216项`。
