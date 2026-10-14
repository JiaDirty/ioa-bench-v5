# 直接交给 Codex 的阶段任务书：先复核，再实现，再真实小批试跑

请在你本地的 `D:\Project\ioa_codex_spec` 执行。这是现有 IoA-Bench v5 **唯一长期 Goal** 的一个研发阶段，不是新的 Goal Pack。长期 Goal 固定为 `NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/`。

## 0. 要求先读哪些文件

1. `AGENTS.md`、`NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/{00_READ_ME_FIRST.md,GOAL_TEXT.md,06_CURRENT_EXECUTION_STAGE.md}`。
2. `state/PROJECT_STATE.yaml`、`docs/v5/{V5_PROGRESS.md,V5_PI_DECISION_LOG.md,V5_SINGLE_MODEL_CONFIRMATION_PLAN.md}`（以当前工作树最新内容为准）。
3. 本包的 `01_IMPLEMENTATION_DESIGN.md`、`02_BLUEPRINT_SCHEMA.json`、`03_T321_EXAMPLE_BLUEPRINT.json`。
4. 相关权威源码：`contracts/v5/construct_maps.json`、`src/ioabench/v5/core/{case.py,engine.py,firewall.py}`、`src/ioabench/v5/{gates.py,suites/t321.py,suites/t333.py}`、`scripts/v5/{build_dataset.py,data_quality.py}`；按需看模型端口和本地 AIHubMix 文档 `D:\Project\Playground\scrape\aihubmix`。

**时效性：** 本包设计所参照的代码快照截止 2026-10-10；目前主线在 2026-10-11 已开展了新一轮在线 Smoke 与配置修订。发现差异先以当前源码、最新 PI 决定和实验契约为准，不能回退主线参数。

## 1. 首阶段必须是“审查设计”，不要直接写生成器

在独立分支/worktree/隔离实验目录做以下检查，产出简短 `review_findings.md`：
- 这份设计有没有违反18项定义、构念边界、CONTROL/RISK 因果约束、Ground Truth 外部权威、防泄漏、评分规则、科研证据不可变原则？
- T321 当前场景及 witness/naive/recovery 能否执行示例 blueprint？哪些字段必须转换或收窄？
- 现有 `mechanism_slots` 粗粒度 diff 是否遗漏同槽内部混淆变化？需什么**最小且充分**的 Suite 专属检验？
- 生成平台的核心接口是否必要、是否可以复用现有实现而减少模块？
- 是否真的可以从该源码生产多个结构上不同的 T321 家族？不要把换域名/公司/字段值当成多样性。
- 审核模型如何保持与生成模型的独立性？自动验证和专家 Gate D 如何区分？
- T333 作为第二 Suite 能否复用框架？其 scorer 弃权机制是否需要保持原样？

发现工程上的误差可自行修正**设计副本并记录变更**。如果必须更改风险构念、既定 Oracle/scorer 语义、CONTROL/RISK 的科研定义，标记 `SCIENCE_DECISION_REQUIRED`，不要直接改这些内容；可以先将原型限制在不触发争议的子类型。

**如果审查存在未解决的阻断问题，不得直接进入付费生成阶段。** 不需要为了形式召开多个冗长审查循环；形成可执行修正结论后继续。

## 2. 第二阶段：实现最小但完整的通用管线

按 `01_IMPLEMENTATION_DESIGN.md` 实施：覆盖规划→真实 AI Structured Blueprint→Schema / SuiteAdapter 校验→T321 确定性编译 CONTROL/RISK→细粒度操纵白名单→ `check_pair` → 去重/结构差异检查→独立 AI 语义复核→合格/拒收/弃权证据持久化。

