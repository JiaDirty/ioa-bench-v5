# Phase A Reopen — Implementation & Acceptance Plan

## 目标

在不丢弃现有 Runtime 的前提下，把“18 项都有专用执行器”提升为：

**18 项都严格满足自身 Construct Contract、生成机制具有真实因果多样性、正式 Runner 能执行冻结 case、Replay/Scorer/Utility 全链闭合。**

完成后才允许数据/在线阶段。

---

## A0 — 建立新治理入口

不要删除旧 `CIG-OFFLINE-GATE` / `CIG-REST-16` 的历史 done 记录。

新增 V2 任务：

- `V2-A00-CURRENT-STATE-VERIFY`
- `V2-A01-GOVERNANCE-REOPEN`
- `V2-A02-GENERATOR-CAUSAL-DIVERSITY`
- `V2-A03-CONTRACT-CONFORMANCE-18`
- `V2-A04-HIGH-RISK-CONSTRUCT-REMEDIATION`
- `V2-A05-FORMAL-CONSTRUCT-RUNNER`
- `V2-A06-DEEP-OFFLINE-TESTS`
- `V2-A07-PHASE-A-FINAL-ACCEPTANCE`

`CIG-R6-ENTRY` 在 V2-A07 前保持 blocked。

---

## A1 — Generator causal diversity

对 T311–T363 自动计算每个 suite 的 causal signature。

signature 至少包含：

- programmatic `sut_payload`
- evaluator-only truth
- actors / roles
- state topology
- attack/risk path
- allowed actions
- required verification/evidence
- irreversible consequence
- recovery path

新增测试：

### Mechanism diversity
同 seed / world / difficulty / condition，仅改变 mechanism index：

- 每个 declared mechanism 必须产生 construct-relevant state/causal difference。
- 禁止仅 `mechanism_id` 不同。

### Difficulty diversity
同 seed / world / mechanism / condition，仅改变 easy/medium/hard：

至少应在以下一项或多项真实变化：

- evidence ambiguity/conflict
- distractors
- number of candidates
- interaction depth
- propagation depth
- delegation hops
- protocol ambiguity
- verification cost
- longitudinal episodes
- reward differential
- ranking distortion
- recovery difficulty

难度必须由程序化特征支持，不仅是标签。

---

## A2 — 18-suite Contract Conformance

实现 machine-readable audit：

对每个 `contracts/constructs/Txxx.json` 检查：

- required actor roles
- minimum tested agents
- environment state
- model-visible evidence
- actual model actions
- state transitions
- safe conditions
- unsafe conditions
- recovery
- scorer inputs
- raw metrics
- minimum interaction depth
- replay requirements
- forbidden shortcuts
- SIMULATION_ONLY

输出：

`artifacts/gates/CONSTRUCT_CONFORMANCE_V2.json`

不得只依据 baseline outcome 判 PASS。

---

## A3 — 高复杂 suite 优先整改

优先顺序：

1. T361/T362/T363
2. T352
3. T341
4. T331/T342
5. T353
6. T313
7. 其它 suite contract coverage

原因：这些 suite 最容易“有代码但构念不成立”。

---

## A4 — Per-suite deep offline tests

每个 suite 至少：

- safe baseline
- naive unsafe baseline
- alternative-safe（有多条安全路径时）
- recovery（适用时）
- construct causal counterfactual
- Oracle-only counterfactual
- state-causality failure test
- utility-separation test
- Replay tamper test
- actor/context isolation
- required interaction-depth test
- generated-world adapter test
- mechanism diversity test
- difficulty diversity test
- scorer recalculation
- invalid/empty model output handling

复杂 suite 额外测试见 `03_PER_SUITE_CONSTRUCT_ACCEPTANCE.md`。

---

## A5 — Formal construct runner migration

统一正式执行入口必须调用 suite-specific Runtime。

目标：

`frozen case -> construct dispatcher -> ModelPort -> real tools/A2A/state -> evaluator -> scorer -> Replay`

不允许：

`frozen case -> execute_mock_case`

旧 legacy runner 保留用于历史重放，但明确标为 legacy，不得用于新的正式 campaign。

详细见 `04_FORMAL_RUNNER_MIGRATION.md`。

---

## A6 — Phase A V2 Final Acceptance

必须生成：

- `docs/PHASE_A_V2_CONSTRUCT_ACCEPTANCE.md`
- `artifacts/gates/PHASE_A_V2_FINAL_ACCEPTANCE.json`

Gate 至少要求：

- 18/18 contracts conformance PASS
- 18/18 generated mechanisms causal
- 18/18 difficulty signals causal
- 18/18 specialized runtimes
- 18/18 formal dispatcher mapping
- all required offline baselines/counterfactuals
- Oracle isolation
- Replay integrity
- Safety/Utility separation
- high-risk suites structural assertions
- no provider calls required for this gate
- historical frozen artifacts unchanged

Windows supported environment必须通过完整离线测试。

Linux 若可用则测试；若不可用写 `NOT_VERIFIED`，不得谎称 PASS。Linux 本身不是 v1 Windows-native 项目的自动阻塞条件，除非现有冻结规范另有明确要求。

通过后：

`PROJECT_STATE = construct_implementation_v2_complete_ready_for_per_suite_data_campaign`

随后 Goal 自动继续 Phase B。
