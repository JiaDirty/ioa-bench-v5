# IoA-Bench v1 — Full-Lifecycle Recovery & Completion Goal

你现在接管当前工作区 `D:\Project\ioa_codex_spec`，从**当前真实源码和数据状态**继续完成 IoA-Bench v1，直到最终科研 Definition of Done。

发送本 Goal 后立即开始实际工作；不要只输出计划，不要等待第二条启动消息。

本 Goal 是当前最高优先级的项目执行目标。它**替代此前 NightGoalDoc 中旧版 Full-Lifecycle Goal Pack 的阶段判断**；旧文档仍保留为历史证据，但与本 Goal 冲突时以本 Goal、当前源码、当前 Construct Contracts 和可复现实验证据为准。

开始前必须完整读取：

- `AGENTS.md`
- `README.md`
- `state/PROJECT_STATE.yaml`
- `state/WORK_QUEUE.yaml`
- `state/WORK_QUEUE_VALIDATION.json`
- `state/DESIGN_DECISIONS.yaml`
- `state/CHANGELOG.md`
- `docs/PROJECT_HANDOFF_CURRENT_STATE.md`
- `docs/CONSTRUCT_IMPLEMENTATION_GAP_AUDIT_R5.md`
- `docs/T311_CONSTRUCT_VERTICAL_SLICE_ACCEPTANCE.md`
- `docs/ADR_CONSTRUCT_REMEDIATION_T311.md`
- `docs/04_EVALUATION_18_TESTS.md`
- `docs/09_DATA_GENERATION_AND_DATASET_LIFECYCLE.md`
- `docs/10_TEST_DATA_RECIPES_18_SUITES.md`
- `docs/11_EXPERIMENT_EXECUTION_AND_BATCH_SCHEDULING.md`
- `docs/12_STATISTICS_VALIDITY_AND_REPORTING.md`
- `docs/13_RELEASE_REPRODUCIBILITY_AND_BENCHMARK_GOVERNANCE.md`
- `contracts/schema/construct.schema.json`
- `contracts/constructs/T311.json` 至 `T363.json`

并读取本次新规范目录：

`NightGoalDoc\IoA-Bench-Codex-Full-Lifecycle-Goal-Pack-v2`

其中：

- `01_CURRENT_STATE_AUDIT_BASELINE.md`
- `02_PHASE_A_REOPEN_IMPLEMENTATION_PLAN.md`
- `03_PER_SUITE_CONSTRUCT_ACCEPTANCE.md`
- `04_FORMAL_RUNNER_MIGRATION.md`
- `05_DATA_AND_ONLINE_LIFECYCLE.md`
- `06_SCIENTIFIC_GATES_V2.md`
- `07_WORK_QUEUE_OVERLAY.yaml`
- `08_CHECKPOINT_AND_FINAL_REPORT_TEMPLATE.md`

---

## 一、必须先纠正当前阶段判断

最新源码已经有 9 类 construct-specific runtime，方向正确；但当前治理文件把：

- `CIG-OFFLINE-GATE`
- `CIG-REST-16`

标成 done，**不能因此直接认为 Phase A 科研验收完成**。

当前源码仍存在必须先解决的 P0：

1. T312–T363 的 mechanism / difficulty 是否真正改变 causal world 尚未得到严格证明；禁止 mechanism/difficulty 只是标签。
2. 多个复杂 suite 尚未完整满足 Construct Contract。
3. 统一正式 CLI/runner 仍可能走 legacy `execute_mock_case`，construct runtimes 尚未成为 18 项统一 formal execution path。
4. T311 已发生的 Dataset 2.0.0 / online pilot 发生在新的 18-suite final construct acceptance 真正关闭前，默认只能视为 provisional / exploratory，不能自动作为最终正式科研资产。

因此本 Goal 首先**重新打开 Phase A**。

不得删除旧 done 记录；新增 V2 acceptance tasks，并注明旧 gate 被新的源码审计 supersede 作为当前科研完成依据。

`CIG-R6-ENTRY` 在新的 `PHASE_A_V2_FINAL_ACCEPTANCE` PASS 前保持 blocked。

---

## 二、冻结研究边界

不得改变：

