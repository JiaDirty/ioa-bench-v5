# Current Authoritative State

本文件是本 Goal 的起始基线，不是不可修改的事实。Codex 必须独立复核关键结论。

## 当前高置信状态

2026-09-30 只读审计给出的当前结论：

- 18/18 construct implementation 已完成；
- 18/18 authoritative Dataset 已完成；
- 18/18 Pilot 已完成；
- deepseek-v4.1-flash 已有 18×90 = 1620 个 Formal results；
- Dataset hash 三方绑定（Run Manifest / Release / Dataset Manifest）18/18 一致；
- T352/T361/T362/T363 的 run-time source hash 与最终 Release source hash 逐字节一致；
- T312–T353 中其余 13 个 suite 的 Run 后源码变化被审计为不进入各自科研执行/评分路径；
- T311 存在：
  - max_tokens=4096 vs 后续统一 8192；
  - concurrency=1 vs 最终 scheduler 3；
  - contract label 1.0.0；
  但已有证据显示：
  - 647 条相关模型记录中最大 completion 3204；
  - 无 length truncation；
  - concurrency 为 case 调度，不进入单 case 科研语义；
  - contract label 为元数据，契约内容未发生对应语义变化。
- Release freeze 后 `src/contracts/config` 没有科研代码修改；
- 18 个评分实现被审计为在各 Formal Run 前已定稿；
- T361–T363 的 Synthetic Human 为独立 `glm-5.3-flash`，5 persona 生效；
- 当前原 G13 存在“Benchmark 本体验收”和“canonical Campaign 验收”混同；
- 原 `RUN_CLASSIFICATION.json` 对 Run↔Release 绑定检查不够严格；
- Release 缺 runtime prompt content hash、Tool Schema hash 等完整冻结元数据。

## 当前建议状态

不要把项目重新定义为“18 项尚未完成”。

当前更准确的阶段是：

**SCIENTIFIC_CLOSURE_AND_CANONICAL_BINDING**

而不是：

**CONSTRUCT_IMPLEMENTATION**

## 当前 canonical Tested Model roster

用户已确认：
`deepseek-v4.1-flash`

除非用户另行修改，不得扩展 roster。
