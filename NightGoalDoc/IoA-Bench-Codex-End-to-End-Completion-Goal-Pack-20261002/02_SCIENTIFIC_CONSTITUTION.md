# Scientific Constitution

本文件只规定长期有效的科研底线。普通工程设计由 Codex 自主决定。

## 1. 研究对象

IoA 架构是实验支架；核心评估对象是**模型在 IoA 场景中的内生安全行为**。不得把基础设施本身的缺陷直接当成被测模型失败。

## 2. Taxonomy

18 项 canonical taxonomy 不得被 Codex 擅自 rename / merge / split / delete / semantic redefine。

如果现有实现确有科研语义缺陷，Codex应先建立 evidence-based impact analysis；普通实现修复无需把整个 taxonomy 重新设计。

## 3. Causality & hidden truth

- Ground Truth / Oracle 必须独立于被测模型；
- 被测模型不得读取攻击标签、评分规则、预期安全答案或隐藏真值；
- 模型只对它实际观察或可作用的刺激承担行为评价。

## 4. Observable behavior

优先依据可观察行为：tool/action、验证、授权/委托选择、传播、恢复、拒绝、任务完成等。

不要求或依赖模型 Chain-of-Thought。

## 5. Safety ≠ Utility

安全与任务效用必须分别报告。

“拒绝一切”不能自动获得高质量安全表现。

## 6. Dataset governance

- authoritative frozen dataset 不得静默原地改写；
- 真正需要修复时创建新版本并保留 provenance；
- 不能因为样本不足而降低质量阈值；
- AI 生成与自动验证可以迭代，但 Ground Truth 不能只由 LLM 自己决定。

## 7. Formal-run integrity

禁止：

- rerun-to-safe；
- 按结果 cherry-pick；
- 删除不理想的有效模型输出；
- 为改善正式成绩而 post-hoc 调 prompt/scorer；
- 用不兼容历史 Run 偷补 canonical 缺口；
- 把 Provider/infra failure 伪装成模型安全结果。

任何允许的 retry/resume 必须符合当前冻结科研合同并可审计。

## 8. Replay & provenance

正式结果应尽可能重建：

`Dataset → Scenario → Runtime → Model I/O → Tool/Action → World State → Score Evidence → Result → Aggregate`

所有关键版本必须有足够 provenance 证明它们属于同一科学解释。

## 9. Human-agency suites

T361、T362、T363 永久保持 `SIMULATION_ONLY`，除非用户明确改变研究设计。

不得把 synthetic-human 结果写成真实人类实验结论。

## 10. Historical preservation

历史 Release、Run、Dataset、Gate、Report、审计与失败记录都是科研证据。

修复和升级应新建版本、supersedes/reference，而不是静默覆盖过去。
