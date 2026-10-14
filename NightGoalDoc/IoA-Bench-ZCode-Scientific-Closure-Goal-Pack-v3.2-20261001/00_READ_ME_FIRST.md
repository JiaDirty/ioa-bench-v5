# IoA-Bench ZCode Scientific Closure Goal Pack v3.2

本包用于当前阶段：**18 项实现完成后的科研收口、Run↔Release 绑定固化、最终验收修订与交付冻结**。

它不是新的“开发 18 项”Goal，也不是让 ZCode 从头重做 Benchmark。

## 当前阶段

根据 2026-09-30 的只读科研一致性审计，当前高置信结论为：

- 18/18 suite 实现完成；
- 18/18 authoritative Dataset 完成；
- 18/18 Pilot 完成；
- deepseek-v4.1-flash 已有 18×90 = 1620 个 Formal results；
- 17 个 suite 与最终 Release 有强绑定证据；
- T311 存在 max_tokens / concurrency / contract-label 偏差，但已有“不影响实际结果”的证据；
- 当前主要剩余工作是独立复核、固化 Run↔Release 追认绑定、补齐 provenance、拆分最终验收并重建最终交付包。

## 推荐目录

将本目录放到：

`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-ZCode-Scientific-Closure-Goal-Pack-v3.2-20261001`

ZCode 目标模式使用：

`GOAL_PROMPT_ZCODE_V3_2.md`

若需要直接粘贴 `/goal`，使用：

`PASTE_GOAL.txt`

## ZCode 目标模式适配

ZCode 会在每轮结束时自动判断 Goal 是否完成，未完成时自动继续。因此本包要求：

- 每轮根据真实磁盘证据校验 S0–S11；
- 计划、TODO、总结、旧 PASS 都不能单独算完成；
- 恢复会话后从 State / Checkpoint / Gate 继续，不重新初始化；
- 只有真正需要用户科研决策、付费正式重跑或外部凭证时才暂停。

## 当前 ZCode 执行模型的身份

ZCode 当前使用的模型只是**项目执行/审计代理**。它不是 IoA-Bench 的 Tested Model，也不能因为执行代理模型发生变化，就自动写入 Tested Model、Validator、Synthetic Human 或 Formal Run provenance。

当前用户已确认的 canonical Tested Model roster 仍为：

`deepseek-v4.1-flash`

## 默认限制

- 不重新设计 18 项；
- 不重新生成已合格 Dataset；
- 不重新执行 1620 个 Formal case；
- 默认不调用 AIHubMix；
- 不覆盖历史 Run / Release / Gate；
- 不因 source hash 不同机械判定重跑；
- 不因旧 Gate 写 PASS 就机械判定完成。

只有新证据证明存在真实科研语义缺陷时，才进入最小范围的修复或重跑分支。