- 优先复用项目已有 ModelPort、哈希、firewall、case、gates 和 data_quality 功能；不足才写最小适配层。
- T321 首版**不要改已有 Suite/Scorer/Generator/Case/公共引擎**来迁就 AI；可选能力不支持则标记 `CAPABILITY_GAP`。
- 不引入 Docker、数据库服务、外部队列、昂贵的通用 DAG 引擎或自创 Agent 框架。
- Schema 示例仅用于演示，不可把示例数据硬编码成实际生成成果。实际要来自真实模型的结构化输出。
- 所有输出按新 run ID 入独立 `artifacts/v5/ai_generation/`；旧数据与旧在线 Pilot 不得改动；禁止将实验数据纳入确认性 Pilot 默认路径。
- 使用当前可用 AIHubMix 中的**不同家族**生成/审核模型，且两者均不是正式被测 `deepseek-v4.1-flash`。核实实际返回身份与 capabilities，且不可静默 fallback。
- 采用 AIHubMix Structured Outputs/JSON Schema（确认当前模型能力），若网关不支持严格 Schema，则只允许有记录的 JSON输出+本地硬校验路径；不能默默接受不完整结构。
- 只从环境变量/既有 secret 读取 key，不回显、不持久化；禁止把本地文档全量塞给模型，按需读取。

## 3. 第三阶段：先离线验证，再实际调用 AIHubMix 少量试跑

用户已明确授权**本次生成和独立审核原型所必需的小规模真实 AIHubMix 调用**，无需因为少量费用频繁申请批准；这是生成试验授权，**不是**216条确认性 Pilot 或正式 Campaign 的授权。记录实际调用和 tokens。

执行阶段必须严格控制**无效劳动**：

**S0 离线预检**——现有 T321 pair 的编译兼容、测试 fixture/Mock、reference gate、候选目录隔离全部通过前禁止调用 Provider。

**S1 最小 API 探针**——1次真实生成模型的结构化输出请求；字段合法、实际身份和网关能力正确才继续，否则立即定位 API/Schema 问题，不开始批量生成。

**S2 单份真实蓝图**——每生成1份立即编译两臂、运行所有硬 Gate、比对旧数据结构，成功才请独立验证模型审核。**第一份就发现工具/编译器/泄漏/参考策略系统性缺陷时，立刻暂停新请求并修复。**

**S3 小批扩展**——第1对真正通过后，一次再生成1–2份，逐份检验，不在前几条已发现问题时继续跑完整计划。优先覆盖至少2种不同子类型或任务证据路径。

**S4 按原因修复并继续**——结构性 Bug 定位修复+针对性回归后恢复；同类系统性生成质量失败连续2次则暂停该类任务并改进生成约束；偶发无效 JSON 有界重试，不能无限重试；实质重复拒收而不是换公司名凑数。

**S5 收尾**——默认最多尝试8份 T321 蓝图/3轮反馈；达到2–3个真正不同的合格 family 即停。如果质量/多样性不足，记录真实结果与能力缺口并停，不降低门槛。不机械生成更多。对 T333 只做少量可复用性试验，禁止改变既定 scorer。

任何原型编译改动都应有有针对性的自动化测试。原则上不需重跑3,240项离线矩阵；**若影响旧核心行为则必须重跑相关 Gate，且要说明为什么需要改动。**

## 4. 最终交付（不是审计文档代替代码）

1. `review_findings.md`：设计审查结论/阻塞点/必要变更与证据；明确科学边界没有被破坏。
2. 可运行原型源码/Schema/T321 SuiteAdapter/测试；一条可重复的命令或简短用法说明，能重新生成不同 run ID 的实验数据。
3. **真实** AIHubMix 生成与独立审核至少一轮的不可变原始证据和结构化结果（若因必要的科学阻断无法继续，清晰注明没有进行付费调用及阻断原因，不能造数据）。
4. 已通过候选 CONTROL/RISK 与拒收记录，全部具 provenance、Case hash、reference gate、语义审核及多样性对照；未通过绝不能混入 accepted。
5. 面向人的简短 `summary.md`：用了哪些实际模型、调用次数和 tokens，生成了多少草案/配对，通过/弃权/拒收多少，停在何处、有没有发现系统性错误、是否达到有证据支撑的高质量/实质多样性，跨 Suite 复用还缺什么。
6. 最小必要的自动化测试结果和隔离证明；说明未改动历史数据、Gate E/Campaign，也未创建新 Goal。

**完成后停止，不自动扩大到18项批量生产，不自动合并到正在运行在线测评的主工作树。** 如果数据没有达到质量要求，报告不能编造成功；聚焦失败原因和下一轮最小改进。
