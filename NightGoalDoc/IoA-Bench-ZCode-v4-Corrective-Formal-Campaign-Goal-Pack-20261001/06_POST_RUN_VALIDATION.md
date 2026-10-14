# Post-run Validation

每 suite：
- 90/90 all-terminal
- no missing/duplicate case IDs
- exact v4 release binding
- exact dataset/contract/scorer/runtime/model profile
- every attempt retained
- only zero-behavior RETRYABLE resumed
- INVALID never resumed
- INFRA_INTERRUPTED never resumed
- FAILED never resumed
- resume idempotent
- Replay hashes/actions/state diffs valid
- T353 three branches complete
- Dataset hash: Run == Dataset Manifest == v4 Release
- T361–T363 SIMULATION_ONLY
- SH exact and isolated
- provider/invalid/interrupted denominators correct

目标 binding：
18/18 `STRICT_BINDING`

任何 suite 非 STRICT：不得进入 v4 canonical Phase C，不得用历史 Run 替代。
