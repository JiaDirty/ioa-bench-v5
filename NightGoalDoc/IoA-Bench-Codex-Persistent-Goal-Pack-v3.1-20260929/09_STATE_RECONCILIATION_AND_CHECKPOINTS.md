# State Reconciliation & Checkpoint Discipline

## 为什么必须自动对账

项目已出现过：

- Run 实际完成，但状态写未完成；
- Dataset实际是2.4.0，状态仍指2.0.0；
- Gate PASS，Work Queue仍 blocked；
- source hash算法不一致。

因此状态文件必须是**派生记录**，不是事实本身。

## Deterministic rebuild

建立或完善状态重建器，从：

- datasets；
- manifests；
- pilots；
- runs；
- results；
- replay；
- gates；
- source hashes；

推导：

- authoritative Dataset；
- pilot status；
- formal status；
- run classification；
- canonical compatibility；
- benchmark release；
- per-model campaign completeness。

## 每段工作结束

立即同步：

- artifact；
- Gate；
- Project State；
- Work Queue；
- Checkpoint；
- Changelog。

并运行 consistency verifier。

## Goal 重复出现时

绝不把它当初始化信号。

读取：
- Checkpoint；
- State；
- Work Queue；
- current evidence。

然后继续当前未完成 Gate。

## Canonical ≠ Valid

一个 Run 可以：

- VALID=true
- CANONICAL=false

这表示它是有效科研结果，但不属于某个指定 Campaign 的聚合版本。
