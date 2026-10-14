# 交付说明：IoA-Bench v5 AI 数据生成流程设计

这是一份给本地 Codex 的**阶段实施包**，不是新 Goal Pack，也没有改动用户 Windows 项目。

文件组成：

1. `01_IMPLEMENTATION_DESIGN.md`：完整设计（科研边界、架构、蓝图→Case、独立复核、质量门槛、高效试跑）。
2. `02_BLUEPRINT_SCHEMA.json`：AI 结构化场景蓝图的通用 JSON Schema（草案契约，需要 Codex 结合当前源码复核）。
3. `03_T321_EXAMPLE_BLUEPRINT.json`：T321-S4 结构化示例（演示性质，**不是**真实 AIHubMix 生成/已经通过 Gate 的案例）。
4. `04_CODEX_EXECUTION_INSTRUCTIONS.md`：交给 Codex 的完整阶段任务书：先复核，再实现，最后调用 AIHubMix 小批量试跑。

## 使用步骤

把这4个文件放入 `D:\Project\ioa_codex_spec\docs\v5\ai_data_generation_design\`（或 Codex 独立 worktree 对应目录）；在同一 Codex 会话中发送 `04_CODEX_EXECUTION_INSTRUCTIONS.md` 的全文，或要求 Codex 依照此文件执行。沿用你已设置的**唯一** v5 长期 Goal，不要创建新的 Goal Pack。

设计与示例中的字段和规则是**新设计提案**，不是声称现有 T321 已支持任意任务图/动态评分；Codex 第一阶段必须用本地**最新**项目对照核验。

真实调用 AIHubMix 需要用户本地已经配置的凭据；本包不包含任何 API key。数据生成/独立审核的少量真实调用由用户在当前对话明确要求执行，但这不授权完整科研 Pilot/Campaign。

5. `05_OFFLINE_EXAMPLE_GATE_DEMO.py` + `06_OFFLINE_CHECK_RESULTS.md`：示例手工编译成 T321 配对并通过旧快照参考 Gate 的证据；只是 fixture，不是通用生成器。
