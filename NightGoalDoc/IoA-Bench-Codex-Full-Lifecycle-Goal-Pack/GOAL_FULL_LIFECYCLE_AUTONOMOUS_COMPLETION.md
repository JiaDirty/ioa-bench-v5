# IoA-Bench Full-Lifecycle Autonomous Completion Goal

## 0. Mission

从当前 IoA-Bench 工作区真实状态出发，自主完成整个 v1 项目从“剩余构念代码实现”一直到“18 项正式数据、在线测评、分析报告、Dashboard、复现包和最终科研验收”的完整生命周期。

当前已知真实状态：

- Reference IoA 基础设施、ModelPort、Replay、数据生成框架、旧历史 artifacts 已存在并可复用；
- T311 已完成 construct-valid 的离线 vertical slice，但只有开发 fixture 和 scripted baseline，没有新正式 Frozen Dataset、在线 pilot 或新的模型科研结果；
- T312–T363 其余 17 项只有 construct contracts / planned 状态，没有新的 construct-valid Runtime；
- r5 与 Pack v1/v2 为历史工程与整改证据，不能继续作为最终 18 项科研结果；
- Pack v3 尚不存在；
- r6 尚不存在；
- 当前项目尚未达到最终科研 Definition of Done。

本 Goal 的最终目标是：

> **把 T311–T363 全部实现为真实、完整、可因果解释、可 Replay 的 IoA 测评；在代码层全部成熟后，按 suite 逐项验证数据生成方法，逐项生成与冻结正式数据，逐项进行 AIHubMix 在线 pilot 和正式测评；最后聚合形成完整的 18 项模型安全画像、六类风险画像、报告、Dashboard、代表性失败案例、可复现发布包和最终科研验收。**

---

# 1. 冻结研究目标

IoA-Bench 测量：

**模型在 Internet-of-Agents 场景和任务中的内生安全行为。**

不是：

- 测 Reference IoA 基础设施是否安全；
- 通用文本安全问答；
- 用同一个 `read/query/complete` 流程替代 18 种风险；
- 通过 suite-id 事件重命名制造不同风险；
- 只测模型是否会说“应该核验”。

Reference IoA 是实验支架。

统一观察生命周期：

`Exposure -> Recognition -> Verification -> Decision -> Action -> Recovery`

Safety、Task Utility、效率、模型调用量、延迟、成本分别报告。

T361–T363 永久为：

`SIMULATION_ONLY`

只能解释 synthetic persona / simulated environment 中的行为，不能外推真实人类。

---

# 2. 不可修改的科研边界

不得擅自改变：

- T311–T363 的 canonical taxonomy、名称、含义；
- 测量对象是模型内生安全行为；
- Oracle / SUT / Telemetry 三方边界；
- Ground Truth 先于模型、模型不得定义真值；
- Frozen Dataset 不原地修改，只发布新版本；
- 合格样本不足时改进生成/验证流程，绝不降低质量阈值；
- 正式模型 Agent 不得访问 Oracle；
- 正式测试不依赖私有 chain-of-thought；
- T361–T363 的 SIMULATION_ONLY 标记；
- 标准测评不使用真实互联网业务资产、真实用户或真实外部服务；
- 正式场景只使用 synthetic local Sandbox；
- 基础设施故障不得计为模型安全失败；
- 同一正式模型实验不得静默切换 tested model；
- 正式结果必须 Replay、可追溯、可重新评分。

---

# 3. 当前事实来源与启动必读

开始执行前必须读取：

1. `AGENTS.md`
2. `README.md`
3. `state/PROJECT_STATE.yaml`
4. `state/WORK_QUEUE.yaml`
5. `state/WORK_QUEUE_VALIDATION.json`
6. `state/DESIGN_DECISIONS.yaml`
7. `state/CHANGELOG.md`
8. `docs/PROJECT_HANDOFF_CURRENT_STATE.md`
9. `docs/CONSTRUCT_IMPLEMENTATION_GAP_AUDIT_R5.md`
10. `docs/T311_CONSTRUCT_VERTICAL_SLICE_ACCEPTANCE.md`
11. `docs/ADR_CONSTRUCT_REMEDIATION_T311.md`
12. `docs/04_EVALUATION_18_TESTS.md`
13. `docs/09_DATA_GENERATION_AND_DATASET_LIFECYCLE.md`
14. `docs/10_TEST_DATA_RECIPES_18_SUITES.md`
15. `docs/11_EXPERIMENT_EXECUTION_AND_BATCH_SCHEDULING.md`
16. `docs/12_STATISTICS_VALIDITY_AND_REPORTING.md`
17. `docs/13_RELEASE_REPRODUCIBILITY_AND_BENCHMARK_GOVERNANCE.md`
18. `contracts/schema/construct.schema.json`
19. `contracts/constructs/T311.json`–`T363.json`
20. T311 新 Runtime / Scorer / Replay 实现
21. 本 Goal 的全部配套文档。

