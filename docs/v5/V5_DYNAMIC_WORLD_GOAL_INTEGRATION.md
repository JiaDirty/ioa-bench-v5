# IoA-Bench v5 — Dynamic World Goal 整合记录（M0 交付 1）

**日期**：2026-10-11
**性质**：Goal 一致性整合决定（M0 交付物）。不创建第二个 Goal，不升级 v6，不覆盖既有科研证据。

## 1. 权威来源核对

| 来源 | 状态 |
|---|---|
| 唯一长期 Goal 契约 `NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/GOAL_CONTRACT.yaml` | **保持唯一权威 Goal**。本整合不修改其 outcome、non-negotiables、Gate A–H 结构。 |
| 新设计包 `NightGoalDoc/IoA-Bench-v5-Dynamic-World-Goal-20261011/`（7 份文件，已全部读完） | 作为同一 Goal 的**目标定义扩展与执行规范来源**并入：`01_LONG_TERM_GOAL.md` 的四项使命与科研不变量与现有契约一致，作为 v5 动态世界阶段的执行依据；`02/03` 为架构与数据工厂设计契约；`04` 的 M0–M10 进入工作队列；`05` 为集成/并发规则；`07` 为 18 Suite 能力索引。 |
| `state/PROJECT_STATE.yaml`（v5 段）、`docs/v5/V5_PROGRESS.md`、`docs/v5/V5_PI_DECISION_LOG.md`（PI-V5-001…006a） | 现状基线，全部核对；见 §4。 |
| Codex 隔离原型 `D:\Project\ioa_codex_spec_ai_generation_probe` | 只读盘点（ISOLATION_MARKER 明确禁止自动合并）。其 `src/ioabench/v5/ai_generation/`（blueprint_schema、t321_adapter、diversity、validator、suite_adapter）+ `scripts/v5/ai_generate_probe.py` + `config/ai_generation_models.json` 于 2026-10-11 12:40–12:50 仍在活跃修改。**M5 前不写该目录、不复制其未稳定成果。** |

## 2. 整合决定

1. **一个 Goal**：现有 Publication-Grade Goal 的 outcome（evidence-backed、reproducible、publication-grade 18-suite single-model v5）不变。新设计的四个使命（动态执行环境、全局事件测量、自动数据工厂、18 项正式测评）是同一 outcome 的**实现路径**，全部落入现有 Gate A–H；不产生任何新 Gate 结构。
2. **一条主线**：M0–M10（新包 `04_WORK_QUEUE_GATES.md`）作为执行任务树写入 `state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml`；里程碑与 Gate 映射见 §3。里程碑状态用 `NOT_STARTED / IN_PROGRESS / VALIDATED / BLOCKED / PI_DECISION_REQUIRED`。
3. **不覆盖证据**：既有 2160 条候选（5.1.5-candidate-20261006、T332 5.1.6-candidate-20261009）、历史 4 模型 Pilot、各次 Smoke、PI 决策、v4.1.13 及更早 Release 全部只读。动态世界产物进入新命名空间（`artifacts/v5/dynamic_world/`、数据版本独立递增），审核通过前只是实验候选。
4. **兼容性红线**：engine/Case/Scenario/exposure/scorer 的扩展必须向后兼容现有 18 个 Suite 模块；任何接口变更需版本化迁移器 + `tests/v5` 回归 + 离线矩阵（受影响时）重跑。冻结正式数据与已发布结果永不回写。

## 3. M0–M10 与 Gate A–H 映射（不另造 Gate）

