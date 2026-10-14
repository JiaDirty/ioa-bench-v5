# Scientific Gates v2

## Gate A — Current State Integrity
- 历史 r5/v1/v2 artifacts hash 不被修改
- current source/tree baseline 记录
- old `done` 状态不当成 V2 科研证据

## Gate B — Generator Causal Diversity
18 suite：
- mechanism IDs 对应真实 causal variation
- Easy/Medium/Hard 对应真实 difficulty variation
- 自动 signature test PASS

## Gate C — Contract Conformance
18/18：
- actors
- state
- actions
- safe/unsafe/recovery
- scorer inputs
- raw metrics
- interaction depth
- replay
- SIMULATION_ONLY
全部检查 PASS。

## Gate D — Oracle / Evidence Isolation
固定 SUT-visible bytes，仅翻 hidden Oracle：
模型可见输入 hash 不变。

## Gate E — Baseline & Counterfactual
每 suite：
- safe
- unsafe
- alternative-safe where meaningful
- recovery where meaningful
- causal counterfactual
- state causality
- utility separation

## Gate F — Complex Construct Structure
至少：
- T331 >=3 tested agents + hop-by-hop + downstream state
- T341 >=4 tested roles + private evidence + votes
- T342 real propagation graph/source/correction
- T352 real reputation feedback update
- T361 scripted persona
- T362 scripted persona + feed/exposure
- T363 scripted persona + baseline/assistance/withdrawal

## Gate G — Formal Runner
18/18:
Frozen Case -> specialized construct runtime。
新 campaign 不使用 legacy `execute_mock_case`。

## Gate H — Replay
- immutable request snapshots
- no future message contamination
- A2A/tool/state before/after
- evaluator/scorer trace
- tamper detection

## Gate I — Phase A V2 Final
B–H 全部 PASS。
Windows supported environment full offline suite PASS。
Linux 如未运行只写 NOT_VERIFIED。
通过前禁止正式 Phase B。

---

# Per-Suite Data Gates

## J — Trial Recipe
small trial:
quality / leakage / mechanism / difficulty / runtime / scorer / replay PASS。

## K — Formal Dataset
- immutable version
- ~90 qualified
- coverage
- provenance
- validators
- rejection reasons
- manifest/hash

## L — Online Pilot
- exact model resolved
- provider key env only
- representative cases
- valid agents/tools/A2A/state
- replay/scorer/utility/cost PASS

## M — Formal Suite Run
- fixed dataset/runtime/scorer/prompt/model
- all work units terminal
- infra failures separated
- replay audit
- scorer recalc
- report
- suite scientific acceptance

---

# Final Campaign Gates

## N — 18/18 Formal Evaluation Complete
所有 suite 达到 `FORMAL_EVALUATION_COMPLETE`。

## O — Final Scientific Acceptance
- Campaign Manifest
- 18 profiles
- 6 category profiles
- no single mandatory total safety score
- SIMULATION_ONLY labels
- Dashboard
- reproducibility bundle
- secret scan
- final audit
- PROJECT_STATE complete
