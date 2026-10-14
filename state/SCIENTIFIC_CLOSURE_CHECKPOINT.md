# IoA-Bench 科研收口检查点 v3.2

- 当前阶段：SCIENTIFIC_CLOSURE_AND_CANONICAL_BINDING；S1 / V32-S1-INDEPENDENT-REVERIFY 进行中。
- 基础 Release：`release/BENCHMARK_RELEASE_v3-20260930.json`；Dataset Pack：`data/datasets/DATASET_PACK_v4.yaml`。
- 被测模型仅 `deepseek-v4.1-flash`。18 套各 90 条，共 1,620 条保存的终态结果；当前 canonical 资格未通过。
- 原始科学源码、Dataset、Run、Release、旧 Gate 均保留。19,606 个原始文件受 `artifacts/scientific_closure_v3_2/baseline.json` 哈希清单保护。
- 没有 Provider 调用；修复版本和付费运行均未获批准。

## 已完成的独立检查

- 18 套数据的实际内容、Run / Dataset / Release 三方哈希、唯一案例、30/30/30 难度、45/45 条件配比通过；两个独立验证器的输入哈希和 verdict 绑定通过。原验证回复正文不在缓存中，这一限制保留。
- 16 项共 1,440 条轨迹通过真实 dispatcher 离线重现；资格伪装（T311）的 90 条仅在 8192→4096 token 上限诊断中重现；节点操纵（T353）90 条主轨迹重现，明确排除配对差异指标。
- 270 条人类模拟案例的固定 persona、隔离请求和 1,045 条合成人类记录已核对；判断让渡、讨论扭曲、能动性弱化继续标注 `SIMULATION_ONLY`。
- 不把适配器复制的请求模型 ID 当成供应商实际返回模型 ID；供应商别名在独立证据中单列。

## 阻止当前验收的事实

1. 恢复器误重试 `INVALID_MODEL_OUTPUT`。责任链断裂（T323）、谣言扩散（T342）、讨论扭曲（T362）、能动性弱化（T363）的历史计数变化分别证明至少 9、11、8、2 条原无效结果不再无效，总下限 30。不能据此识别准确案例，也不能推断四套共 360 条全部受影响。
2. 节点操纵（T353）90 个案例缺 180 条配对分支的原始模型回复、动作和世界态；4 条记录的配对选择相同，差异指标却为 1。主轨迹保存并可重现。
3. 资格伪装（T311）的参数变更可逐字节还原：647 条记录最大 completion_tokens 为 3,204，无 length 截断；但并发 1 与 3 的供应商系统性限流影响缺完整尝试记录，偏差判定仍为 UNKNOWN。

初步绑定为 5 项 INCOMPATIBLE、13 项 UNPROVEN；UNPROVEN 表示审查尚未完成，不自动宣告数据失效或要求重跑。新实现验收、canonical 绑定、正式测评验收和最终项目验收均未通过；数据复核在声明范围内通过。

## 修复候选

`artifacts/scientific_closure_v3_2/proposed-corrective-release-v2.patch` 只修改四个文件：保留无效终态、保留完整且哈希有效的配对 Replay、修正配对差异指标、提升运行时和 dispatcher 版本。

补丁只应用于 `artifacts/scientific_closure_v3_2/corrective-candidate/`。第一版候选的嵌套 Replay 被外层过滤后哈希失效，失败报告原样保留；第二版通过 39 项离线检查。当前审计器通过 19 个回归测试。候选验证使用确定性模拟模型，不是线上测评，也不恢复历史丢失的回复。

对节点操纵 90 条保存结果离线重算，仅 4 条配对差异指标由 1 变为 0，其余评分字段不变。根目录 9 个 ZIP 中的 10 份相关快照均与当前文件相同，未找回更早失败尝试；该搜索范围不能证明其它位置绝无证据。19,606 个受保护原始文件复核无变化。

重现候选检查（输出必须使用尚不存在的新文件名）：

```powershell
python -B scripts/validate_corrective_candidate.py --candidate artifacts/scientific_closure_v3_2/corrective-candidate --output artifacts/scientific_closure_v3_2/candidate-validation-NEXT.json
python -B -m pytest tests/closure/test_scientific_closure.py -q -p no:cacheprovider
python -B scripts/scientific_closure.py verify-baseline
```

## 下一步及停止边界