| 里程碑 | 对应 Gate | 说明 |
|---|---|---|
| M0 现场基线与并行隔离 | （前置） | 本文件 + 工作队列 + 基线哈希清单 + 并行规则。 |
| M1 科研—执行契约 | A（构念与因果） | 18 构念 → 世界能力/评价事实契约；构念语义变化 = `PI_DECISION_REQUIRED`。 |
| M2 动态 IoA 运行核心 | A/C 支撑 | engine 能力组件 + 事件账本；旧 18 套件回归。 |
| M3 全局监测与可靠测量 | B（评分效度） | 事件→outcome 通用链路 + Suite 专属谓词；T331/T333 沿用预注册审计路径。 |
| M4 T321 动态垂直切片 | A+B+C 的单机制证明 | 两种真实不同执行结构、多路径、细粒度差分；不可实现标 `CAPABILITY_GAP`。 |
| M5 数据工厂修复与合流 | C 前置 | 等 Codex 稳定快照 → 隔离审查 → 选择性移植 + 测试。 |
| M6 第二 Suite 复用证明 | A/C | T312 或 T323 同一骨架；固定 Adapter API。 |
| M7 18 Suite 渐进适配 | A/B/C | 分机制簇；T361–T363 保持 `SIMULATION_ONLY`。 |
| M8 候选生产与 Gate C/D 准备 | C/D | 批量生成需 PI 批准（见 §5）；Gate D 双盲包准备，真实专家审阅不可由 AI 代替。 |
| M9 确认 Pilot 与科学冻结 | E/F | 216-case Pilot 与冻结需 PI 单独授权（PI-V5-006 线约束仍在）。 |
| M10 正式测评、统计与交付 | G/H | 仅在 A–F 通过且 PI 明确批准后执行。 |

## 4. 冲突核查结果（逐项）

| # | 潜在冲突 | 结论与处理依据 |
|---|---|---|
| C1 | 新包 03 称“用户不以模型调用费为主要限制” vs PI-V5-006“新付费调用一律需明确批准” | **以最新 PI 意志为准**：用户 2026-10-11 Goal 指令明确“授权长期架构开发、离线测试、Mock 验证和小规模真实 API 技术试验；不等于预批准大规模生成、确认性 Pilot 或正式 Campaign”。已记为 PI-V5-007；超出小规模技术试验的调用仍逐项报批。 |
| C2 | 数据工厂固定 `mimo-v2.6-pro`（生成）+ `glm-5.3-flash`（审核）vs PI-V5-005“生成/验证/persona 模型与被测模型不同家族即可” | **无冲突，需记录**：mimo（Xiaomi 家族）与 glm（Z.AI 家族）均非 DeepSeek 家族且互相独立；用户 2026-10-11 指令明确指定。记入 PI-V5-007。Codex 原型 `config/ai_generation_models.json` 与此一致。 |
| C3 | 新包 02 的“目标接口草案”（declarative world spec 等）与现有源码字段不一致 | 设计包自身声明“以最新真实代码为准，不照文字机械引入”。处理：M2 以现有 `Case/Scenario/EnvContext` 为基础做**最小兼容扩展**，不推倒重来。 |
| C4 | 动态世界“Agent 自主选择路径” vs P3 witness 判定机制 | **无冲突**：witness/naive/recovery 仅用于 Gate 判定可辨识性（P3 原文即如此）；不得反向限制被测 Agent 行动——与 01_LONG_TERM_GOAL 表述一致。 |
| C5 | 新包 05 引用的 v1.1.2 冒烟状态与台账差异（“16 Suite 96/96”遗漏 T352/T332 8192 批次） | 以 `V5_PROGRESS.md` 精确表述为准：T352/T332 原始冒烟为 v1.1.0/8192，v1.1.2 覆盖由 pair recheck（`artifacts/v5/probes/v112-pair-recheck.jsonl`）补齐；18/18 套件在 v1.1.2 下均有在线覆盖。已在工作队列 M0 记录该版本区分，不得声称“18 项同一冒烟结果”。 |
| C6 | 动态世界数据工厂与既有 5.1.5/5.1.6 候选池关系 | 新产物进独立实验命名空间（`CANDIDATE_EXPERIMENTAL`），不进确认性 Pilot 默认发现路径；升格为正式数据需 Gate C/D + 版本 + PI 决定（01_IMPLEMENTATION_DESIGN §6/§9 与新包 03 §5 一致）。 |
| C7 | 新包要求“旧 18 套件行为兼容回归”与“只在共享运行语义改动时跑全矩阵” | 两者兼容：默认针对性回归；engine/exposure/firewall/gates 语义改动时重跑 3240 离线矩阵（2026-10-11 暴露检查器变更时即按此执行，有先例）。 |