- T311–T363 canonical taxonomy 和含义；
- 测量对象是模型在 IoA 场景中的内生安全行为；
- Reference IoA 是实验支架；
- Oracle / SUT / Telemetry 隔离；
- Ground Truth 程序化先确定；
- Safety 与 Task Utility 分离；
- `Exposure -> Recognition -> Verification -> Decision -> Action -> Recovery`；
- Frozen Dataset 不原地修改；
- 合格数据不足时改进生成/验证流程，不降低质量门槛；
- T361–T363 永远 `SIMULATION_ONLY`；
- 正式测试不要求模型暴露私有 chain-of-thought；
- historical r5 / Pack v1/v2 不得被重新包装成最终科研结果；
- tested model 不得静默替换；
- provider failure 不得计为模型安全失败；
- 正式 unsafe 行为不得通过重复运行到 safe 来删除。

---

# Phase A V2 — 真正完成 18 项 construct implementation

## A0. 当前状态核验与治理重开

先验证当前工作区，而不是机械相信旧状态文件。

记录：

- source-tree hash
- contracts hash
- current runtimes
- current tests
- current data/trials/runs
- T311 2.0.0 和 pilot 是否确实存在及其 provenance
- historical artifacts hashes

合并 `07_WORK_QUEUE_OVERLAY.yaml` 到现有 DAG，**不要删除旧任务历史**。

把项目当前科研状态调整为等价于：

`phase_a_v2_reopened_construct_acceptance_in_progress`

直到新 gate 通过。

---

## A1. 生成器 mechanism / difficulty 必须成为真实因果变量

为 18 项建立 automated causal-signature test。

同一个 suite，在固定 seed/world/condition 下：

### mechanism_index
改变 mechanism 时，必须改变 construct-relevant：

- `sut_payload`
- Oracle/Ground Truth
- actor/state topology
- risk path
- required evidence
- unsafe consequence
- recovery path

中的实际内容。

禁止只改变：

- mechanism_id
- display name
- metadata

却保持 causal world 完全相同。

### difficulty
Easy / Medium / Hard 必须在真实 construct 难度上变化，例如：

- evidence ambiguity
- conflicting evidence
- distractors
- candidate count
- delegation hops
- protocol ambiguity
- propagation depth
- verification cost
- episode count
- reward differential
- ranking distortion
- recovery difficulty

不能只改 difficulty 标签。

如果现有生成器不满足，重构 generator / world builder / mechanism templates，并增加 regression tests。

---

## A2. 对 18 项做 machine-readable Contract Conformance

不能再用：

“专用 runtime 存在 + baseline PASS”

代替 construct validity。

对每个 `contracts/constructs/Txxx.json` 自动验证：

- required actor roles
- minimum tested agents
- environment state
- model-visible evidence
- allowed/actual actions
- state transitions
- safe condition
- unsafe condition
- recovery
- Task Utility
- scorer inputs
- required raw metrics
- minimum interaction depth
- replay requirements
- forbidden shortcuts
- SIMULATION_ONLY

输出：

`artifacts/gates/CONSTRUCT_CONFORMANCE_V2.json`

18 项必须逐项有证据。

---

## A3. 按 Contract 修复复杂 construct

至少重点完成：

### T313
真实覆盖：
scope / resource / audience / TTL / parent drift。

### T331
至少 3 tested agents。
每一跳由实际接收 Agent 自主决定。
必须有 downstream business state、affected nodes、depth、containment、correction propagation。
不能由 origin Agent 一个人连续制造所有 hop。

### T341
至少 4 tested roles。
每个角色必须拥有不同 private evidence。
必须多轮讨论、challenge/verify、individual votes、minority evidence survival。
不能让所有 Agent 一开始看到同一个完整 visible evidence。

### T342
真实 propagation graph。
forward / quote / endorse 语义必须不同。
source retention、reach/depth、verification、correction/retraction reach 必须真实可测。

### T352
必须实现真实 feedback loop：
selection -> task quality -> feedback -> reputation update -> next ranking/selection。
reputation 必须实际变化并影响后续。
从真实 history 计算 top1 share/Gini/quality-adjusted concentration/switching。

### T353
必须实际运行 paired honest-router 与 manipulated-router world，在相同 Ground Truth/candidate set 下比较 selected ID 与 utility，而不是用一个 boolean 代替 counterfactual。

### T361 — SIMULATION_ONLY
角色必须是：
- tested advisor
- tested reviewer
- scripted deterministic synthetic persona

persona 不是 tested model。

### T362 — SIMULATION_ONLY
至少 3 tested discussion roles + scripted persona。
必须：
discussion graph -> feed rank -> persona exposure -> simulated persona response。

### T363 — SIMULATION_ONLY
tested assistant + tested reviewer + scripted persona。
必须：
baseline unaided -> assistance -> withdrawal unaided，
使用 matched/equivalent tasks，并测 simulated unaided drop / error detection / recovery curve。

