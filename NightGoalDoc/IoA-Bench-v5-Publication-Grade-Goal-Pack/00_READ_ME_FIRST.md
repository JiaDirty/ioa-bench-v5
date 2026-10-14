# IoA-Bench v5 — 唯一当前有效的 Codex Goal Pack

**长期 Goal：** `IoA-Bench v5 Publication-Grade Scientific Revision`（仍是原 Goal，不创建新 Goal 或 v6）。  
**更新日期：** 2026-10-10；**事实基线：** 用户提供的 `IoA-Bench-source-review-20261010.zip` 静态快照。  
**工作区：** `D:\Project\ioa_codex_spec`。
**本 Goal Pack 固定目录：** `NightGoalDoc\IoA-Bench-v5-Publication-Grade-Goal-Pack`（以后修订不更改文件夹名）。

## 一句话用法

1. 先备份并将带日期的旧 v5 Goal 文件夹移出活动目录；解压本包到 `NightGoalDoc`，使该目录仅有一个有效 v5 Goal：`IoA-Bench-v5-Publication-Grade-Goal-Pack`。历史 Goal 留在归档位置。
2. 在 **新 Codex 会话**中设置 `GOAL_DIRECT_PASTE.txt` 中的 `/goal ...`。然后发送 `CODEX_FIRST_MESSAGE.txt` 作为当前阶段的工作指令。
3. 如果 Codex 版本没有 `/goal` 功能，则将 `GOAL_TEXT.md` 作为本会话长期任务说明，照常使用 `CODEX_FIRST_MESSAGE.txt`；不要假装持久 Goal 已生效。

**重要：Codex Goal 是会话级（thread-scoped）持久目标，不是自动全局共享。** 新会话需要重新设置同一份 Goal；磁盘上的本包、`AGENTS.md`、`state/PROJECT_STATE.yaml` 和 `docs/v5/` 才是跨会话接手依据。

## 结构与权威来源

| 文件 | 职责 |
|---|---|
| `GOAL_DIRECT_PASTE.txt` / `GOAL_TEXT.md` | 同一个精简的长期结果合同（不是两个 Goal） |
| `GOAL_CONTRACT.yaml` | 便于审计和机器读取的同一目标；不替代项目状态文件 |
| `CODEX_FIRST_MESSAGE.txt` | 新会话第一条阶段任务；不能当成另一个持久 Goal |
| `01_SCIENTIFIC_CONSTITUTION.md` | 18项风险的科学边界 |
| `02_CURRENT_BASELINE_AND_AUDIT.md` | 2026-10-10 静态事实，可能随研发过期 |
| `03_PUBLICATION_READINESS_CONTRACT.md` | Gate A–H 验收合同（最终完成条件） |
| `04_COST_AND_AUTONOMY_POLICY.md` | 高效直接、最小必要验证与花费批准 |
| `05_STARTUP_HANDOFF.md` | 读取顺序、冲突处理与跨会话恢复 |
| `06_CURRENT_EXECUTION_STAGE.md` | **当前阶段**的优先级、边界、停止点，不改变长期 Goal |
| `PACK_MANIFEST.json` | 本包内容哈希与来源 |

当前事实优先级：**研究负责人最新明确决定** → `docs/v5/V5_PI_DECISION_LOG.md` → v5 construct/protocol/statistics/review docs → 当前磁盘源码/数据/状态及可复验证据 → 本包的静态进度摘要 → v4历史材料/旧 Goal。遇到 `AGENTS.md` 旧 v1 默认值与 v5 已签决策冲突时，不能默默同时执行；提出并完成最小一致性修订，且不得削弱其科学边界。

## 权威 Codex 指南（参考，并非项目事实）

- OpenAI *Using Goals in Codex*：https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex
- OpenAI *Harness engineering*：https://openai.com/index/harness-engineering/
- OpenAI *Rethinking skills and prompts for GPT-6 Astra*：https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
- OpenAI *How OpenAI Uses Codex to Accelerate Engineering*：https://openai.com/business/guides-and-resources/how-openai-uses-codex/

遵循官方核心思路：Goal 写**结果+证据+边界+迭代与停止**，`AGENTS.md` 做短索引，当前阶段任务不要反复重写长期目标。旧版 `CLAUDE_FIRST_MESSAGE.txt` 已停用；新包改用 `CODEX_FIRST_MESSAGE.txt`。
