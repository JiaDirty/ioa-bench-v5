# Scientific Constitution

本文件规定 v5 可以大胆重构什么，以及绝不能为了方便或旧结果而悄然改变什么。

## 1. 研究对象

IoA-Bench 评估的是**模型在受控 IoA 场景中的内生安全行为**。参考 IoA runtime 是实验支架，不是被评分对象。

环境故障、恶意 peer、错误 registry、协议歧义、声誉/激励信号等只能成为刺激；除非模型实际接触、能够行动并产生相应行为，否则不能直接记成模型安全失败。

## 2. Canonical taxonomy 保留

18 项 canonical taxonomy 保留：

T311、T312、T313、T321、T322、T323、T331、T332、T333、T341、T342、T343、T351、T352、T353、T361、T362、T363。

可以重构 operationalization、scenario、scorer 和数据；不能未经用户批准 rename / merge / split / delete / semantic redefine。

## 3. Construct before code

任何新 suite/scorer/data 的设计顺序必须是：

`intended construct → causal hypothesis → manipulation/exposure → observable behavior → safe/unsafe/utility/recovery definitions → exclusions/confounders → scorer → data`

不能从已有代码或旧 scorer 反向拼凑理论定义。

## 4. Model-visible information must be neutral

被测模型不得直接看到：

- Oracle/GT；
- `unsafe_*`、score、expected-safe 等 evaluator judgement；
- suite/taxonomy identity；
- 仅为 scorer 服务的 “critical/malicious/risk” 判定字段；
- intended answer；
- hidden attack label。

业务世界中客观可观察的事实可以出现，但 evaluator 的结论必须保持隐藏。

所有 provider-facing messages/tool results 必须接受 payload-level leakage audit，而不是只搜索 `oracle`/`ground_truth` 关键词。

## 5. Exposure must be provable

每个 formal case 必须能从持久化证据证明：

`target mechanism → model-visible exposure → opportunity to act → model behavior → world consequence → score evidence`

没有 exposure proof 的 case 不能被当作该 construct 的行为测量实例。

## 6. Safety and task utility are distinct

普通答错、格式错、任务没完成，不自动等于安全失败。

安全 scorer 必须说明：

- 哪个 observable behavior 违反了什么安全 predicate；
- 为什么它由目标机制触发或相关；
- 与普通 capability/utility failure 如何区分。

## 7. Causal and discriminant validity

Control/Treatment 或 counterfactual pairing 应尽可能只改变目标机制。

高重叠 construct 必须有 negative controls、mechanism ablation 或其他 discriminant evidence，特别关注：

- T311 / T312 / T353
- T313 / T323
- T321 / T322
- T331 / T342
- T332 / T333
- T341 / T343 / T362
- T351 / T352 / T353
- T361 / T362 / T363

## 8. Dataset is a measurement instrument

“每项 90 条/120 条”只是配额，不是质量证据。

v5 必须从 scenario-family / mechanism coverage 层设计数据，并证明：

- effective scenario-family N；
- pair-aware diversity；
- subtype coverage；
- world/role/evidence/action-path diversity；
- 非 entity-substitution-only；
- 无明显 benchmark shortcut；
- Ground Truth 可审计且允许合理的多路径安全策略；
- difficulty 是有证据的 strata，而不是仅有标签。

不允许为了凑数降低质量阈值。

## 9. Scoring must be preregistered before formal run

正式 Campaign 之前冻结：

- safety predicate；
- utility predicate；
- recovery predicate；
- outcome priority；
- invalid/budget/infra policy；
- denominator rules；
- uncertainty analysis；
- validators/exposure checker；
- report/aggregation logic。

Campaign 之后发现 validator/scorer 语义缺陷，应进入新版本，而不是 post-hoc 改验收器来让旧结果通过。

## 10. Reliability evidence is separate from reproducibility

Deterministic code、Replay 完整、hash 一致只能证明工程复现性。

论文级 measurement reliability 需要适当的：

- independent review / expert agreement；
- judge agreement（若用 judge）；
- test–retest / repeated subset；
- uncertainty / sensitivity analysis。

没有证据就写 `NOT YET ESTABLISHED`。

## 11. Human-agency boundary

T361–T363 保持 `SIMULATION_ONLY`，除非用户明确批准改变研究设计并获得真正的人类研究依据。

synthetic persona 的结果不能写成真实人类 agency 结论。

## 12. Historical integrity

v4.1.13 与更早 Release/Run/Dataset/Report/Audit 永久保留为历史证据。

v5 不覆盖、不篡改、不重命名历史结果。

所有重大变化必须以新版本、supersedes/provenance 表达。

## 13. 单模型正式研究边界（PI-V5-005）

- v5 唯一正式被测模型是 AIHubMix 请求 ID `deepseek-v4.1-flash`；历史响应名 `deepseek-v4-1-flash-260910` 仅是需要保存/核验的 Provider 身份证据，不能当成另一个必测模型。
- 不要求跨模型排序、跨模型区分力或四模型 Gate E。不能把历史四模型 Pilot 追认成有效正式试验。
- 生成/复核/模拟角色所用辅助模型不属于被测模型，不得让被测模型参与出题真值形成或独立判分。
- 单模型结果只支持事先界定的该模型、该配置、该候选分布的结论，不代表其他模型或真实人的行为。

## 14. Honest claims

目标是让证据决定论文能写什么，而不是让实现迎合预期结果。

即使 v5 最终显示模型表现很差，只要测量有效、过程严谨，这仍然是成功的 Benchmark。
