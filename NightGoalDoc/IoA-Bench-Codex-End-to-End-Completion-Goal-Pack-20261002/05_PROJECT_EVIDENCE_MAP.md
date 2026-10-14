# Project Evidence Map

本文件告诉 Codex **去哪里找证据**，不预先替 Codex 判断当前状态。

## 首先读取

1. `AGENTS.md`
2. `state/PROJECT_STATE.yaml`
3. `state/WORK_QUEUE.yaml`
4. `state/SCIENTIFIC_CLOSURE_CHECKPOINT.md`
5. 当前相关 `release/*.json`

## 科研定义与合同

- `contracts/`
- `config/`
- `AGENTS.md`
- 相关 ADR / design decisions
- `state/DESIGN_DECISIONS.yaml`

## 18 项实现

- `src/ioabench/`
- suite runtime/scorer modules
- dispatcher / model / sandbox / replay / report layers
- `tests/`

不要只检查“文件存在”，应检查正式执行路径真正调用的是哪一份实现。

## Dataset

- `data/datasets/`
- Dataset Pack manifests
- per-suite manifest / cases / validation / rejected provenance
- frozen version maps

## Releases & provenance

- `release/`
- frozen source/config/contract hashes
- runtime/model/scheduler profiles
- run manifests
- supersedes / addendum / version history

## Formal Runs

- `data/runs/`
- runtime manifests
- checkpoints
- results
- Replay
- attempt/provenance logs

区分：
- mock / pilot / fixture；
- historical formal；
- current canonical formal。

## Artifacts

- `artifacts/gates/`
- `artifacts/reports/`
- `artifacts/scientific_closure_*`
- canonical aggregation outputs
- delivery manifests / inventories / validation outputs

## Goal packs

`NightGoalDoc/` 中有多代历史 Goal Pack。

它们用于理解历史决策和工作方法，但不是天然的当前 truth。旧 Goal 中的局部任务或旧 blocker 不应覆盖当前磁盘证据。

## Historical bundles

历史 ZIP / delivery package / session export 可以用于取证和恢复 provenance，但不得因方便而覆盖当前 canonical scientific contract。

## Evidence conflict rule

当“旧文档说 PASS”而当前运行/文件/hash 显示失败时，按失败处理并继续解决。

当“旧文档说有 blocker”但当前真实实现与验证已证明其关闭时，不要继续被旧 blocker 绑住。
