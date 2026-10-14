# Acceptance & Delivery

新验收：
- BENCHMARK_IMPLEMENTATION_ACCEPTANCE_V4 = PASS
- DATASET_PACK_ACCEPTANCE_V4 = PASS
- CANONICAL_BINDING_ACCEPTANCE_V4 = PASS（18/18 STRICT）
- DEEPSEEK_CANONICAL_CAMPAIGN_ACCEPTANCE_V4 = PASS
- FINAL_PROJECT_ACCEPTANCE_V4 = PASS

新的 Phase C 只能消费 v4 Run IDs。

Report 必须披露 v4 release/hash、18 run ids、dataset pack、source tree、strict retry semantics、INVALID/INFRA_INTERRUPTED/provider denominators、single-execution、SIMULATION_ONLY、T353 corrected metric/replay、历史 baseline 关系。

新 bundle 包含 v4 Release、source/contracts/config snapshot、Dataset refs/manifests、profiles、18 Run Manifests、results/replay refs、strict binding audit、acceptance、Phase C、report/dashboard、validation、dependency lock、state/checkpoint/changelog、inventory、CRC、SHA-256、secret scan。

历史 bundle 不覆盖。
