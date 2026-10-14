# IoA-Bench v5 动态世界与高质量数据工厂——统一长期 Goal 交付包

**日期**：2026-10-11。**性质**：拟写给 ZCode 的长期 Goal 整合方案，不是已在用户 Windows 主线执行的变更，不是 v6，不是另一个 Benchmark。

## 使用方法

1. 把此包解压至 `D:\Project\ioa_codex_spec\docs\v5\dynamic_ioa_goal_design\` 或其他不覆盖现有文件的文档目录。
2. 向 ZCode 发送 `06_ZCODE_START_PROMPT.md` 的完整内容，让它阅读本包全部设计；将 `01_LONG_TERM_GOAL.md` **合并到现有单一 v5 Goal 的目标体系中**，不要另建互相竞争的 Goal。
3. ZCode 首先做只读最新盘点（实际 Windows 主线优先于本设计、2026-10-10 静态源码和 2026-10-11 聊天报告），提出变更清单和分阶段任务树，然后开始可独立推进的工作。
4. Codex 正在 `D:\Project\ioa_codex_spec_ai_generation_probe` 进行语义保真与多样性修正。未经比对、测试、验收，不得自动把独立副本覆盖到主线。主项目没有 `.git`，不要假设可以创建 worktree。
5. 不把“架构完美”当作无法验证的口号。每个里程碑有可审计的验收与停止条件；Gate D 专家独立审阅及 Gate G 正式付费运行的必要审批不可绕开。

## 本包文件

- `01_LONG_TERM_GOAL.md`：ZCode 长期唯一总目标、角色边界、最终完成标准。
- `02_RUNTIME_AND_MEASUREMENT_DESIGN.md`：可组合动态 IoA 世界、自主执行、事件与因果测量设计。
- `03_DATA_FACTORY_AND_QUALITY.md`：MiMo + GLM 数据工厂、语义保真和实质多样性验证。
- `04_WORK_QUEUE_GATES.md`：M0–M10 工作队列、阶段验收、停止准则和 Gate A–H。
- `05_INTEGRATION_AND_EXECUTION.md`：现有 v5 与 Codex 隔离原型集成、安全迁移、版本锁定和并发规则。
- `06_ZCODE_START_PROMPT.md`：可以直接发送给 ZCode 的启动指令。
- `07_18_SUITE_MIGRATION_MATRIX.md`：18项测评与可复用环境能力映射。

**已核查依据**：既有 v5 Goal、`03_PUBLICATION_READINESS_CONTRACT.md`、2026-10-10 静态源码中的 `Case`/`engine`/`check_pair`/T321/construct maps、2026-10-11 上传的 `ai_generation.zip` 和 `QUALITY_REPORT.md`，以及用户提供的 ZCode v1.1.2 / 128K Smoke 汇报。最新 Windows 代码与 Codex 正在进行的新修复未被本包独立复验；必须启动时核对。
