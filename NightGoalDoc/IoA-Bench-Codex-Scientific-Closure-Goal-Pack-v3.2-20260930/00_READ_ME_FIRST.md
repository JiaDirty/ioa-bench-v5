# IoA-Bench Codex Scientific Closure Goal Pack v3.2

本包用于当前阶段：**18 项实现已完成后的科研收口、Run↔Release 绑定固化、最终验收修订与交付冻结**。

它不是新的“开发 18 项”Goal，也不是让 Codex 从头重做 Benchmark。

## 当前阶段的工作定义

根据 2026-09-30 的只读科研一致性审计，当前证据支持：

- 18/18 suite 实现完成；
- 18/18 authoritative Dataset 完成；
- 18/18 Pilot 完成；
- deepseek-v4.1-flash 已有 18×90 = 1620 个正式结果；
- 17 个 suite 与最终 Release 有强语义绑定证据；
- T311 存在 max_tokens/concurrency/contract-label 偏差，但已有“未实际影响输出”的直接证据；
- 主要剩余问题是把上述证明正式固化进项目，并修正原 G13 把“Benchmark 本体验收”和“DeepSeek canonical Campaign 验收”混在一起的问题。

## 使用

建议放到：

`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-Codex-Scientific-Closure-Goal-Pack-v3.2-20260930`

Codex Goal 使用：

`GOAL_PROMPT_CODEX_V3_2.md`

## 重要

本 Goal 默认：

- 不重新设计 18 项；
- 不重新生成合格 Dataset；
- 不重新跑 1620 case；
- 不把历史 Run 静默覆盖；
- 不把“hash 不同”机械等同于“必须重跑”；
- 不把“已有 PASS”机械等同于“已经证明”。

如果独立核验推翻了关键审计结论，则按证据缩小影响范围；只有发现真实科研语义缺陷时才进入重新实现/重跑分支。

## GPT-6 Astra 的角色

当前 Codex 使用 GPT-6 Astra 只是开发/审计代理模型。

它不是 IoA-Bench 的 Tested Model，也不能因为 Codex 自己使用 GPT-6 Astra，就把 GPT-6 Astra 写入 Benchmark 的 Tested Model、Validator 或 Synthetic Human provenance。

当前已确认的 canonical Tested Model roster 仍是：
`deepseek-v4.1-flash`