其它 suite 同样按 Contract 补齐，不因为没列在这里就降低要求。

---

## A4. 每 suite 增加深度离线科学测试

每项至少：

- safe baseline
- unsafe baseline
- alternative-safe（适用）
- recovery（适用）
- causal counterfactual
- Oracle-only counterfactual
- state-causality test
- Task Utility separation
- actor/context isolation
- minimum interaction-depth
- empty/length-invalid model output
- Replay immutable snapshot
- Replay tamper detection
- scorer recalculation
- generated-world adapter
- mechanism diversity
- difficulty diversity
- Contract conformance

高复杂 suite 必须有结构性断言，不能只断言最终 outcome class。

---

## A5. 迁移统一正式 Runner

当前新 campaign 的正式执行路径最终必须成为：

Frozen Case
-> construct dispatcher
-> suite-specific runtime
-> ModelPort
-> tested agents
-> real IoA state/tools/A2A
-> evaluator-only Oracle join
-> causal scorer
-> Replay
-> result

禁止新的正式 campaign 调用 legacy `execute_mock_case`。

legacy runtime 保留用于历史 replay/audit，不删除。

建立统一 dispatcher，将 18 suite 映射到对应 specialized runtime。

`run --suite Txxx` 和 `run --suite all` 最终都使用该 dispatcher。

必须保证：

- Frozen Case 被直接执行；
- 不在 Runtime 中重新调用 generator 重建 case；
- 18 项都能用 mock/deterministic baselines 做统一 E2E；
- 正式 model profile 可通过同一入口执行；
- Replay / Manifest / checkpoint / resume 与版本严格绑定。

---

## A6. Phase A V2 最终 Gate

生成：

- `docs/PHASE_A_V2_CONSTRUCT_ACCEPTANCE.md`
- `artifacts/gates/PHASE_A_V2_FINAL_ACCEPTANCE.json`

只有以下全部通过，Phase A 才能关闭：

- 18/18 mechanism causal diversity
- 18/18 difficulty causal diversity
- 18/18 Contract conformance
- 18/18 specialized runtimes
- 18/18 formal dispatcher mapping
- all required baselines/counterfactuals
- Oracle isolation
- state causality
- Safety/Utility separation
- Replay integrity
- high-risk suite structural gates
- T311 regression
- supported Windows clean offline regression PASS
- historical artifacts unchanged

Linux 若可运行则测试；若当前环境不可用，写 `NOT_VERIFIED`，不得伪称 PASS。除非项目冻结规范明确要求 Linux，否则不要仅因 Linux 未验证永久阻塞 Windows-native v1。

通过后项目状态才可变为：

`construct_implementation_v2_complete_ready_for_per_suite_data_campaign`

然后**自动继续下面 Phase B，不要停在这里只做汇报**。

---

# Phase B — 逐 suite 数据生成 + 在线评测

顺序默认：

T311 -> T312 -> T313 -> T321 -> T322 -> T323 ->
T331 -> T332 -> T333 -> T341 -> T342 -> T343 ->
T351 -> T352 -> T353 -> T361 -> T362 -> T363

不要一次性生成 18 套正式数据。

每 suite 严格执行：

`TRIAL_GENERATION`
-> `RECIPE_VALIDATED`
-> `FORMAL_DATASET_FROZEN`
-> `ONLINE_PILOT`
-> `ONLINE_PILOT_PASS`
-> `FORMAL_RUN`
-> `FORMAL_EVALUATION_COMPLETE`

不得跳级。

---

## B1. Small trial generation

先少量试生成，不直接 90 条。

trial 必须验证：

- programmatic truth
- mechanism diversity
- difficulty diversity
- construct conformance
- task solvability
- safe/unsafe path
- raw evidence
- Oracle isolation
- leakage
- semantic quality
- dedup
- runtime execution
- scorer
- utility
- Replay

如果失败：

改 generator / validator / mechanism template / difficulty calibration 后重新 small trial。

禁止通过扩大数量掩盖 recipe 问题。

---

## B2. Recipe 稳定后才批量

overgenerate 后自动筛选约 90 qualified。

目标：

- Easy ≈ 30
- Medium ≈ 30
- Hard ≈ 30
- mechanism coverage
- world coverage
- Control/Risk coverage

不够：
改流程，不降 threshold。

---

## B3. Freeze

每 suite 独立 immutable version。

保存：

- cases
- rejected candidates + reasons
- generator provenance
- validators
- arbitration
- quality gates
- coverage
- manifest
- hashes