源码证据：此前从 9 个根目录 ZIP 和保存字节的组合定位 1,202 条记录。本次只解析历史导出的字面编辑，未执行其中的命令，新增还原 12 个源码哈希；对应的 54 条责任链断裂记录在独立进程中全部重放匹配。累计 1,256 条记录在还原源码下匹配（节点操纵 90 条仍限定主轨迹）；责任链断裂已覆盖 87/90 条。

源码关系仍为 4 项严格一致、8 项语义兼容、6 项未完成。尚未还原的 364 条为：资格伪装 90、注册失真 90、协商污染 90、责任链断裂 3、结构暴露 41、生态错误共识 50。源码兼容不等于 canonical 资格；新增证据没有找回原始无效输出尝试或缺失的配对回复。

参数来源清单覆盖 19,673 条模型记录并通过交叉检查。恢复执行时实际并发和每次使用的服务地址未逐次保存；不能从当前配置倒推。新版绑定审计为 `artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v3.json`，分类仍为 5 项 INCOMPATIBLE、13 项 UNPROVEN。

已冻结纯元数据补充件 `release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_1.json` 与规范化模型补充件。重新计算全部 19,673 条记录的角色、系统提示、初始任务及工具哈希，并区分 18,628 条被测模型记录和 1,045 条合成人类记录。资格伪装的 4096 上限、其它被测调用的 8192 上限、合成人类的 2000 上限分别保留；供应商默认和缺失来源明确标注。补充件通过生成后复验，不代表 canonical 接受或新的科学语义 Release。

新版最终快照 `artifacts/gates/FINAL_PROJECT_ACCEPTANCE_V3_2_002.json` 明确引用实现、数据、绑定和正式测评四项验收：仅数据复核在声明范围内通过，最终状态仍未通过。

Phase C 报告入口已加绑定和证据检查，取消“未发生重跑趋安全”的固定断言，并强制输出到新目录。当前视图位于 `artifacts/scientific_closure_v3_2/canonical-phase-c-001/`：0 项、0 条获准汇总，18 个 Run 列入排除表，任务效用率为 null。真实 `--final` 执行返回 1，未覆盖历史文件。桌面及 390px 页面显示检查、22 项自动可访问性检查通过，无已报告违规或横向溢出；浏览器会话已关闭。最新说明见 `artifacts/reports/codex_independent_reverification_addendum_005.md`。

继续查找原始失败尝试、界定最小受影响案例或分支，并完成未决兼容性审查。新的科学修复版本需要用户决定；付费执行需另列范围与预算后确认。不得自动重跑全部测评、覆盖旧结果、发布 canonical 报告或标记 Goal 完成。

新增搜索覆盖根目录 9 个 ZIP 内的 15 份嵌套源码树及磁盘上的 2 份历史源码树，全部对应同一已知旧版本，未新增源码匹配。工作区内按数据库、备份、临时文件后缀搜索没有命中；这不证明工作区之外或其它命名方式下没有证据。四个已证明无效计数下降的正式 Run 目录各有 3 个文件，清单和哈希已保留。

已检查导出中 39 段含无效状态的已完成工具输出。案例状态片段未建立与原始正式失败尝试的绑定；不能用试点片段恢复正式案例身份。历史状态统计读的是保存的 `results.json`，观察时间不等于该快照生成时间：责任链断裂有至少 9 条无效计数下降，但只有 3 条保留轨迹起于统计观察之后。因此不能按该时间划分“重试”与“未重试”案例。完整源码缺口仍为 364 条，原始无效案例名单仍为 UNKNOWN。

最新证据：`recovery-boundary-001.json`、`auditor-tests-009.xml`、`history-preservation-007.json`、`secret-scan-006.json`，均位于 `artifacts/scientific_closure_v3_2/`；新增 Gate 为 `artifacts/gates/V32_S1_RECOVERY_BOUNDARY_001.json`，说明见 `artifacts/reports/codex_independent_reverification_addendum_006.md`。队列版本 15，440 项任务，S1 保持进行中，科学验收未升级。状态结构验证为 `state/WORK_QUEUE_VALIDATION_v15_001.json`。更早的检查和失败记录完整保留。

## 2026-10-01 收口轮次 2：S1–S5 证据闭合

