# V5 M5/P4 验收报告 — Codex AI 数据工厂快照接收、选择性合流与 T321-DYNA 蓝图编译

> 日期：2026-10-11 · 授权：PI 选项 A（docs/v5/V5_PI_REQUEST_M5_M8_20261011.md 批复）· 执行：ZCode 会话
> 状态：**步骤 1-4 完成（离线验收 PASS）；步骤 5（有限真实 API 验证）按 PI 约定"不可用即停止"，冻结于 BLOCKED_ON_GATEWAY**

## 0. 结论一览

| PI 选项 A 步骤 | 状态 | 证据 |
|---|---|---|
| 1. M5 快照接收（哈希验收） | **完成，PASS（带一项如实记录的未验证字段）** | §1，porting-review.json |
| 2. 选择性合流（移植契约，不移植 legacy 适配器） | **完成** | §2，src/ioabench/v5/ai_generation/ |
| 3. T321-DYNA 真实蓝图编译（失败闭合 CAPABILITY_GAP） | **完成** | §3，t321_dyna_compiler.py |
| 4. T321 两个动态结构端到端离线验证 | **完成（结构 A 编译路径 14/14；结构 B 既有验收保持）** | §4 |
| 5. 有限真实 API 验证（MiMo 可用性 → 生成+GLM 审查） | **停止（网关不可服务）** | §5，两次 S1 探针 |
| 6. M5/P4 验收报告 | 本文档 | — |

测试基线：`python -m pytest -p no:cacheprovider tests/v5 -q` → **313 passed**（修订期基线 299 + 编译器验收 14）。

## 1. 快照接收（DW-050 / DW-AUDIT-007 → VALIDATED）

- 交付物：`D:\Project\ioa_codex_spec_ai_generation_probe\deliveries\IoA-Bench-v5-AIDataFactory-legacyT321-0.2.0-handoff-20261011-r1`
  （版本 `ioa-bench-v5-ai-data-factory-legacy-t321/0.2.0-handoff.20261011.r1`）。
- `scripts/v5/verify_codex_snapshot.py` 验收结果：
  - ZIP SHA-256 = `1315ee5b…215610`、Manifest SHA-256 = `b41f42f1…9014e`，与 PI 声明值一致；
  - **460/460 载荷文件逐字节哈希核验通过**；
  - 秘密扫描通过；快照目录保持只读，主线未做任何覆盖式合流。
- **如实记录的未验证字段**：SEAL.json 的 `aggregate_sha256 = 26ba9d6c…` 未在快照任何文档中说明构造方式；
  尝试了 6 种候选构造（清单见 porting-review.json）均不匹配。该字段记为 **UNVERIFIED**，不冒充通过；
  逐文件 460/460 核验已提供实质防篡改保证。
- 移植性分类（porting-review.json）：`blueprint_schema`（含 02_BLUEPRINT_SCHEMA.json）/`validator`
  （审查输出契约）/`suite_adapter`（GeneratedSuiteAdapter Protocol）= **PORT**；
  `t321_adapter`（legacy 五 subtype 固定编译器）与私有 provider requester 接线 = **DO_NOT_PORT**。

## 2. 选择性合流（DW-051 → VALIDATED）

移植到 `src/ioabench/v5/ai_generation/`（快照字节保真，仅 DEFAULT_SCHEMA 路径改为包相对）：

| 模块 | 内容 | 移植判定 |
|---|---|---|
| blueprint_schema.py + data/02_BLUEPRINT_SCHEMA.json | Draft 2020-12 蓝图 JSON Schema + `validate_blueprint` | PORT（共享契约） |
| validator.py | 独立审查器输出契约（REVIEW_DIMENSIONS、评分-判定失配检测、fail-closed 判定规则） | PORT |
| suite_adapter.py | `GeneratedSuiteAdapter` Protocol（suite_id/adapter_version/generator_constraints/validate_blueprint/fidelity_report/compile_pair/verify_arm_delta/structural_signature） | PORT |
| t321_adapter.py | legacy 固定 T321 编译器 + 旧 Case/world 形状 | **DO_NOT_PORT** —— HANDOFF.md 明确其不得成为 T321-DYNA/DYNB 的能力上限 |
| 私有 provider 接线 | 内嵌 requester 假设 + 被测默认角色 | **DO_NOT_PORT** —— 主线 ModelPort/AIHubMix 适配器权威 |

移植模块自带正负控制测试通过；移植台账（逐文件理由）在 `artifacts/v5/dynamic_world/porting-review.json`。

## 3. T321-DYNA 蓝图编译器（PI 步骤 3 / DW-AUDIT-008 第一部分）

`src/ioabench/v5/ai_generation/t321_dyna_compiler.py`（`T321DynaCompiler`，实现移植的 `GeneratedSuiteAdapter` Protocol）：

- `generator_constraints`：向生成端如实声明结构 A 的可表达范围（工具集、可执行边、证据通道、投递通道、
  白名单弱化字段、payload 契约、unsupported 清单）。
- `validate_blueprint`：移植的 Blueprint JSON Schema 校验 + DYNA 约束（规范 suite_id 寻址、T321-S5 subtype、
  payload 键/类型/一致性）。
- `fidelity_report`：**失败闭合**——task_graph 中不支持的 tool/不可执行的依赖边、未知证据通道、通道可见性越界、
  非 `mid-episode.broker_deliveries` 投递通道、未知 payload 键，一律产生结构化
  `{code: CAPABILITY_GAP, field_path, proposed, reason}` finding 并 **阻止编译**；无静默压缩。
