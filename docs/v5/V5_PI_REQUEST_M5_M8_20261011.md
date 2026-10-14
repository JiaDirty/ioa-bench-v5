# PI_DECISION_REQUIRED — M5 数据工厂合流解锁 与 M8 扩量生成授权

**日期**：2026-10-11
**提交方**：ZCode（动态世界阶段）
**决策路径**：PI-V5-007 后续；本文件即两项决策所需的完整范围与证据
**状态**：两项均待 PI 批准；批准前不发生任何对应 Provider 调用或写操作

---

## 请求一：M5 解锁 — 接收 Codex 数据工厂快照并开展隔离集成

### 背景
Codex 在 `D:\Project\ioa_codex_spec_ai_generation_probe` 独立开发 MiMo→T321→GLM 数据生成原型（`ai_generation` 包：blueprint_schema / t321_adapter / diversity / validator / suite_adapter + `ai_generate_probe.py`）。原 M5 解锁条件为 24h 目录静默；修订包 `04_GLOBAL_EXECUTION_AND_MONITOR_CONTRACT.md` 与 PI 指示已将该规则替代：**Codex 交付 SHA-256 哈希固定的不可变快照 + 测试清单 + 已知风险声明后，可立即开展隔离审查，不必机械等待**。截至 2026-10-11 17:19 该快照尚未交付，故 M5 仍 BLOCKED——阻塞方是 Codex 的交付物，不是时间。

### 请求内容
1. **请 PI 向 Codex 转达交付要求**：不可变快照（文件清单 + 逐文件 SHA-256）、测试报告、已知问题/未解决风险声明。
2. **批准 ZCode 在收到快照后执行以下隔离集成流程**（只读验收，不写 Codex 目录）：
   - 逐文件 diff vs 主线，判定可移植性；
   - 移植目标：`ai_generation` 契约、能力映射、稳定算法与测试 → 主线新命名空间；
   - 移植后主线全量回归 + 离线矩阵；
   - **边界**：Codex 当前蓝图若仅支持旧 T321 固定流程，标为 `T321_LEGACY_BLUEPRINT`，不得宣称动态世界支持。

### 风险与边界
- 不整目录覆盖主线；不重造已有数据工厂组件；历史证据只读。
- 快照质量不足时记录缺陷并退回 Codex，不降门槛凑合流。

---

## 请求二：M8 扩量生成授权（分阶段）

### 背景
M8 前置论证已完成：`docs/v5/V5_M8_COVERAGE_TARGETS.md`（配额原则 + 诚实发现）+ `artifacts/v5/dynamic_world/coverage-analysis.json`（离线覆盖分析）。**关键前置依赖：M8 扩量的 AI 生成链路需先经请求一的 M5 合流**——在 Codex 原型合流并端到端验证前，无法启动 MiMo 生成。

### 请求内容（分两阶段，均受硬门槛约束）
1. **阶段一（M5 合流后）**：MiMo→动态编译→GLM 全链小规模技术验证——按 `01_IMPLEMENTATION_DESIGN §7` 阶段门控 S0–S5，先 1 份 Blueprint 全链走通（生成→编译→硬 Gate→家族判定→GLM 审核），再微批 2–3 份；上限 8 份探索、2–3 个有效独立家族即停。估计调用量：数十次 Provider 调用（生成+审核），与 PI-V5-006a 技术试验同量级。
2. **阶段二（阶段一验收后）**：按覆盖目标配额扩产——每 Suite 有效家族 ≥36（30 存量 + 6 新结构）；**第一优先格**为 19 个动态切片结构扩产（需先为每切片参数化 ≥6 种真结构变体）；低载体形状 Suite（T352/T363/T343/T333/T362）优先。规模：约 18 Suite × 新增 6+ 家族 × 2 实例 = 216+ 对新候选（Provider 调用量显著，需 PI 确认预算）。

### 质量与诚实约束（不因授权而放松）
- 全链硬 Gate + 家族级结构去重 + GLM 独立审核（仅机器质量审阅，不替代 Gate D）；
- 名义 vs 有效家族分开报告；拒收全留痕；门槛不足即停不降级；
- 生成数据一律 `CANDIDATE_EXPERIMENTAL`，不进 Gate C 正式池/Pilot/Campaign 分母，除非后续 Gate C/D + PI 决定升格；
- 被测模型 deepseek-v4.1-flash 的安全表现不驱动任何选题/筛选。

---

## 批准选项

| 选项 | 内容 |
|---|---|
| A（推荐） | 批准请求一（M5 快照接收+隔离集成）+ 请求二阶段一（小规模全链验证）；阶段二待阶段一证据出来后再批 |
| B | 仅批准请求一；阶段一另行报批 |
| C | 暂缓；维持 M5 BLOCKED 现状 |

**无论批准与否**：P0–P2 修复、动态 Runner、证据矩阵等已完成工程成果不受影响；Gate D 人类专家审阅、确认性 Pilot、正式 Campaign 的授权边界不变。

---

## ⚠️ 提交后新增发现（2026-10-11 20:02 UTC，S1 能力探针实测）

**`mimo-v2.6-pro` 当前在 AIHubMix 网关不可服务**：探针（`scripts/v5/mimo_s1_probe.py`，证据 `artifacts/v5/data_factory/s1-mimo-probe-20261011T120201Z.json`）显示模型发现通过但生成调用返回 HTTP 400 `no_available_channel`（"The model mimo-v2.6-pro cannot be served at the moment"，tid 2026101112020569958）。

**影响**：即使 PI 批准本文件请求，**M8 阶段一的 MiMo 生成在网关恢复该模型前无法执行**。选项：
- 等待网关恢复（探针可随时重跑，脚本与证据路径不变）；
- 或由 PI 指定替代生成模型（须与被测模型不同家族、非 DeepSeek，按 05 契约 §2 记录真实身份）。

此项为外部依赖（网关侧模型可用性），ZCode 无法解除。GLM-5.3-Flash 审核侧可用性未受本探针影响（未测试）。
