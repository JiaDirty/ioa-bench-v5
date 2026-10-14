# Frozen Research Decisions

## 1. Benchmark 面向多个 Tested Model

不把 `deepseek-v4.1-flash` 固定为唯一最终被测模型。

最终 Tested Model roster 由用户决定。

Codex/Zcode 可以做候选发现、能力探测和比较，但不能未经授权永久替用户决定最终 roster。

## 2. 18 项有独立 Case

18 个 suite 各自有自己的 Dataset。

不是一个 case 同时用于 18 项。

目标约：
- 90 case / suite；
- 30 Easy / 30 Medium / 30 Hard；
- 总计约 1620 case / Benchmark Release。

## 3. 每个 Case 正式执行一次

对每一个 Tested Model：

每个 Frozen Case 正式执行 1 次。

基础设施失败可按规则重试；
已经形成有效模型行为的结果不得为了改变 outcome 重跑。

## 4. Dataset 不按新旧判断

现有 2.x Dataset：

- 合格就 KEEP；
- 缺证据就补证据；
- 语义/Truth/机制有错才发布新版本；
- Frozen Dataset 不原地修改。

## 5. 已有结果不自动作废

已有 T311–T333 等正式结果：

只按科学有效性分类。

如果当次运行可证明严谨、正确、可追溯，就保留为有效研究结果。

不因为以后有新的统一 Campaign 就删除。

## 6. 正式 Campaign 要在18项整体准备好后进行

允许开发阶段逐项：
- 修复；
- 小规模生成；
- 预实验；
- 诊断。

但新的完整正式 Campaign 只有在：

18/18整体通过预实验
→ Benchmark Release被冻结

之后才开始。

## 7. T361–T363

这三项仍属于18项主 Benchmark。

使用：
- 一个冻结的独立 Synthetic Human Model；
- 多个预定义 persona；
- 同一 synthetic-human profile 用于不同 Tested Model。

始终标：
`SIMULATION_ONLY`

## 8. 辅助模型

Generator / Validator / Arbitrator / Synthetic Human Model 不提前写死。

Codex根据：
- 本地 AIHubMix 文档；
- 能力；
- 结构化输出；
- 延迟；
- 稳定性；
- 限流；
- 成本；
- 实际质检质量；

选择最合适模型。

正式 Dataset 最终关键验证必须有独立于对应 Tested Model set 的证据。

## 9. 并发

不固定死某个 concurrency。

通过实际压力测试找稳定吞吐最优值。

正式 Campaign 前冻结 scheduler profile。

## 10. 模型参数

不同模型可有不同兼容参数。

同一个 Tested Model 在同一个 Campaign 中，基础 Model Profile 必须固定。

Construct-specific tools/roles/budgets 可以不同，但必须来自 Contract 并冻结。
