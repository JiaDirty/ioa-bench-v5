# Final Delivery & Provenance

## 最终报告需要更新

只更新“结论与 provenance”，不改实验结果。

至少明确：

- Benchmark Release base；
- Addendum；
- canonical Dataset Pack；
- canonical Tested Model roster；
- 18 Formal Run IDs；
- binding level；
- T311 documented deviation；
- 18 suite outcome aggregation；
- single-execution limitation；
- T361–T363 SIMULATION_ONLY；
- invalid/provider denominator；
- known limitations。

## Dashboard

不能把 development/exploratory/invalidated Run 混入 canonical aggregation。

## Reproducibility Bundle

必须包含：

- base Release；
- Release Addendum；
- Dataset Pack；
- normalized Model Profile；
- independent reverification；
- retroactive binding audit；
- T311 deviation artifact；
- new acceptance artifacts；
- canonical run manifests；
- replay references；
- reports；
- code/tests/contracts/config；
- dependency lock；
- handoff docs。

## Secret discipline

任何新的：
- Goal；
- Changelog；
- report；
- manifest；
- handoff；
- zip；

都不得包含 API key。

构建包后：
- secret scan；
- CRC；
- manifest；
- SHA-256；
全部记录。

## 历史资产

以下保留，不删除：

- 原 Benchmark Release；
- 原 G13；
- 原 RUN_CLASSIFICATION；
- 所有旧 Run；
- superseded Dataset；
- historical gates。

新 artifacts 通过 supersedes/reference 字段解释关系。
