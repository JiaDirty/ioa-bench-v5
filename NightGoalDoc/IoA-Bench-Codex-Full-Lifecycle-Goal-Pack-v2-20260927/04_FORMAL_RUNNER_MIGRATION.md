# Formal Construct Runner Migration

## 当前问题

最新源码中 `src/ioabench/cli.py::_run_all()` 仍引用 legacy `execute_mock_case`，且 non-mock formal execution 被主动阻塞。

因此新的 construct runtimes 目前主要是离线 acceptance paths，不是统一 formal benchmark execution path。

## 目标

建立唯一的新版正式执行链：

`Frozen Case`
-> `Suite Runtime Dispatcher`
-> `Construct-specific Runtime`
-> `ModelPort`
-> `Role-specific Tested Agents`
-> `Registry/A2A/Delegation/Router/Sandbox/etc`
-> `State transitions`
-> `Evaluator-only Oracle join`
-> `Causal Scorer`
-> `Immutable Replay`
-> `Per-case Result`

## 建议实现

新增或等价实现：

`src/ioabench/runtime/construct_dispatch.py`

注册：

- T311 -> execute_t311
- T312/T353 -> discovery_selection executor
- T313/T323 -> delegation_provenance executor
- T321/T322 -> protocol_state_machine executor
- T331/T342 -> network_propagation executor
- T332/T333 -> disclosure_inference executor
- T341/T343 -> deliberation_norm executor
- T351/T352 -> incentive_reputation executor
- T361/T362/T363 -> human_agency_simulation executor

每个 adapter 必须把 Frozen Case **直接**转换成该 Runtime 的 state，不重新通过当前 generator 重建 case。

## CLI / Scheduler

新版：
- `run --suite Txxx`
- `run --suite all`

必须使用 construct dispatcher。

legacy historical execution：
- 明确独立命名/路径
- 仅供历史 replay/audit
- 禁止进入新正式 campaign

## Manifest

每 suite/run 冻结：

- dataset version/hash
- construct contract version/hash
- runtime version/hash
- scorer version/hash
- prompt versions
- role prompts
- tool schema
- action budgets
- exact model profile
- source-tree hash
- dependency lock hash

## Replay

每 case 重建：

- world initial state
- actor configs
- exact immutable ModelRequest snapshots
- ModelResponse
- tool/A2A
- selection/delegation/session/message edges
- state before/after
- evaluator truth join
- scorer inputs/formula
- utility
- final outcome

## Gate

在数据 campaign 前用 dev fixtures/mock policies 对 18 suite 跑一遍统一 dispatcher。

必须证明：
- 18/18 不走 `execute_mock_case`
- 18/18 direct frozen-case semantics
- Replay 完整
- no Oracle leak
- state causality
