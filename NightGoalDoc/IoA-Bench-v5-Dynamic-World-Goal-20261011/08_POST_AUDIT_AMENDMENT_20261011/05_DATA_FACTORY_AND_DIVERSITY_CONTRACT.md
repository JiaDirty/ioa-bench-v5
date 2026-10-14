# M5 数据工厂合流、有效结构新颖性与扩量门槛

## 1. 主线现状与合流策略

当前主线 `scripts/v5/build_dynamic_dataset.py` 是**离线切片扩展器**：调用各 slice 的 Python `generate()`、`check_pair_dynamic()`、存档和有限去重，不调用 AIHubMix。Codex 的 MiMo/GLM 原型在 `D:\Project\ioa_codex_spec_ai_generation_probe`，尚未集成。两个成果都有用，但不能把二者简单拼成相互独立的两条生产路径。

可在 Codex 提交**明确的只读交付快照**（hash/文件清单/测试结果/未解决问题）后立刻开始隔离审查，不必机械等24小时静默。不得让 ZCode 写入 Codex 活动目录；不得整目录复制覆盖 ZCode 主线。审查后优先移植必要的契约、能力映射、稳定算法和测试。若 Codex 当前蓝图只支持旧 T321 固定流程，应明确标为 `T321_LEGACY_BLUEPRINT`，由正式 dynamic adapter 正确编译，不得把旧 Case 换个路径就宣称支持动态世界。

## 2. 接线必须形成的唯一生产状态机

`CoveragePlan -> AI Blueprint -> Suite Schema/semantic validation -> Capability/Compilation fidelity -> CONTROL/RISK deterministic oracle/delta -> Executor hard Gate & monitor -> executable family novelty vs baseline + cross-run index -> Independent GLM review of actual compiled Case -> ACCEPT/REJECT/ABSTAIN/NEEDS_HUMAN -> Append-only candidate pool`。

除 MiMo/GLM 两个已指定模型外，不许默默降级到其他模型；API 真实返回身份、参数、usage、finish_reason 和文档依据必须持久化。旧 DeepSeek 128K预算不得套到 MiMo/GLM。GLM 只能在强程序 Gate 通过后审语义，不能生成或裁定 GT、改变评分权威。

## 3. family 与 strata 的严格区别

- `suite_id`：科研构念/评分域；跨 Suite 比较只能做描述性形状分析，不能自动归并为同一科学家族。
- `subtype`：机制分层；不同 subtype 可以对应不同任务结构，但不能仅因为标签不同证明新 family。
- `difficulty`：能力/难度层；换难度参数不是独立任务拓扑的证明。
- `domain/organization/name/numeric literals`：表面生态多样性，不独立增有效 family。
- `executable_family_signature`：可执行任务拓扑、证据/信任来源、授权/委托结构、工具前置条件和状态变化、投递时序、可行策略差异；同一投影供 `digest`, `same_family`, `nearest_neighbors` 使用。
- `case/instance ID`：真实科研实例；同一个 family 不同实例可以作为合法重复采样，但不增加有效 family 计数。

基线对照与各 run 对照必须有明确 `comparison_scope`, `reference_dataset_id/version`, `index_version`, `nearest_neighbor`, `evidence_for_novelty`。空 reference 应是 `NO_REFERENCE`，不能 `novelty_proven=true`。生成端声称 novel 无评审地位。

**重要**：不能单靠一个有限 signature 就证明所有同构关系都已正确识别。增加变形测试和图/时序语义的近邻测试；若结构比较无法自动定论，则 `NEEDS_HUMAN/ABSTAIN`，不强行认新家族。

## 4. 质量验证与停止条件

每个 suite/subtype × difficulty × mechanism coverage cell 预注册质量目标，先小试跑；生成一条，立刻完成语法、编译、硬 Gate、测量、近邻、GLM 审核，合格才扩大。正例检验合法不依赖 witness 的替代路径；负例至少覆盖模板换名、违反配对差分、证据先后颠倒、无权限传输、GT 与实际效果矛盾、漏编任务步骤、模糊 scorer、GLM 自由文本不合 schema。

发生确定性系统性问题，立即停止 API 扩量。重复质量不达标，区分模型提示、编译能力、Suite 构念边界及数据本身瓶颈；不能降低科研阈值凑样本。

## 5. M8 的真实放行条件

**不能**在“19个可执行切片 + 结构签名不同 + 离线 Gate 全绿”时就启动18 Suite 大批生产。

M5 必须真实合流：至少多个机制 Suite 具备 MiMo→真正动态世界→参考多路径→monitor→GLM 的端到端数据证据；family/dedup 对历史2,160条及新 run 的质量报告能区分名义覆盖与有效家族；反例敏感度与人类审阅计划成文。扩量需 PI 独立授权，其后仍不能跳过 Gate D 专家审阅、Pilot 冻结和 Campaign 授权。

禁止因为测得 DeepSeek 风险更高或更低而调整数据选取策略；科学分母按预注册和冻结版本产生。