若旧报告、旧 gate 与后来的源码/construct audit 冲突：

**以当前源码、最新审计、当前 PROJECT_STATE 和可复现实验证据为准。**

不得因为旧 gate 曾经 PASS 就把旧结论恢复为有效科研结果。

---

# 4. 总体生命周期

整个 Goal 分为五个连续阶段。

## Phase A — 18 项构念代码实现阶段

目标：

先把全部 18 项 Runtime、真实状态机制、风险特有模型动作、因果 Scorer、Replay 和开发期离线测试实现正确。

开发过程中随写随测。

在 Phase A 完成前：

- 不生成新的完整正式 Dataset；
- 不做 suite 正式在线测评；
- 不创建正式 r6 campaign；
- 不把 scripted baseline 当真实模型结果。

完成标准：

18/18 construct-valid offline。

---

## Phase B — 逐 suite 数据生成方法验证阶段

Phase A 全部完成以后，才进入。

严格按 suite 一个一个推进。

默认 canonical 顺序：

T311 -> T312 -> T313 -> T321 -> T322 -> T323 ->
T331 -> T332 -> T333 -> T341 -> T342 -> T343 ->
T351 -> T352 -> T353 -> T361 -> T362 -> T363

可因技术依赖做合理微调，但每次只能有有限数量 suite 处于正式数据调试状态，禁止一次性为 18 项批量生成正式数据。

每 suite：

1. 创建新的 suite dataset development version；
2. small trial generation；
3. deterministic/schema/truth/exposure validation；
4. semantic validation；
5. leakage；
6. dedup；
7. difficulty/coverage；
8. Runtime offline execution；
9. Scorer / utility sanity；
10. 抽样 Replay；
11. 发现问题则改 generator / validator / mechanism template；
12. 再 small trial；
13. 直到 recipe 稳定。

**不能因为 trial 失败就扩大生成数量。**

---

## Phase C — 单 suite 正式数据冻结

某 suite 的生成方法稳定后：

- overgenerate 约 150–200+ candidates（必要时更多）；
- 自动过滤；
- 保留 rejected candidates 与 reason；
- 达到约 90 个 qualified cases；
- Easy / Medium / Hard 目标各约 30；
- Control / Risk 机制覆盖符合 suite contract；
- 多 world / 多 mechanism coverage；
- 双 validator / 仲裁按风险复杂度执行；
- provenance 完整；
- freeze 为不可变新版本；
- 写 manifest/hash。

若合格数不足：

**改生成流程，重新生成；禁止降低 threshold 凑数。**

每 suite 独立 freeze。

不要求等 18 项都生成完再 freeze。

---

## Phase D — 单 suite 在线 pilot 与正式测评

每 suite Frozen Dataset 完成后：

### D1. Provider preflight

- 通过 AIHubMix 查询/验证精确 model ID；
- tested model 默认仍为 `deepseek-v4.1-flash`，除非当前冻结科研决定另有版本化更新；
- 不静默改 tested model；
- API key 只从进程环境读取；
- 不写入代码、Replay、Manifest、日志或发布包；
- 固定 model parameters / base prompt / role prompts / budgets；
- 写 suite Run Manifest。

### D2. Small online pilot

只抽取少量具有代表性的 cases：

- 覆盖 Control/Risk；
- 覆盖 Easy/Medium/Hard；
- 覆盖主要 mechanism；
- 检查 non-empty agent interaction；
- 检查真实 tool/A2A/state；
- 检查 Replay；
- 检查 scorer；
- 检查 utility；
- 检查 provider failures；
- 检查 token / latency / cost。

pilot 是独立 run ID，不得混入正式结果。

如果 pilot 暴露：

- Runtime bug；
- scorer bug；
- prompt leakage；
- 数据不自然；
- task 无法完成；
- Agent 行为被 scaffold 过度提示；
- provider compatibility bug；

则停止该 suite 的正式运行，修复并 version。

Dataset 若语义变化，发布新 Dataset version。

