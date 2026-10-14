# Per-Suite Data + Online Lifecycle

只有 `PHASE_A_V2_FINAL_ACCEPTANCE` PASS 后执行。

默认顺序：

T311 -> T312 -> T313 -> T321 -> T322 -> T323 ->
T331 -> T332 -> T333 -> T341 -> T342 -> T343 ->
T351 -> T352 -> T353 -> T361 -> T362 -> T363

## 1. 每 suite 先 Trial

不要直接 90 条。

先生成少量机制/难度/世界覆盖样本，用于验证 recipe。

Trial 检查：

- schema
- truth invariants
- construct conformance
- mechanism diversity
- difficulty diversity
- safe/unsafe path
- task solvability
- raw evidence / Oracle isolation
- leakage
- semantic quality
- dedup
- runtime execution
- scorer
- utility
- Replay

失败：
改 generator / validator / mechanism template / difficulty calibration，再试。

禁止通过扩大数量掩盖 recipe 问题。

## 2. Recipe validated 后才批量生成

overgenerate，自动 qualify 到约 90。

目标：
- Easy ≈ 30
- Medium ≈ 30
- Hard ≈ 30
- mechanism coverage
- world coverage
- Control/Risk coverage

合格不足：
改流程，不降质量门槛。

## 3. Freeze

每 suite 单独 immutable version。

保留：
- candidates
- rejected + reason
- generator provenance
- validator verdicts
- arbitration
- content hashes
- manifest

旧 Frozen Dataset 不原地修改。

## 4. T311 现有 2.0.0

先做 provenance audit。

若证明：
- 来自当前 construct-compatible generator
- recipe 已通过当前 V2 gates
- mechanism/difficulty/coverage 完整
- validators/provenance 完整
- Frozen Case 与 current formal runner 直接兼容

可保留并晋升为正式使用版本。

否则：
保留 2.0.0 为 provisional，生成新的版本。

## 5. Online pilot

每 suite Frozen 后先小规模 pilot。

覆盖：
- Control/Risk
- Easy/Medium/Hard
- main mechanisms
- multi-agent roles

检查：
- model output validity
- real tools/A2A
- state transitions
- Replay
- scorer
- utility
- cost/latency
- provider failure

pilot 独立 Run ID，不进入正式结果。

## 6. Formal online run

pilot PASS 后执行完整 suite。

原则：
- v1 每 case 1 repetition
- provider error 可 retry
- valid unsafe behavior 不重跑到 safe
- invalid model output 按冻结 policy
- no silent tested-model substitution
- semantic version change -> new Run ID
- checkpoint/resume

## 7. Suite complete

只有：
dataset frozen + pilot pass + full run + replay audit + scorer recalc + report
后才：

`FORMAL_EVALUATION_COMPLETE`

再进入下一 suite。

## 8. Final aggregation

18 suite complete 后：
- Campaign Manifest
- 18 detailed profiles
- six-category profile
- Safety/Utility separate
- representative failures/recoveries
- Dashboard
- final report
- reproducibility bundle
- Final Scientific Acceptance

不要求为了形式重新付费跑一个单独 1620-case mega-run；兼容的 18 个正式 suite runs 可以由 Campaign Manifest 聚合。
