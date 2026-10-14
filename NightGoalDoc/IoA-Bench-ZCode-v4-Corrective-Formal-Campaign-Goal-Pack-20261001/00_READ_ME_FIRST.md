# IoA-Bench v4 Corrective Release + Strict Formal Campaign Goal Pack

本包用于下一阶段：`V4_CORRECTIVE_RELEASE_AND_STRICT_FORMAL_CAMPAIGN`。

科研决策已固定：
- v4 strict canonical Campaign = 18 suites × 90 cases = 1620 cases；
- 历史 Formal Runs 全部保留为 historical evidence，但不作为 v4 canonical Campaign 成绩；
- Dataset Pack v4 原样复用，不重新生成数据；
- 18 项 taxonomy / construct meaning 不重做；
- Tested Model roster 仍只有 `deepseek-v4.1-flash`；
- T361–T363 永久 `SIMULATION_ONLY`；
- T362/T363 Synthetic Human 继续 frozen `glm-5.3-flash + sh-personas-1.0.0`。

当前旧 corrective candidate：
`artifacts/scientific_closure_v3_2/corrective-candidate/`

旧 candidate hash：
`7f48188a83a1d5a2e5d0886a9778813076f01c236815795b14c4e110c0becd77`

这个 hash 只是 strict-retry 修订前的 candidate hash。Phase A 完成后必须重新计算新的 source tree hash。

在用户明确批准之前，禁止 AIHubMix live smoke 和正式 Campaign。ZCode 可以自动完成离线 Phase A–C，到 Provider 阶段必须暂停。
