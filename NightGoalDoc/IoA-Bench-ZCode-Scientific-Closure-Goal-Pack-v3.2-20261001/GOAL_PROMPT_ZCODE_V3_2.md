# IoA-Bench — ZCode Scientific Closure & Canonical Binding Goal v3.2

将 `D:\Project\ioa_codex_spec` 中已经完成实现的 IoA-Bench 收口为一个**证据完整、版本边界清晰、Run↔Release 绑定可审计、最终验收逻辑正确、可直接用于科研交付的冻结 Benchmark**。

当前工作区：
`D:\Project\ioa_codex_spec`

本 Goal 配套规范目录：
`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-ZCode-Scientific-Closure-Goal-Pack-v3.2-20261001`

推进时按当前任务需要读取：

- `01_CURRENT_AUTHORITATIVE_STATE.md`
- `02_INDEPENDENT_REVERIFICATION_PROTOCOL.md`
- `03_RETROACTIVE_RELEASE_BINDING_PROTOCOL.md`
- `04_RELEASE_METADATA_HARDENING.md`
- `05_T311_DEVIATION_PROTOCOL.md`
- `06_ACCEPTANCE_MODEL_AND_G13_REPAIR.md`
- `07_FINAL_DELIVERY_AND_PROVENANCE.md`
- `08_SCIENTIFIC_GATES_V3_2.md`
- `09_WORK_QUEUE_OVERLAY_V3_2.yaml`
- `10_CHECKPOINT_TEMPLATE.md`

不要因为 Goal 被自动续跑、恢复或重复注入而从头开始；每轮都从当前磁盘证据、State、Work Queue、Checkpoint 与 Gate 继续。

## 最终目标

最终必须同时满足：

1. 18 项 canonical IoA 测评保持当前已经完成的实现；除非新证据证明存在真实科研语义缺陷，否则不得重新打开 construct implementation。
2. 18 套 authoritative Dataset 的版本、hash、验证状态重新核对，并保持 immutable。
3. 2026-09-30 历史只读审计的关键结论由当前 ZCode 会话从磁盘证据重新复核，不能仅继承历史结论。
4. 每个 deepseek-v4.1-flash Formal Run 都有明确的 Run↔Dataset↔Runtime↔Scorer↔Prompt↔Tool↔Model Profile↔Release 绑定证据。
5. 将追认结果正式固化为版本化 `RETROACTIVE_RELEASE_BINDING_AUDIT`。
6. Release 缺失的 runtime prompt content hashes、Tool Schema hashes、Model Profile provenance 等元数据补齐，但不得静默修改原冻结 Release。
7. T311 的 max_tokens / concurrency / contract-label 偏差得到正式、可复核的 documented deviation。
8. “Benchmark 本体通过”和“DeepSeek canonical Campaign 通过”拆开验收。
9. 当前 canonical Tested Model roster 固定为用户已确认的 `deepseek-v4.1-flash`，不得自行扩充。
10. 最终 Dashboard / Report / Replay / Delivery Bundle 只引用明确 canonical 的结果与验收状态。
11. 最终项目状态可以从磁盘证据重建，并通过一致性验证。

## 完成证据

任何 PASS 必须来自真实文件或可复核运算。优先使用 authoritative Dataset/Manifest/content hash、18 个 Formal Run Manifest/Results/Replay、Benchmark Release Manifest、Runtime/Scorer/Contract/Prompt/Tool Schema 实际内容及 hash、Model/Scheduler Profile、source tree/historical snapshot diff、独立 tests/recomputation、acceptance artifacts、final delivery manifest/secret scan/CRC/SHA-256。

以下内容不能单独作为完成证据：PROJECT_STATE、旧 FINAL_SCIENTIFIC_ACCEPTANCE.json、旧 RUN_CLASSIFICATION.json、计划、TODO、总结文本、运行时长、mtime 单点、目录存在或既有 PASS 标签。

## 科研约束

- 18 项 taxonomy 与科研含义不变；
- 不重新设计已经通过的 construct；
- 不因 source hash 不同自动判定重跑；
- 不因 Run 已存在自动判定 canonical；
- Frozen Dataset 不原地修改；
- 历史 Run / Release / Gate 不静默覆盖；
- Safety 与 Task Utility 分离；
- Oracle / SUT / Telemetry 隔离；
- T361–T363 永远 `SIMULATION_ONLY`；
- valid model outcome 不得 rerun-to-safe；
- Provider failure 与模型结果分离；
- secret 不得进入 Goal、日志、Replay、Manifest、handoff 包；
- 当前 ZCode 执行模型只是执行/审计代理，不属于 Benchmark Tested Model roster，除非用户另行明确指定。

## 每轮自动推进规则

每轮结束前：

1. 读取当前 State / Work Queue / Checkpoint 与必要证据；
2. 判断 S0–S11 中哪些 Gate 已由真实证据满足；
3. 找到依赖已满足但尚未闭合的当前 Gate；
4. 推进该 Gate；
5. 每次真实修改后同步 artifact、Gate、State、Queue、Checkpoint、Changelog；
6. 历史审计与磁盘证据冲突时，以磁盘证据为准；
7. 若发现科研语义缺陷，先做 impact analysis，再限定最小修复范围；
8. 不为了“看起来统一”而重跑已经证明等价的 suite；
9. 不为了保留旧结果而忽略已经证明会影响模型行为或评分的差异。

只要仍存在未闭合 Gate、UNKNOWN/UNPROVEN、acceptance 未拆分、provenance 未补齐、final delivery 未完成、State 与磁盘不一致，就不得判定 Goal 完成，ZCode 应继续下一轮。

## Provider / 重跑规则

本 Goal 默认不调用 AIHubMix，也不重新跑正式模型。

如果独立复核发现某个 suite 的 Formal Run 无法证明与目标 Release 科研等价，并且只有重跑才能解决：

1. 完成 evidence-based impact analysis；
2. 明确受影响 suite；
3. 明确为什么现有证据无法解决；
4. 明确预计调用范围和成本影响；
5. 将其记录为 blocker；
6. 等待用户明确批准后才能调用 Provider。

不得从 1 个 suite 的问题自动扩大成 18 项重跑。

## 只有以下情况才暂停并要求用户决定

- 修改 18 项 canonical 科研含义；
- 修改核心科研解释；
- 扩展 Tested Model roster；
- 需要付费或大规模 Provider 重跑；
- 无法通过现有证据判断某 suite 是否 canonical；
- 会形成新语义 Benchmark Release 的方法变更；
- API key / 账户权限 / 额度等必须由用户提供的外部条件。

普通 hash、manifest、acceptance、report、reconciliation、packaging 问题由 ZCode 自主处理。

## 最终完成条件

只有当 `08_SCIENTIFIC_GATES_V3_2.md` 的 S0–S11 全部真实通过，并且最终证据明确给出：

- `BENCHMARK_IMPLEMENTATION_ACCEPTED = PASS`
- `DATASET_PACK_ACCEPTED = PASS`
- `RETROACTIVE_RELEASE_BINDING = PASS` 或有明确、可接受的逐 suite documented deviation
- `DEEPSEEK_CANONICAL_CAMPAIGN = PASS` 或 `PASS_WITH_DOCUMENTED_DEVIATIONS`
- `FINAL_PROJECT_ACCEPTANCE = PASS`

同时最终 Dashboard / Report 与 canonical evidence 一致、最终交付包完成、secret scan clean、CRC PASS、SHA-256 已记录、历史科研资产保留、State/Queue/Checkpoint 与磁盘一致，且不存在 required-rerun blocker，才允许 Goal 完成并收尾。
