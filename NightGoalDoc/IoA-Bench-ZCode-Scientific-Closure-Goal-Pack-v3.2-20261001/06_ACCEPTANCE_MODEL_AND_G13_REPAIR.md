# Acceptance Model & G13 Repair

原 G13 不应同时用一个 PASS 混合：

1. Benchmark 本体是否完成；
2. Dataset 是否完成；
3. DeepSeek 历史 Formal Runs 是否 canonical；
4. Phase C 是否只消费 canonical evidence。

## 新验收结构

### A. BENCHMARK_IMPLEMENTATION_ACCEPTANCE
验证：
- 18/18 construct implementation；
- tests；
- runtime/scorer mapping；
- no unresolved construct defect。

### B. DATASET_PACK_ACCEPTANCE
验证：
- 18/18 authoritative dataset；
- independent validation；
- leakage；
- hash binding；
- provenance。

### C. CANONICAL_BINDING_ACCEPTANCE
验证：
- 18/18 Run binding level；
- T311 deviation；
- no INCOMPATIBLE/UNPROVEN suite。

### D. DEEPSEEK_CANONICAL_CAMPAIGN_ACCEPTANCE
验证：
- roster = deepseek-v4.1-flash；
- 18×90 terminal；
- 18/18 binding accepted；
- Replay；
- provider/invalid denominators；
- no rerun-to-safe。

### E. FINAL_PROJECT_ACCEPTANCE
只有 A–D 全部通过，并且最终 report/dashboard/bundle 与 canonical evidence 一致，才 PASS。

## 新 artifacts

建议：

- `artifacts/gates/BENCHMARK_IMPLEMENTATION_ACCEPTANCE.json`
- `artifacts/gates/DATASET_PACK_ACCEPTANCE.json`
- `artifacts/gates/CANONICAL_BINDING_ACCEPTANCE.json`
- `artifacts/gates/DEEPSEEK_CANONICAL_CAMPAIGN_ACCEPTANCE.json`
- `artifacts/gates/FINAL_PROJECT_ACCEPTANCE_V3_2.json`

原 `FINAL_SCIENTIFIC_ACCEPTANCE.json` 保留历史，不覆盖。

## 推荐 verdict

如果独立复核与上一轮审计一致：

- Benchmark implementation: PASS
- Dataset pack: PASS
- Canonical binding: PASS_WITH_DOCUMENTED_DEVIATION
- DeepSeek campaign: PASS_WITH_DOCUMENTED_DEVIATION
- Final project: PASS

最终 report 必须明确 T311 deviation。