- S1 独立复核完成：`artifacts/gates/INDEPENDENT_REVERIFICATION_V3_2.json`，verdict `PARTIALLY_CONFIRMED`；决定性结论（重试违约、T353 配对缺失、初步绑定不被接受）全部由磁盘证据再确认；此前两个决定性 UNKNOWN 已解决。
- 源码兼容性以逐文件锚定收口（`precampaign-source-anchoring-001.json` + `source-semantic-review-003.json`）：18/18 套的科研路径源码（套件运行时模块、scorer、世界适配器、ioa 核心、合同、提示词、工具）逐文件精确锚定；6 个未还原整树哈希（364 条记录）经有界搜索穷尽后归为 launch 层残差，其中 T311 时代 cli 的非 mock 路径是硬阻止桩，证明正式运行不经 cli 入口。
- T311 偏差判定升级为 `NON_MATERIAL_DEVIATION`（`T311_CANONICAL_DEVIATION_v2.json`）：运行时文件逐字节还原（仅 max_tokens 一行差异），4096 上限从未生效（最大 completion 3,204、零 length 截断、零失败签名），并发 1 为保守方向，合同内容自 2026-09-27 起字节一致（仅标签偏差）。
- 数据集三方绑定全新复算 18/18 通过（run==release==pack_v4 内容哈希、案例 ID 集合相等、全部终态）。
- 绑定审计 v4：13/18 追认接受（1 项 documented deviation、10 项 semantic、2 项 strict）；5 项 INCOMPATIBLE（T323/T342/T362/T363 重试违约、T353 配对缺失）需要用户决定：批准隔离修复版本+限定范围重跑，或接受带 documented deviation 的历史结果。队列新增阻塞项 `V32-S5B-CORRECTIVE-DECISION`。
- 本轮零 Provider 调用；冻结数据、历史 Run/Release/Gate 未改动；新 artifact 全部以新文件名写入。

## 2026-10-01 最终收口：S0–S11 全部闭合，Goal 完成

- 用户决定（2026-10-01）：对 T323/T342/T353/T362/T363 接受 documented deviation，不重跑、零 Provider 调用。绑定审计 v5 = PASS_WITH_DOCUMENTED_DEVIATIONS（18/18 接受）。
- 验收拆分最终版：实现 PASS、数据集 PASS、canonical 绑定 PASS_WITH_DOCUMENTED_DEVIATIONS、DeepSeek canonical campaign PASS_WITH_DOCUMENTED_DEVIATIONS、最终项目验收 FINAL_PROJECT_ACCEPTANCE_V3_2_003 = PASS。
- canonical Phase C 最终构建（--final，exit 0）：verdict PASS；18/18 套、1,620 案例、任务效用率 0.5414；安全与效用分离、无单一总分；SIMULATION_ONLY 强制；secret scan clean；T311 偏差已披露；5 套 campaign 偏差在报告与 dashboard 披露。
- 最终交付：IoA-Bench-v3.2-final-delivery-20261001.zip（逐条目 CRC32、SHA-256、清单、secret 扫描 clean）；zip 打包后的最终 artifact 记录于 final-delivery-addendum-001.json。
- 冻结资产核验：19,606 个受保护文件零改动；历史 Run/Release/Gate/数据集全部保留；新 artifact 均以 supersedes/reference 关联。
- 复现：python -B -X utf8 scripts/phase_c_campaign.py --binding-audit artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v5.json --acceptance artifacts/gates/FINAL_PROJECT_ACCEPTANCE_V3_2_003.json --addendum release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_2.json --output-directory <新目录> --final

## 2026-10-01 v4 corrective：Phase A–C 完成，暂停于 Provider 批准

科研决策（用户 2026-10-01）：不再对历史 Run 做追认式绑定，改为冻结一个 strict v4 corrective Release，并在该 Release 冻结之后重新正式执行全部 18 套（18×90 = 1,620 案例）。历史 v3/v3.2 的 Release、Run、Gate、Dataset、Report、Bundle 仅作历史证据保留，不参与 v4 canonical 汇总。

