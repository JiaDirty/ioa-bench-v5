# Release Metadata Hardening

## 原则

不要修改已经冻结的：
`release/BENCHMARK_RELEASE_v3-20260930.json`

原文件保持 immutable。

## 缺口

当前已知缺口包括：

- runtime role/system/task prompt content hashes；
- actual Tool Schema hashes；
- Model Profile 中部分 provider/default fields；
- Run↔Release retroactive binding reference；
- T311 documented deviation reference。

## 推荐处理

优先创建一个**元数据补充件 / Addendum**，而不是把它误称为新的科研语义 Release。

建议：

`release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_1.json`

并包含：

- base_release_id；
- base_release_sha256；
- addendum_scope = provenance_and_metadata_only；
- per-suite runtime prompt hashes；
- per-suite tool schema hashes；
- model profile normalized fields；
- scheduler/retry references；
- retroactive binding audit hash；
- T311 deviation artifact hash；
- statement: no benchmark semantics changed。

如果独立核验证明为了补这些字段必须改变实际 Runtime/Scorer/Prompt/Tool 内容，则不能用 Addendum；必须停止并判断是否形成新 Benchmark Release。

## Model Profile

生成/补充规范化 profile，不静默覆盖旧 profile。

至少记录：

- exact model ID；
- provider；
- endpoint family；
- temperature；
- top_p：若未显式设置，写 `PROVIDER_DEFAULT_UNSET`；
- max_tokens；
- reasoning parameter；
- tool calling behavior；
- response format behavior；
- timeout；
- retry；
- context window（UNKNOWN 就明确 UNKNOWN）；
- concurrency reference；
- source evidence。

不要把未知值猜成具体值。