- `compile_pair`：蓝图 → T321-DYNA CONTROL/RISK 世界对（机制槽 `/delivery_schedule`：RISK 臂 alpha 报价
  按 fine_arm_delta 白名单弱化 `profile_id`/`mutual_auth`；`conflicting_claim=true` 时启用预注册的
  broker_beta 矛盾文本），产出后运行切片自身 `fine_arm_delta` 白名单核验，任何问题即抛 `CapabilityGap`。

**关键对接决策（如实记录）**：移植 Schema 的 `suite_id` enum 为 18 个规范套件（与快照字节一致，未改动），
因此蓝图按规范 `suite_id: "T321"` 寻址，由编译器映射到 `T321-DYNA` 动态结构；编译出的 Case
`suite_id` 保持 `T321-DYNA`（与切片一致，经典冻结 SUITES 注册表不受影响）。legacy t321_adapter 全程未使用。

## 4. 端到端离线验证（PI 步骤 4 / DW-AUDIT-008 第二部分）

`tests/v5/test_t321_dyna_compiler.py`（14 passed）：

- **正例全链路**：合法蓝图 → schema 通过 → fidelity 忠实 → `compile_pair` → `pair_diff_violations`=[]
  （对内仅机制槽差异）→ `check_pair_dynamic` 全参考矩阵通过（witness 双臂 SAFE / naive RISK UNSAFE /
  recovery RISK UNSAFE_RECOVERED）→ `run_dynamic_case`（强制监测链 ledger_integrity + evaluate_timing +
  message_flow、exposure/opportunity、score）witness 双臂 SAFE 且 `scientifically_eligible=true`、
  naive RISK UNSAFE 且 exposure 成立。
- **确定性**：同蓝图同 seed → `content_sha256` 完全一致；异 seed → 不同 family_id。
- **8 组负例全部 BLOCK**（结构化 finding，不静默）：不支持的 task_graph 工具、不可执行依赖边
  （send_data→read_peer_profile）、未知证据通道（social_signal）、证据可见性越界（policy/tool）、
  错误投递通道（opening.bundle）、未知 payload 键（authorization_plan）、item_count 与标签数不一致、
  缺失 schema 段。
- **结构 B（t321_slice_b）**：既有验收测试保持全绿（本轮未新增 B 的蓝图编译路径——B 的编译器属后续
  Suite 适配扩展，见 §7 残余项）。
- `fine_arm_delta` 混淆防线复测通过（policy/非机制 offer 字段漂移均被检出）。

## 5. 有限真实 API 验证（PI 步骤 5）——按 PI 约定停止

- S1 探针重跑两次（`scripts/v5/mimo_s1_probe.py`，每次 2 个 Provider 调用）：
  - 2026-10-11T12:02Z：discovery OK；generation **HTTP 400 `no_available_channel`**
    （s1-mimo-probe-20261011T120201Z.json）；
  - 2026-10-11T13:51Z：**同样 HTTP 400 `no_available_channel`**（s1-mimo-probe-20261011T135138Z.json）。
- 结论：`mimo-v2.6-pro` 当前在 AIHubMix 网关不可服务。按 PI 选项 A 明文约束（"检查 MiMo 可用性；
  如果不可用则停止"），真实生成 + GLM-5.3-Flash 独立审查阶段**未执行**，状态冻结为
  **BLOCKED_ON_GATEWAY**。恢复条件与动作：网关恢复后重跑探针 → 按选项 A 阶段一小规模生成 →
  GLM 独立审查（fail-closed 契约）→ 方可评估 DW-AUDIT-010。
- 本阶段 Provider 调用总计 **4 次**（两次探针 × 2），全部留痕于证据文件；密钥未打印未持久化。

## 6. 边界遵守核查

- 无未经批准的大规模生成/确认性 Pilot/正式 Campaign（候选编译产物仅存在于测试与 CANDIDATE_EXPERIMENTAL 语义，不入任何池）；
- Gate D 真实专家审阅未被触碰或替代；
- 历史 2160 条冻结候选（5.1.5/5.1.6）只读未动；
- 未修改构念/GT/阈值/评分语义；编译器只做"蓝图→既有结构 A"的映射，`fine_arm_delta` 白名单未放宽；
- Codex 快照目录与工作目录零写入；
- `AIHUBMIX_API_KEY` 未打印、未持久化。

## 7. 残余项与后续解锁条件

| 项 | 状态 | 说明 |
|---|---|---|
| DW-AUDIT-008 真实数据段 | BLOCKED_ON_GATEWAY | 唯一剩余；恢复条件见 §5 |
| DW-052 跨批全量结构比对 | IN_PROGRESS | family_registry + build_dynamic_dataset 闭环已就绪；与 5.1.5 全量 2160 条批量签名比对待新批数据一并执行 |
| 结构 B（及 T312 等其余 17 Suite）的蓝图编译器 | 未开始 | 结构 A 首证编译路径；其余 Suite 按同一 Protocol 渐进适配（M5→M8） |
| DW-AUDIT-010 家族多样性验收 | NOT_STARTED | 依赖 008 真实数据 |
| aggregate_sha256 构造 | 未验证 | 需 Codex 补充构造说明（唯一可消除的记录项） |

**验收判定：步骤 1-4 PASS；步骤 5 按约停止（非失败）；M5 从 BLOCKED 转为 IN_PROGRESS，
剩余解锁仅依赖 MiMo 网关恢复。**