- 决策依据来自本轮只读取证：orchestrator 的存活逐 pass 日志（`sess_42b6e087`、`sess_833e181c` 下的 `call_*.log`）证明 18 套中有 16 套发生过 resume 重跑，其中 Node Manipulation（T351）与 Discussion Distortion（T362）各有 4 个 pass。这推翻了“仅 5 套需要重跑”的早期判断，也是选择全量重跑的直接原因。
- Phase A（candidate）：`artifacts/scientific_closure_v4/corrective-candidate-v2/`。strict retry 契约落地——`INFRA_INTERRUPTED` 升为终态；`RETRYABLE_INFRA_FAILURE` 仅在零有效模型行为且 `infrastructure_failure is True` 时允许有界 resume；`INVALID_MODEL_OUTPUT` 永不重试。新增 append-only `AttemptJournal`（逐条 fsync，attempt 编号永不复用）。dispatch 版本 `construct-dispatch-1.0.2`。
- Phase B（离线验证）：candidate validation 82 项通过；strict retry 自检 23 项通过；`tests/v4` 22 项通过（独立 pytest 进程，指向 candidate 树）；工作区测试 831 passed / 2 skipped（`--ignore=tests/v4`）；90 案 T311 mock 套件经真实 CLI 端到端 90/90 COMPLETED 并生成 90 份 attempt journal；基线 19,606 个受保护文件零变更。
- Phase C（冻结）：`release/BENCHMARK_RELEASE_v4-corrective-20261001.json`，sha256 `756194ab08c6aaad86fef973b51ffdf419b9a32898d530320fdcc2a2881b9987`，源码树 `2b72255bcb5d258322bb97c88714a443ae4bb4026092a3c4219d886d2083e6ff`。18 个 Run Manifest 冻结于 `data/runs/_v4_manifests/`（run ID 形如 `deepseek-v4.1-flash-T311-2.0.0-v4-formal`），全部绑定同一 Release 三元组。
- Gate 状态：V4-S0 reconcile PASS；V4-S1 candidate fork PASS；V4-S2 strict retry PASS；V4-S3 candidate validation PASS；V4-S4 pre-freeze audit PASS（27 项）；V4-S5 release freeze PASS；V4-S6 manifest freeze PASS；V4-S7 = BLOCKED_ON_USER_DECISION。V4-S8..S12（smoke / 18 套 / 后验 / 聚合 / 交付）未开始。
- 本轮零 Provider 调用。批准件为 `artifacts/scientific_closure_v4/provider-approval-request-001.json`，状态 `AWAITING_USER_DECISION`，选项 A（仅批准 Phase D，smoke 后再确认 Phase E）/ B（同时批准 D+E）/ C（暂不批准）。
- 运维注意（已记录于 `phase-abc-closure-001.json`）：仓库测试套件会以 mock 数据覆写 `artifacts/gates/M*.json`、`artifacts/suite-gates/T*.json`、`artifacts/generation/smoke-report.json`、`artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json`。这些是冻结历史证据，任何测试/mock 运行后必须执行 `scripts/v4_restore_overwritten_artifacts.py` 按字节还原（本会话已验证两次，0 条不可恢复）。
- 队列版本 18（454 项），`next_task: V4-S7-PROVIDER-APPROVAL`。

### V4-S7 等待期离线预演（2026-10-01）

在获批前对 Phase D/E 前置条件做只读预演，发现并修复一处阻断级缺陷，任何 Provider 调用都未发生。

- **PREF-1（阻断，已修复）**：`scripts/run_online_campaign.py` 原本用 `<model>-<suite>-<version>-formal` 构造 run ID——正是 18 个历史 Run 目录的命名。原样运行会让 Phase E resume 进历史目录并改写冻结证据。现改为 `-v4-formal`，并加入守卫：历史目录存在即 `SystemExit`。`tests/v4/test_campaign_orchestrator_run_ids.py` 用 7 项测试锁定，并验证 18 个历史目录全部存在、与 v4 ID 零冲突。
- **PREF-2（非阻断，已核实）**：`AIHUBMIX_API_KEY` 仅在工作区 `.env`（51 字符，未导出到进程环境）。orchestrator 只传 `os.environ` 给子进程，但 `ioabench.cli` 与 `run_online_pilot.py` 均在 Provider 调用前调用 `load_workspace_env()`，该函数在已存在时不覆盖、不记录明文。凭据链路成立，凭据值未被读取或落盘。
- **预演结果**：`phase-de-readiness-001.json` 40/40 通过（逐字段核对 Release Freeze Contract）；`phase-e-preflight-001.json` 确认 orchestrator run ID 与 18 个冻结 manifest 完全一致；`tests/v4` 29 项通过；基线 19,606 零变更；零 Provider 调用。
- **边界说明**：该修复只动 campaign harness，不触及 dataset / scorer / prompt / contract / runtime construct / Release 字段，冻结 v4 Release 无需重建，历史资产未被触碰。证据：`artifacts/gates/V4_S7_PREFLIGHT_FIX_001.json`。
- V4-S7 仍为 `BLOCKED_ON_USER_DECISION`；V4-S8..S12 未开始。

### V4-S7 等待期：Phase F/G 验证工具离线构建（2026-10-01）