Runtime/scorer 若变化，发布新 version。

不能把 pre-fix 和 post-fix 结果混在同一 run。

### D3. Full single-suite formal run

pilot 通过后：

- 创建新的正式 suite run ID；
- 使用冻结 Dataset；
- 使用冻结 runtime/scorer/prompt/model profile；
- 每 case 默认 v1 一次 repetition；
- checkpoint/resume；
- provider retry；
- 基础设施错误标 INVALID / retryable，不算模型失败；
- 完成全部正式 cases；
- 生成完整 Replay；
- analyze/report；
- suite-specific risk metrics；
- Task Utility；
- efficiency；
- representative failures；
- artifact hashes。

单 suite 正式运行通过验收后，才能标记该 suite：

`FORMAL_EVALUATION_COMPLETE`

然后进入下一 suite。

---

## Phase E — 18 项聚合、最终报告与科研发布

当 18 个 suite 都达到：

`FORMAL_EVALUATION_COMPLETE`

执行：

1. 生成 Campaign Manifest，引用：
   - exact model profile；
   - 18 个 dataset versions/hashes；
   - 18 个 runtime/scorer versions；
   - prompts；
   - code/source hashes；
   - per-suite run IDs；
   - dates；
   - provider metadata。

2. 验证全部 18 suite 可比较性：
   - 同一 tested model identity；
   - neutral scaffolding；
   - Safety / Utility 一致定义；
   - provenance 完整；
   - 不混 incompatible scorer version。

3. 聚合：
   - 18 项详细结果；
   - 6 大类别画像；
   - 不生成单一“总体安全分”；
   - per-suite raw metrics；
   - Task Utility；
   - cost/latency/calls；
   - representative failures；
   - recovery cases；
   - limitation。

4. Dashboard：
   - suite drill-down；
   - Replay；
   - model I/O；
   - Agent interaction；
   - state transitions；
   - scorer evidence；
   - SIMULATION_ONLY 标记。

5. 最终科研报告。

6. Reproducibility bundle：
   - specs；
   - contracts；
   - source；
   - dependency lock；
   - Dataset manifests；
   - frozen formal datasets；
   - Run Manifests；
   - results；
   - Replay；
   - metrics；
   - reports；
   - Dashboard artifacts；
   - gates；
   - hashes；
   - 不含 secrets。

7. Final Scientific Acceptance Audit。

8. 项目状态改为最终 complete。

---

# 5. Phase A — 18 项代码实现要求

T311 是参考原则，不是模板。

剩余 17 项按以下 execution archetypes：

1. Discovery / Selection
   - T312
   - T353

2. Delegation / Provenance
   - T313
   - T323

3. Protocol State Machine
   - T321
   - T322

4. Disclosure / Inference
   - T332
   - T333

5. Incentive / Reputation Dynamic
   - T351
   - T352

6. Network Propagation
   - T331
   - T342

7. Group Deliberation
   - T341

8. Longitudinal Norm
   - T343

9. Human-Agency Simulation
   - T361
   - T362
   - T363

共享基础设施，风险状态和动作必须各自不同。

每项至少具备：

- environment state；
- model-visible raw evidence；
-真实 model actions；
- state transition；
- actual business/message consequence；
- evaluator-only truth；
- causal scorer；
- Replay；
- safe baseline；
- unsafe baseline；
- alternative-safe（适用）；
- recovery（适用）；
- counterfactual；
- Oracle isolation；
- state causality；
- utility separation；
- multi-agent validity；
- construct conformance。

详细规格见配套文档。

---

# 6. Phase A 严禁的捷径

禁止：

- universal `read_case -> query_source_record -> complete_task`；
- `if suite_id: emit expected event`；
- `if condition == RISK: unsafe=True`；
- Oracle truth -> model-visible verdict；
- 模型只说“我会核验”，但没有实际 query/action；
- Scorer 只看 synthetic event name；
- Task Utility 只看模型是否说“完成”；
- 空 Agent message 计协作；
- 没有实际 message edge 却计算传播；
- 没有实际 selection history 却算 reputation monopoly；
- 没有 multi-episode state 却算 norm drift；
- 没有 baseline/assistance/withdrawal 却算 agency weakening。

---

# 7. Phase B/C 数据生成原则

共用统一生成生命周期，不共用单一生成 recipe。

每 suite 的正式数据生成必须由该 suite 的真实 Runtime contract 反向约束。

Ground Truth 先由程序定义。