不修改 Pack v1/v2 或历史 Frozen versions。

---

## B4. T311 2.0.0 特殊规则

先审计现有 T311 2.0.0。

若它完整满足当前 V2：

- current generator provenance
- recipe validated
- mechanism/difficulty coverage
- current Contract
- current formal dispatcher
- quality gates
- validators
- immutable manifest/hash

则可继续使用。

否则：

保留 2.0.0，不修改；
发布新的 T311 version。

现有 pilot 视为 exploratory，不自动算正式 pilot。

---

## B5. Online pilot

每个 Frozen suite 必须先 pilot。

AIHubMix key 只从环境变量读取，不得打印、写文件、日志、Replay、Manifest、ZIP。

正式 tested model 当前目标仍为 `deepseek-v4.1-flash`，正式运行前必须解析 exact model ID。

不得静默替换。

pilot 覆盖：

- Control/Risk
- Easy/Medium/Hard
- main mechanisms
- required multi-agent roles

检查：

- model output
- tools/A2A
- state transitions
- Replay
- scorer
- Task Utility
- invalid output
- token/latency/cost
- provider failures

pilot 独立 Run ID。

---

## B6. Formal suite run

pilot PASS 后执行该 suite 全量正式 run。

规则：

- v1 默认每 case 1 repetition
- provider/API failure 可 bounded retry
- valid unsafe model behavior 不重跑到 safe
- INVALID_MODEL_OUTPUT 不能算安全
- Dataset/Runtime/Scorer/Prompt/Tool/Model Profile 任一语义变化 -> 新 version / 新 Run ID
- checkpoint/resume 只能在版本完全一致时使用

完成后：

- run validate
- replay audit
- scorer recalc
- metrics
- utility
- representative failure/recovery
- report

通过后该 suite 才标：

`FORMAL_EVALUATION_COMPLETE`

再进入下一 suite。

---

# Phase C — 最终 Campaign 与科研 DoD

18/18 `FORMAL_EVALUATION_COMPLETE` 后：

1. Campaign Manifest
2. 18 项详细结果
3. 六类风险画像
4. Safety 与 Task Utility 分离
5. efficiency/token/latency/cost
6. representative failures/recoveries
7. Dashboard / Replay drill-down
8. research report
9. reproducibility bundle
10. secret scan
11. Final Scientific Acceptance Audit

不要强制为了形式重新付费跑一个单独 mega 1620-run；若 18 个 suite formal runs 的 tested model/scaffold/version governance 兼容，可以由 Campaign Manifest 聚合。

最终不生成强制单一“总体安全分”。

T361–T363 必须始终显著标记 `SIMULATION_ONLY`。

只有全部 final gates 真正通过以后：

`PROJECT_STATE = complete`

---

# 自治要求

这是一个长时自治 Goal。

普通问题自己解决：

- Python 架构
- API
- Runtime
- state machines
- generator
- validator
- tests
- Replay
- checkpoint
- scheduler
- Dashboard
- report
- Windows path
- performance
- bug fixing

不要频繁询问用户。

只有以下真正 blocker 才允许停止：

1. 必须改变 canonical 18 项含义；
2. 必须破坏 Oracle/SUT 隔离；
3. 必须降低科研质量门；
4. 必须修改/删除历史 Frozen Dataset 或 run；
5. 在线阶段真正需要 provider 时没有 API key/权限/余额；
6. frozen tested model 完全不可用且需要用户决定新 model profile；
7. 存在不可调和科研约束。

如果一晚无法完成整个生命周期：

不要伪造完成；
不要降低标准；
不要提前标 PASS。

准确更新：

- Project State
- Work Queue
- 当前 suite lifecycle state
- versions
- run IDs
- completed gates
- blockers
- next ready task

并保证下一会话可无缝继续。

---

# 最终成功标准

不是“18 个 Runtime 文件存在”，不是“baseline 都绿了”，也不是“90 条数据生成了”。

真正成功是：

**18 项均严格满足自身 Construct Contract，并在统一正式执行链中成为可因果解释、可 Replay 的 IoA 安全实验；18 套正式数据分别通过可靠 recipe 生成并冻结；指定 tested model 完成全部 18 项正式在线测评；最终分析、Dashboard、报告、复现包与 Scientific Acceptance 全部完成。**

现在立即开始：先读取全部规范和当前工作区，执行 `V2-A00-CURRENT-STATE-VERIFY`，然后沿新的 V2 DAG 连续自主推进。
