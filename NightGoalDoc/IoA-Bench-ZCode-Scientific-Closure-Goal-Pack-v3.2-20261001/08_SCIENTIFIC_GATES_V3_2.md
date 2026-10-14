# Scientific Gates v3.2

## S0 — Current State Reconciliation
- 18 authoritative datasets identified；
- 18 candidate canonical DeepSeek formal runs identified；
- base Release identified；
- no silent mutation of frozen assets。

## S1 — Independent Reverification
- `INDEPENDENT_REVERIFICATION_V3_2.json`
- decisive ZCode audit claims independently checked；
- no unresolved decisive UNKNOWN。

## S2 — Dataset Binding
- 18/18 Run Manifest == Dataset Manifest == Release dataset content hash；
- dataset acceptance remains PASS。

## S3 — Runtime/Scorer/Prompt/Tool Compatibility
Per suite:
- runtime semantic relation；
- scorer semantic relation；
- runtime prompt hash；
- tool schema hash；
- relevant source diff；
all resolved.

## S4 — T311 Deviation
- max_tokens effect checked；
- concurrency effect checked；
- contract content checked；
- verdict NON_MATERIAL / MATERIAL / UNKNOWN。

## S5 — Retroactive Binding Audit
18 suites each classified:
- STRICT_BINDING
- SEMANTIC_BINDING
- BINDING_WITH_DOCUMENTED_DEVIATION
- UNPROVEN
- INCOMPATIBLE

No UNPROVEN or INCOMPATIBLE allowed for canonical acceptance.

## S6 — Release Metadata Addendum
- base Release immutable；
- prompt hashes frozen；
- tool hashes frozen；
- normalized profile frozen；
- binding audit linked；
- no semantic change。

## S7 — Acceptance Split
Separate artifacts exist for:
- benchmark implementation；
- dataset pack；
- canonical binding；
- DeepSeek campaign；
- final project。

## S8 — Phase C Canonical Consistency
- aggregation references only accepted canonical runs；
- dashboard/report consistent；
- SIMULATION_ONLY correct；
- T311 deviation disclosed；
- no single overall safety score unless explicitly intended。

## S9 — State / Queue / Checkpoint Consistency
- derived state matches disk；
- queue completed correctly；
- changelog/checkpoint synced。

## S10 — Final Delivery
- reproducibility bundle complete；
- secret scan clean；
- CRC PASS；
- SHA-256 recorded；
- final inventory complete；
- no API key in package。

## S11 — Final Completion
Only if:
- S0–S10 PASS；
- no required rerun blocker；
- `FINAL_PROJECT_ACCEPTANCE_V3_2.json` = PASS；
then Goal may complete.
