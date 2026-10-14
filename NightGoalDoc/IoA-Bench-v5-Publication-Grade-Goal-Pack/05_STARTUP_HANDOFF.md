# 新 Codex 会话接手规范（不是重做 v5 架构）

**固定 Goal 目录：** `NightGoalDoc\IoA-Bench-v5-Publication-Grade-Goal-Pack`。以后仅更新本目录文档，不为阶段任务另建 Goal 目录。

## 正确启动

1. 进入 `D:\Project\ioa_codex_spec`；阅读根 `AGENTS.md`（留意其中沿用 v1 的默认值，遇到与当前 v5 PI 决策不一致之处只做必要修订，不丢弃科学原则）。
2. 阅读本目录 `00_READ_ME_FIRST.md`、`GOAL_TEXT.md`，以及对当前改动真正相关的 `01`、`03`、`04`、`06`；不必每次全文扫描所有旧 Goal 和历史 ZIP。
3. 读取 **现时** `docs/v5/V5_PI_DECISION_LOG.md`、`docs/v5/V5_PROGRESS.md`、`docs/v5/V5_SINGLE_MODEL_CONFIRMATION_PLAN.md`、`state/PROJECT_STATE.yaml` 的 v5 小节；按需打开 `contracts/v5/construct_maps.json`、`docs/v5/V5_03_STATISTICAL_ANALYSIS_PLAN.md`、`docs/v5/V5_04_REVIEW_PROTOCOL.md`。
4. 根据源码和证据确认当前进行中的最短高价值任务；优先执行 `06_CURRENT_EXECUTION_STAGE.md` 描述的阶段。已有代码和测试不从头重建。
5. 简要记录实际变化、证据、阻塞及下一动作到**现有状态/进度台账**；不要再创建额外 Goal Pack 或重复的进度管理系统。

## 首次会话行为

先设长期 Goal（`GOAL_DIRECT_PASTE.txt`），再发 `CODEX_FIRST_MESSAGE.txt`。如果界面没有 `/goal`，使用 `GOAL_TEXT.md` 作为长任务目标，不声称已启用自动延续。

若 `GOAL_DIRECT_PASTE.txt` 过长或环境限制，可将其中纯任务正文写入 Codex Goal，配套文件已经包含不变量和 Gate 细节。Goal 文本和独立首次消息职责不同，不要把第一条消息再保存为新 Goal。

## 事实来源与一致性规则

- 最新用户确认的 PI 决策与正式版本化协议优先于旧 Goal、旧 v4 state 及本包静态摘要。
- 项目状态必须区分 `implemented` / `offline verified` / `exploratory online` / `independently validated` / `frozen` / `formal run`。
- 允许修复过时的执行说明/索引；研究含义、阈值、样本数和版本的变更须按项目内部科学决策机制记录，不得为得到更好模型得分而改变。
- 长跑被用户批准费用或独立审阅阻断时，**停在阻塞点**，同时完成其他可离线独立推进的工作。不要把停止误判为 Goal 失败，或为“连续执行”绕过授权。

## 不要重复过去做过的阶段

旧 `05_STARTUP_HANDOFF.md` 要求重做 Scientific Architecture Pass，那是2026-10-04启动 v5 时的工作，目前已由 `V5_00_ARCHITECTURE_DECISION.md`、18套构念和实现成果覆盖。只有新证据直接推翻现有架构假设时，才做定向方法学复核。
