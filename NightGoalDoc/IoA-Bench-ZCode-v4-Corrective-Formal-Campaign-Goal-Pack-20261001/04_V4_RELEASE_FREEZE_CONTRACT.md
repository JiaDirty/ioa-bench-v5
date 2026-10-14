# v4 Release Freeze Contract

建议：
`release/BENCHMARK_RELEASE_v4-corrective-20261001.json`

Freeze 前必须：
candidate validation PASS；full pytest PASS；closure PASS；baseline PASS；mock strict retry PASS；T353 three-branch Replay PASS；Dataset Pack hash rechecked；Frozen Versions 18/18；dependency lock known。

Release 必须冻结：
release_id, frozen_at, supersedes v3, source_tree_sha256, dependency_lock_sha256, dataset_pack_v4_sha256, 18 datasets, 18 contracts, prompt hashes, tool schema hashes, scorer versions, runtime/dispatch versions, model profile, scheduler, strict retry semantics, replay schema, SH profile, canonical constraints。

Freeze 后不得修改科研源码或语义。若 smoke 需要科研语义修改，则停止并创建新的 Release，不原地改 v4。
