# Scientific Gates & Acceptance v3.1

## G0 — Authoritative State
- 18 Dataset identities明确；
- 现有 pilots/runs分类明确；
- source hash统一；
- campaign state可重建；
- Dataset Pack引用正确。

## G1 — Current Source Re-anchor
- current Contract/runtime/scorer mapping PASS；
- changed scientific components targeted regression PASS；
- formal dispatcher PASS；
- T361–T363 redesign重新验收。

## G2 — Dataset Acceptance 18/18
每 suite：
- Ground Truth；
- mechanism；
- difficulty；
- leakage；
- semantic coherence；
- dedup；
- solvability；
- runtime compatibility；
- validator evidence；
- provenance；
全部 PASS。

## G3 — Dataset Pack Freeze
18 authoritative datasets组成一个 versioned pack。

## G4 — Auxiliary Model Profiles
- generator/validator/arbitrator选择可追溯；
- synthetic human profile可追溯；
- independence policy满足。

## G5 — All-Suite Dry Run
18/18 representative run覆盖：
- Control/Risk；
- E/M/H；
- major mechanisms；
- multi-agent；
- tools/A2A；
- Replay；
- Scorer；
- Utility；
- invalid/provider paths。

## G6 — Provider & Scheduler Freeze
- model profiles validated；
- retry policy frozen；
- concurrency calibrated；
- scheduler profile frozen。

## G7 — Benchmark Release Freeze
冻结：
- source；
- datasets；
- contracts；
- runtimes；
- scorers；
- prompts；
- tools；
- replay；
- synthetic human；
- provider/scheduler；
- dependency lock。

## G8 — Existing Research Result Audit
已有 Run全部得到明确分类：
- valid？
- compatible with which Benchmark Release？
- canonical？
- rerun needed？

## G9 — Tested Model Profile Freeze
每个正式 Tested Model：
- exact ID；
- capability；
- base profile；
- tool compatibility；
- limits；
- no silent substitution。

## G10 — Formal Model Campaign
约1620 case / model；
每 case 1次有效 execution；
18 suite全部终态。

## G11 — Campaign Acceptance
- 18/18；
- Safety/Utility分离；
- provider failure正确排除；
- invalid明确；
- no unsafe rerun-to-safe；
- Replay audit；
- Manifest complete。

## G12 — Multi-Model Comparison Ready
至少完成用户指定的全部 Model Campaign。

## G13 — Final Scientific Release
- canonical manifests；
- per-suite outcomes；
- six-family profiles；
- model comparison；
- Dashboard；
- Report；
- Drilldown；
- Reproducibility Bundle；
- SIMULATION_ONLY labels；
- secret scan；
- limitations；
全部通过。

只有 G13 PASS 才能把长期 Goal 标记 complete。