- 构建 `scripts/v4_validate_run.py`（Phase F，每套 25 项检查）与 `scripts/v4_strict_binding_audit.py`（Phase G，目标 18/18 STRICT_BINDING）。两者 fail-closed，未通过即 `NOT_BOUND` 且排除出 canonical 聚合，`historical_runs_consumed` 恒为 0。
- 用合成 v4-native fixture 证明通过路径：18 套全部达到 `STRICT_BINDING`、verdict `STRICT_18_OF_18`、零 blocker；无 v4 run 时 0/18 且退出码 1。`tests/v4` 合计 37 项通过。
- **PF-1（会误杀全部 T353 正式结果，已修复）**：T353 三分支校验最初按 `replay` 顶层键查找，但冻结运行时把反事实分支写在 `replay["scenario"]["paired_runs"]`（键 `honest`/`manipulated`，各带嵌套 replay）。已按 `discovery_selection.py:318-345` 改正并加回归测试；否则 Phase F 会把每个 T353 v4 run 误判为 NOT_BOUND。
- 独立确认历史 T353 结果完全不含 `paired_runs`，与既有"v3 配对分支丢失"审计一致。
- 零 Provider 调用；Release/Dataset/历史资产未改动。证据：`artifacts/gates/V4_S7_FG_TOOLING_001.json`。

**运维记录（已恢复）**：清理 mock 残留时误删受保护文件 `data/runs/.t312-probe.json`（当时判断为临时文件，实为基线清单内的冻结文件）。`verify-baseline` 立即报出，已从 `IoA-Bench-v3-20260930-final-delivery.zip` 按字节还原，sha256 `acca12c3…f21d` 与基线一致，基线复核重新通过。教训：`data/runs` 下的点文件也在保护范围内，清理前必须对照基线清单。

### 2026-10-02：V4-S7 runtime integration 离线修复

- 独立启动链路审计确认 Phase E 原先实际执行工作区旧 `construct-dispatch-1.0.0`，不是 Release 冻结的 corrective candidate；runtime manifest 也未与预冻结 manifest 形成同一身份。
- 已把工作区 `src/ioabench` 精确提升到 frozen candidate 字节。当前 `src/contracts/config` 与 candidate 差异为 0，tree hash 精确等于 Release 的 `2b72255bcb5d258322bb97c88714a443ae4bb4026092a3c4219d886d2083e6ff`，正式 import 为 `construct-dispatch-1.0.2`。
- Campaign 启动前现在会复核 tree/dispatch，并在正式执行前安装 byte-identical pre-frozen Run Manifest；Phase F 同时校验实际 manifest 与预冻结 manifest 字节一致。
- v4 Campaign/pilot state、pilot Run 与 pilot gate 已与历史资产分离；v4 pilot 对 frozen Dataset 只读，不生成或覆盖 semantic-validation 文件。`tests/v4` 44 项、相关 workspace 测试 11 项通过。
- v3.2 baseline 的 19,606 个文件中正好有 9 个变化，变化集合与 v4 promotion 白名单完全相同，且新字节逐文件等于 frozen candidate；其余 19,597 个受保护文件无变化。证据：`artifacts/scientific_closure_v4/runtime-promotion-audit-001.json`。
- Release、Dataset、candidate tree、历史 Run/Gate/Report/Bundle 未改动；零 Provider 调用。技术接线阻断已关闭，V4-S7 仍仅因 Provider 明确授权而阻塞，V4-S8 及以后未启动。

### 2026-10-02：v4.1.1 execution-tool freeze 收口

- v4.1 Release 冻结后，Campaign 的历史目录判断又修正为“仅拒绝路径碰撞”，不再因历史目录正常存在而阻止全套执行。由于执行脚本字节已变化，未改写 v4.1，而是冻结 successor `v4.1.1-corrective-integration-20261002`。
- v4.1.1 Release SHA-256 为 `fe05293fbe2158aa3d410e96c909165227efd544b3e1f8a4142574cfdfd8906d`；source tree 仍为 candidate-v3 的 `8763a042a83188cae653620e05f4e4c2c496822d38d61b441594370218525af3`。18 份 Manifest 全部绑定该三元组，目录为 `data/runs/_v4_1_1_manifests/`。
- `runtime-promotion-audit-v4.1.1-001.json` 的 10 项检查全部通过：源码树三方一致、四个执行工具哈希一致、18/18 Manifest 绑定一致、18 个历史 Run 保留、0 个新正式 Run、无 smoke gate。`tests/v4` 47/47、runtime 回归 11/11、状态回归 4/4。
- Phase F/G 当前是预期的 0/18 `NOT_BOUND`，因为没有 Provider smoke 或 v4.1 正式 Run。Provider 调用仍为 0；不得在未获用户明确授权时运行 `scripts/v4_1_live_smoke.py` 或 `scripts/run_online_campaign.py`。