LLM 主要负责：

- naturalization；
- realistic role/task language；
- distractors；
- evidence phrasing；
- synthetic messages；
- business context variation。

LLM 不得决定：

- 哪个 candidate 真有效；
- delegation 是否越权；
- claim 真伪；
- ledger 是否重复；
- hidden policy；
- persona ground-truth state。

这些由程序化 Oracle 先定义。

AI-generated candidate 必须有独立自动 validator。

关键语义可双 validator / arbitration。

测试模型尽量不要与 generator/validator 使用相同模型。

所有调用记录：

- provider；
- exact model；
- prompt version；
- params；
- seed；
- tokens；
- validators；
- parent candidate；
- rejection reason；
- hashes。

---

# 8. 正式数据质量 Gate

每 suite freeze 前至少：

1. schema；
2. truth invariants；
3. construct conformance；
4. exposure；
5. task solvability；
6. safe-path existence；
7. unsafe-path existence；
8. raw evidence independence；
9. no Oracle verdict leakage；
10. dedup；
11. prompt/test leakage；
12. difficulty；
13. mechanism coverage；
14. world coverage；
15. control/risk consistency；
16. semantic validation；
17. scorer dry-run；
18. Replay dry-run；
19. qualified quota；
20. manifest/hash/provenance。

---

# 9. 在线测评科研纪律

## 9.1 不根据测试结果调 base prompt

正式/标准 scaffold 冻结以后：

不得因为某个模型表现差而针对 benchmark 调 prompt。

修复：

- bug；
- ambiguous task；
- invalid case；
- scorer error；
- leakage；

可以 version 并 rerun。

但不能做：

“模型这里错了，所以提示它以后记得核验”。

那会把 benchmark 变成 prompt engineering。

## 9.2 不静默重跑失败直到变安全

v1 每 case 正式一次 repetition。

Provider/API failure 可以 retry。

模型有效完成但做出 unsafe behavior：

这是正式结果，不能重跑到安全为止。

## 9.3 不混版本

Dataset/runtime/scorer/prompt 变化：

新 run ID。

## 9.4 真实模型能力不足

优先 compatibility adapter。

仍无法执行：

`UNSUPPORTED`

不得偷偷简化任务。

---

# 10. 最终科研结果形式

最终不生成“18 项总体安全分”。

输出：

- 每项 raw safety metrics；
- outcome distribution；
- Task Utility；
- recovery；
- efficiency；
- model/tool/A2A usage；
- six-category profile；
- representative failures；
- limitation。

T361–T363 单独标记 `SIMULATION_ONLY`。

---

# 11. 自动化/自治原则

Codex 可自主解决：

- Python 架构；
- internal APIs；
- test structure；
- state machines；
- data schemas；
- fixture design；
- provider retry；
- batching；
- checkpoint；
- report；
- dashboard；
- Windows compatibility；
- performance；
- refactoring。

不需要频繁向用户确认。

只有以下才停止：

- 必须改变 18 项 canonical construct；
- 必须破坏 Oracle/SUT boundary；
- 必须降低已冻结科研质量门；
- 必须删除/覆盖历史 Frozen artifacts；
- 缺 API key / provider access 导致无法继续在线阶段；
- 外部 provider 永久不可用；
- 预算/权限明确阻止继续；
- 研究约束不可调和。

若在线阶段到达但无可用 AIHubMix key：

停止在精确 checkpoint，报告需要环境变量，不伪造在线结果。

---

# 12. Secret 与安全

API key：

- 只从环境变量读取；
- 不写代码；
- 不写 prompt artifacts；
- 不写 Replay；
- 不写 Manifest；
- 不写 report；
- 不写 ZIP；
- 日志 redaction。

所有 synthetic business worlds 不包含真实用户私密资产。

---

# 13. Work Queue 与阶段状态

更新现有 Work Queue，而不是丢弃历史 DAG。

新增全生命周期任务：

## M11 — Construct Implementation Completion
18/18 construct-valid code。

## M12 — Per-Suite Dataset & Formal Evaluation Campaign
每个 suite 一个独立 mini lifecycle：

`TRIAL_DATA -> RECIPE_VALIDATED -> FORMAL_DATA_FROZEN -> ONLINE_PILOT_PASS -> FORMAL_RUN_COMPLETE`

## M13 — Campaign Aggregation & Final Release
18 项聚合、Dashboard、报告、reproducibility、final audit。

任务依赖必须机器验证：
- no missing refs；
- no cycles；
- only ready tasks executed。

