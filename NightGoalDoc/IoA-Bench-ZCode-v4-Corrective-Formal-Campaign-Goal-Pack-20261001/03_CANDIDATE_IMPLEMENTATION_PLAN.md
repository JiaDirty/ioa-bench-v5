# Candidate Implementation Plan

旧 candidate 不覆盖：
`artifacts/scientific_closure_v3_2/corrective-candidate/`

建议新目录：
`artifacts/scientific_closure_v4/corrective-candidate-v2/`

保留旧修复：
- INVALID_MODEL_OUTPUT terminal
- T353 paired Replay
- T353 rehash
- T353 counterfactual metric fix
- T353 runtime 2.2.0

最小修改范围：
- `src/ioabench/core/types.py`: `INFRA_INTERRUPTED`
- `src/ioabench/runtime/batch.py`: terminal set, attempts[], resume rule
- `src/ioabench/runtime/scientific_io.py`: AttemptJournal
- `src/ioabench/runtime/construct_dispatch.py`: infra classification + DISPATCH_VERSION 1.0.2
- `src/ioabench/cli.py`: terminal/run-validate/denominator
- `src/ioabench/runtime/run_gates.py`: INFRA_INTERRUPTED denominator
- `scripts/run_online_campaign.py`: terminal/formal_complete/resume semantics
- `scripts/phase_c_campaign.py`: provider denominator
- `src/ioabench/runtime/full_manifest.py`: release_id/release_sha256 binding
- `scripts/validate_corrective_candidate.py`: expand validation

不改：
Dataset Pack v4、taxonomy、17 suite scorer semantics、T353 contract、roster、SH config。