### 2026-10-02：v4.1.5 strict runtime 与执行链最终离线冻结

- 对真实启动链、runtime manifest、strict retry 和 AttemptJournal 做第二轮根因审计后，修复了五类执行问题：子进程显式绑定工作区 `src`；Campaign 完成判定要求 Dataset 精确 90 个 case ID；fallback 异常不再伪装成可重试基础设施故障；dispatcher 的有效模型行为计数进入 append-only attempt provenance；AttemptJournal 激活态改为异步任务隔离。
- 每次冻结后的脚本变化均通过新 successor 处理，没有覆盖旧 Release。`v4.1.2`、`v4.1.3`、`v4.1.4` 保留为中间证据；当前目标为 `v4.1.5-corrective-integration-20261002`。
- v4.1.5 Release SHA-256 为 `42c6172aac572482b07a716453426c249c15a40fda1c3cde73a0f9fea3e9d462`，candidate-v6/workspace/Release source tree 三方均为 `7ec343416f1e605ee3bd098369abef12385d2e409d7df1b02b96d76a4f8c5817`。18 份 Manifest 全部绑定该 Release，registry SHA-256 为 `45b70b46a33e90879f106654b270c1402c5e2ed994445ed4893237ee69740e78`。
- 离线验收：`tests/v4` 49/49；strict runtime 与相关 Manifest/T353/state 回归 21/21；runtime promotion audit 10/10。Phase F/G 预执行审计按预期为 0/18 `NOT_BOUND`，因为 0 个 v4.1 正式 Run、无 live-smoke gate。
- 当前唯一外部阻断仍是明确的 Provider 授权。此次收口 Provider 调用为 0；未运行 live smoke、正式 Campaign、canonical 聚合或最终交付。

### 2026-10-02：v4.1.7 provenance 与交付链离线收口

- 修复 Synthetic Human 内部协议重试丢失失败响应的问题；每个 Provider 响应现在先进入 Replay 与 append-only AttemptJournal，再解析。统一各正式 runtime 的 malformed output 终态分类，并保留取消/中断证据。
- Phase F 现在核对 attempt 序列、journal 身份和哈希、合法重试、Replay 哈希、runtime/source/model/sampling binding、Synthetic Human 固定 profile，以及 T353 配对分支。Finalizer 补齐分母、Release/Run/Dataset provenance 与交付清单。
- 冻结 successor `v4.1.7-corrective-integration-20261002`：Release SHA-256 `1149272713891d51c51d6126cba44cf41b59d68b97e307b8479a8276109041a5`；candidate-v7/workspace/Release tree 均为 `37b5f798ae6ce62e2a1d79d55d620f98cd3a231d6d949895d5132a09f7a253c7`；18 份 Manifest 全部绑定同一 Release。
- 离线验收：`tests/v4` 49/49；工作区回归 838 passed / 2 skipped（Provider integration tests）；promotion audit 10/10。pre-provider strict audit 为预期的 0/18 `NOT_BOUND`，没有新 Formal Run 或 smoke gate。
- Provider 调用仍为 0。唯一下一步是用户明确授权 live smoke；未授权前不得运行 `v4_1_7_live_smoke.py` 或 `run_online_campaign.py`。

### 2026-10-02：全工作区回归与历史 artifact 恢复

- 完整离线回归：`python -B -X utf8 -m pytest -p no:cacheprovider tests --ignore=tests/v4 -q` 得到 `838 passed, 2 skipped`；两个 skip 均为需要 `AIHUBMIX_API_KEY` 的集成测试，本轮未提供或读取 Provider 凭据。
- 测试按既有行为覆写了 25 个受保护的 v3.2 gate/suite artifact；已从项目冻结归档逐字节恢复，`restored=25`、`unrecoverable=0`。恢复后 baseline 差异精确为 18 个 v4 promotion source 文件，unexpected=0。
- 恢复器增加 source/config/contract 保护和自动递增报告文件名，避免后续测试恢复过程覆盖 v4 source 或既有恢复证据。
