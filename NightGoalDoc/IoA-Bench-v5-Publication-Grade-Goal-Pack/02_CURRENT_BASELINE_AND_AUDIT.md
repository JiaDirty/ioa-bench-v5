# v5 当前真实基线与待证事实（快照日期：2026-10-10）

本文件不是每日自动更新的进度报告。真正的权威是当前工作区的 `docs/v5/V5_PROGRESS.md`、`docs/v5/PROJECT_PROGRESS_18_SUITES_20261010.md`、`docs/v5/V5_PI_DECISION_LOG.md`、`state/PROJECT_STATE.yaml` 的 `v5` 节、现场源码和验证产物。每次新会话以这些磁盘证据为准，不从本文件硬推当前状态。

## 研究对象与历史

研究对象：**被测模型在受控 Internet-of-Agents 场景中的可观察内生安全行为**。IoA 架构是实验支架而非评分对象。18项 canonical taxonomy 不变。T361–T363 `SIMULATION_ONLY`。

v4.1.13 历史正式运行曾完成，2026-10-04 科学审计判为 `NOT_SCIENTIFICALLY_READY`。其1620条历史正式案例及报告/Replay/Release 仍须保留，仅为历史证据，不能当成 v5 科学达标。

## v5 已有成果（2026-10-10静态快照）

- 18/18 项均已实现独立 suite/场景/生成器/scorer/参考策略；共同引擎已搭建，**不是等待从零实现**。
- 用户上传的源码快照记录 `tests/v5`: 71 passed；离线矩阵 18 × 60对 × 3种子 = 3,240/3,240 通过。这证明程序和脚本参考策略的离线行为，**不证明真实模型表现、数据语义质量或科研效度**。
- `5.1.5-candidate-20261006`：18 × 60 pairs × 2 arms = 2,160条候选案例；自动 Gate C 18/18 检查通过，**未冻结**。当前数据主要是参数化程序生成；`naturalize_phrasebank.py` 的存在不等于 AIHubMix 大规模多样化数据已完成。
- T332 `t332-scenario-5.1.1` 有定向场景接口修复；`5.1.6-candidate-20261009` 是 **仅T332局部候选**，不是所有18项统一升级。
- 历史四模型 Pilot `pilot-20261006-v5.1.5`：864终态；整体验收因请求 Llama 却返回 Gemma 等问题及部分套件失败而 INVALID。DeepSeek 的216行是**探索性诊断**，不能追认新版正式 Gate E。
- 2026-10-09 `PI-V5-005`：唯一正式被测模型 = AIHubMix 请求 ID `deepseek-v4.1-flash`，历史响应元数据为 `deepseek-v4-1-flash-260910`；取消多模型正式比较。`PI-V5-006`：**任何新的付费 Provider 调用均须用户明确批准**。
- Gate D 已备好单模型审阅材料和协议，但独立人工/领域专家标签为0。Gate E 需新的确认试点。Gate F冻结、Gate G正式运行、Gate H正式结果均未完成。

## 已识别的在线诊断线索（不是已经证明的根因全集）

- 历史 DeepSeek 216行：186 `COMPLETED`、26 `INVALID_MODEL_OUTPUT`、4 `BUDGET_EXCEEDED`。某些输出可能受 4096-token 限制影响；未来 protocol 已提议 `max_tokens=8192`，但**未在线证实修复**。
- T332：历史重复查询导致预算耗尽，修复后未验证；T333：高 scorer abstain；T331：CONTROL utility不足；T352：大量无效输出。不要假设这些故障全由 API 或全由场景引起。
- 对照已检索官方文档的既有人工代码审阅线索：模型多轮工具调用的 `reasoning_content` / reasoning detail 保留回传、HTTPError/URLError 捕获顺序、Provider身份响应头、Exposure mechanism-level proof、Pilot混合候选版本、case完整性检查。**逐项在当前源码中复现/确认再修复，不因报告提及而盲目改代码**。

## 证据入口

- `docs/v5/PROJECT_PROGRESS_18_SUITES_20261010.md`
- `docs/v5/V5_00_ARCHITECTURE_DECISION.md`
- `contracts/v5/construct_maps.json`
- `docs/v5/V5_PI_DECISION_LOG.md`
- `docs/v5/V5_03_STATISTICAL_ANALYSIS_PLAN.md`
- `docs/v5/V5_04_REVIEW_PROTOCOL.md`
- `docs/v5/V5_SINGLE_MODEL_CONFIRMATION_PLAN.md`
- `artifacts/v5/pilot/pilot-20261006-v5.1.5/deepseek_single_model_diagnostic.{md,json}`
- `artifacts/v5/gates/offline-matrix-20261009-single-model-precheck.json`

**限制：** 2026-10-10上传的“源码审阅包”未包含完整在线 Pilot 原始轨迹、所有 reviewer artifacts、历史完整回放。缺失证据标 `UNKNOWN`，不能把未读取材料解释为不存在。