**未发现需要修改构念、Oracle 或评分语义的冲突。** 所有整合均在“扩展”而非“改写”范围内。

## 5. 授权状态快照（2026-10-11，来自用户 Goal 指令 + PI-V5-006/006a）

- 已授权：长期架构开发、离线测试、Mock 验证、小规模真实 API 技术试验（含数据工厂 S0–S5 阶段门控内的最小试跑，遵守 01_IMPLEMENTATION_DESIGN §7 的阶段门控与停止条件）。
- 未授权（保持 `PI_DECISION_REQUIRED` / `BLOCKED`）：大规模（18 Suite 全量）候选数据生产、216-case 确认性 Pilot、正式 18 项 Campaign、Release 冻结。
- Gate D：`BLOCKED_EXTERNAL_REVIEW`，人类独立专家审阅不可由 AI 代替。

## 6. M0 盘点结论（能力—缺口摘要）

**已存在且复用**（`src/ioabench/v5/`）：
- `core/case.py`：`Case`（world/oracle/mechanism_slots/fingerprints/provenance）、JSON Pointer 机制槽、`pair_diff_violations`。
- `core/engine.py`（v5-episode-engine-1.2.0）：turn 制多 Agent 剧集、类型化 `ToolSpec`（decision 标志）、`EnvContext`（state/actions/events/inboxes）、预算前置执行、reasoning 持久化、AttemptJournal。
- `core/firewall.py`（静态+运行时防泄漏）、`core/exposure.py`（v1.2.0 合取指纹暴露/机会证明）、`core/outcome.py`（分离轴 + LEGACY_TABLE）、`core/policy.py`（witness/naive/recovery 脚本策略）、`gates.py`（check_pair）、`runner.py`（run_case 全链）、`worlds.py`（8 域）、18 个 Suite 模块（程序化 generate + Scenario + scorer + 参考策略）。
- 脚本：build_dataset、data_quality、pilot（manifest 硬门）、run_offline_gates、agreement、build_review_package、protocol_probe、v112_pair_recheck。
- 状态：tests/v5 89 passed；离线矩阵 3240/3240；协议 v1.1.2 在线冒烟 18/18 技术通过。

**缺口**（按 M1–M7 排序）：
1. **G1（M1）**：构念→世界能力/评价事实的结构化契约不存在（现在散落在 18 个模块实现 + construct_maps 叙述字段中）。
2. **G2（M2）**：世界是 Suite 硬编码的固定结构（如 T321 固定 offers/exception/items 形状），无声明式实体/证据/授权/时序规范，无能力组件装配；`EnvContext.events` 只有 `{seq,turn,kind,payload}`，无因果边/状态前后哈希/可见性/授权链字段；工具执行无调用方权限仲裁（能列出工具即可调用）；无证据出现时机/撤销/冲突的一等表示。
3. **G3（M3）**：暴露/机会已有通用证明，但“时序性质”（先核验后行动、未经许可不发送等）靠各 Suite scorer 代码内联实现，无常驻事件谓词机制；跨 Agent 传播链测量无通用支撑。
4. **G4（M4）**：T321 现有 5 个 subtype 共享同一执行结构（accept→send→close 单链），需证明≥2 种真正不同的可执行任务/证据/交互结构且不依赖 witness 路径。
5. **G5（M5）**：数据工厂主线无 `ai_generation` 包（Codex 隔离开发中）；等待其稳定后按 05_INTEGRATION §M0 规则移植。
6. **G6（M6–M7）**：第二 Suite 及 18 项适配未开始（依赖 M2/M3/M5）。

（详细逐 Suite 映射在 M1 交付 `contracts/v5/dynamic_world_capability_maps.json`。）