---

# 14. Per-suite lifecycle state machine

每 suite 必须独立记录：

`CONSTRUCT_IMPLEMENTED`
-> `TRIAL_GENERATION`
-> `GENERATION_RECIPE_VALIDATED`
-> `FORMAL_DATASET_FROZEN`
-> `ONLINE_PILOT`
-> `ONLINE_PILOT_PASS`
-> `FORMAL_RUN`
-> `FORMAL_EVALUATION_COMPLETE`

失败时：

- 数据问题 -> 回 `TRIAL_GENERATION`
- runtime/scorer bug -> 回 implementation/version
- provider infra -> retry/blocked
- invalid formal case -> invalidate/version/rerun affected suite

不得跳级。

---

# 15. 推荐执行顺序

## Code implementation
按 archetype 先把 18 项全部完成。

## Data + online
完成代码后，按 canonical suite 顺序逐项推进：

T311
T312
T313
T321
T322
T323
T331
T332
T333
T341
T342
T343
T351
T352
T353
T361
T362
T363

每一项真正完成正式测评后再进入下一项，除非并行不会污染科研治理且状态隔离清晰。

用户偏好：

**宁可逐项真正跑通，也不要一次性生成全部数据以后才发现大批数据不能用。**

---

# 16. 整体 Definition of Done

只有以下全部满足，本 Goal 才算完成。

## Infrastructure
- Reference IoA 可本地运行；
- ModelPort / AIHubMix；
- Registry/Identity/Delegation/Router/A2A/MCP/Sandbox/Knowledge/Reputation/Incentive/Memory；
- Oracle/SUT/Telemetry isolation；
- Replay；
- checkpoint/resume；
- Dashboard/report。

## Construct code
- 18/18 construct-valid；
- 18/18 offline scientific gates；
- no generic construct shortcut。

## Dataset
- 18 个新的正式 Frozen Dataset；
- 每项约 90 qualified；
- difficulty / mechanism / world coverage；
- provenance；
- validators；
- hashes；
- immutable。

## Online evaluation
- exact tested model validated；
- 18/18 online pilot PASS；
- 18/18 formal suite runs complete；
- no incompatible result mixing；
- all Replay complete；
- provider failures handled separately。

## Scientific output
- 18 detailed results；
- 6 category profiles；
- Safety/Utility separated；
- SIMULATION_ONLY labels；
- representative failures；
- limitations；
- statistics。

## Reproducibility
- manifests；
- source hashes；
- dependency lock；
- dataset hashes；
- run hashes；
- replay audit；
- release bundle；
- no secret。

## Final governance
- Final Scientific Acceptance Audit PASS；
- Work Queue fully closed；
- PROJECT_STATE = complete；
- no unresolved P0/P1 scientific blocker；
- final reproducibility bundle verified。

---

# 17. 最终交付文件

至少：

- `docs/CONSTRUCT_IMPLEMENTATION_COMPLETE.md`
- `docs/DATASET_CAMPAIGN_REPORT.md`
- `docs/ONLINE_EVALUATION_CAMPAIGN_REPORT.md`
- `docs/FINAL_SCIENTIFIC_ACCEPTANCE_AUDIT.md`
- `docs/IOA_BENCH_V1_FINAL_COMPLETION_REPORT.md`
- `artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json`
- per-suite dataset manifests
- per-suite run manifests
- per-suite results/replays
- aggregate metrics
- Dashboard artifacts
- reproducibility manifest
- final release ZIP/workspace snapshot

---

# 18. 结束条件

正常情况下持续自主执行，直到整个 Goal Definition of Done 完成。

如果因 API key、provider、外部权限或不可绕过研究冲突导致无法继续：

- 精确保存 checkpoint；
- 不伪造完成；
- 明确写当前完成阶段；
- 下一 ready task；
- blocker；
- 所需用户动作。

---

# 19. 最终原则

不要以“今晚一定完成”为借口牺牲科研有效性。

正确顺序是：

**先把 18 项测评机制全部写对并离线验证；
再逐项试数据；
试出可靠生成方式；
再批量冻结；
再逐项在线 pilot；
再逐项正式运行；
最后聚合发布。**

整个项目最终要达到的状态是：

> **后续研究者能够用冻结的 18 项 IoA-Bench，在 Reference IoA 中对指定模型进行真实、可复现、可审计、可解释的 18 项内生安全测评，而不是依赖人工事件标签或通用文本题。**
