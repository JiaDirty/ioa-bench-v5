# Outcome & Completion Contract

本文件把长期目标拆成“完成时必须是真的什么”。

## A. Benchmark 本体

最终必须存在一个明确版本的 Benchmark Release：

- 18 canonical suites；
- 18 accepted datasets；
- versioned Dataset Pack；
- versioned Contracts；
- versioned Runtimes；
- versioned Scorers；
- Prompt content hashes；
- Tool schema hashes；
- Replay schema；
- Run Manifest schema；
- Provider/Retry policy；
- Scheduler/Concurrency profile；
- dependency lock；
- source-tree hash；
- Windows runtime profile。

## B. 数据

每个 suite 的 authoritative Dataset 必须有：

- version；
- content hash；
- manifest hash；
- case count；
- difficulty coverage；
- mechanism coverage；
- Control/Risk structure where applicable；
- Ground Truth；
- rejected / not-selected provenance；
- validation evidence；
- leakage evidence；
- runtime compatibility evidence。

## C. 运行

每个正式 Run 必须可回答：

- 用了哪个 Benchmark Release？
- 哪个 Dataset？
- 哪个 Tested Model exact ID？
- 哪个 Model Profile？
- 哪个 Prompt？
- 哪套工具？
- 哪个 Scorer？
- 哪个 source hash？
- 哪个 dependency lock？
- 是否有 Replay？
- 是否 terminal？
- 是否发生 provider retry？
- 是否有 invalid output？
- 是否属于 canonical campaign？

## D. 多模型

Benchmark 必须支持：

同一 Benchmark Release
→ 多个 Tested Model
→ 每个模型完整18项
→ 每个 case 一次有效正式执行
→ 分模型独立结果
→ 可公平比较。

## E. 科研输出

至少有：

- per-suite raw outcomes；
- Safety metrics；
- Task Utility；
- difficulty breakdown；
- mechanism breakdown；
- six-family profile；
- invalid/provider denominators；
- latency/tokens/cost；
- failure/recovery examples；
- model-to-model comparison；
- SIMULATION_ONLY 标注；
- Dashboard；
- Report；
- Reproducibility Bundle。

## F. 不能算完成的情况

以下任何一项存在，都不能称为最终完成：

- 18 项仍有未验收 suite；
- Dataset 有已知语义错误；
- Formal Run 无法追溯配置；
- Campaign 混入不同 Benchmark Release 却未标注；
- Replay 缺失且无法重建；
- Provider failure 被算作模型安全失败；
- 历史 invalid run 被 Dashboard/Report 当成正式结果；
- T361–T363 未标 `SIMULATION_ONLY`；
- Tested Model roster 尚有用户明确要求但未完成的模型；
- final acceptance 仅依赖总结文本而没有可核验证据。
