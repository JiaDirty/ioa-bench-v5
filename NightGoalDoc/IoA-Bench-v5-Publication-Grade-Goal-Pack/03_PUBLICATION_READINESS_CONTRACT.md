# Publication Readiness Contract

`PUBLICATION_READY` 不是“没有发现 bug”，而是当前证据足以支撑预先限定的论文 claim。

以下 Gate 是**完成证据**，不是要求模型机械按顺序做 checklist。Codex 可以调整实现路径，但不能绕过 required Gate。

## Gate A — Construct & Causal Validity

18/18 suites 必须有版本化 construct map，至少固定：

- intended construct
- what is explicitly out of construct
- mechanism subtypes
- causal hypothesis
- treatment / control / counterfactual
- exposure definition
- model-visible evidence
- action opportunity
- safe behavior
- unsafe behavior
- task utility
- recovery
- exclusions
- confounders
- expected failure modes
- discriminant relation to adjacent constructs

通过要求：

- T352/T362 等已知错位得到实质重构或有充分证据保留；
- 高重叠 construct 有 discriminant tests / negative controls / mechanism ablation plan；
- 普通 capability error 不被系统性混入 safety failure；
- external/domain review 没有 unresolved critical construct objection。

## Gate B — Scoring Validity

18/18 scorer 必须从 construct map 推导，而不是从旧实现继承。

每 suite 至少明确：

- deterministic evidence inputs
- safety predicate
- utility predicate
- recovery predicate
- outcome precedence
- invalid/budget/infra handling
- denominator membership
- boundary examples
- cases where scorer must abstain / mark uncertain

通过要求：

- no evaluator outcome leakage；
- scorer 与 blinded audit gold set 达到预定义 agreement threshold；
- 重大 disagreement 有原因分类与修复；
- AI judge 若存在，必须有明确 role、prompt/version、agreement/calibration evidence；
- formal scorer/validator 在 Campaign 前被 Release pin。

## Gate C — Dataset Quality & Diversity

v5 数据必须由 scenario-family architecture 驱动，而不是把 quota 当多样性。

每 suite 需要可复核的：

- scenario-family inventory
- mechanism subtype coverage
- control/treatment pairing
- world/topology variation
- role/org variation
- evidence-pattern variation
- action-path variation
- safe-strategy/recovery variation
- pair-aware dedup
- entity-substitution-only audit
- leakage audit
- ambiguity/GT audit
- difficulty evidence

通过要求：

- 明确报告 effective scenario-family N；
- 不以 entity/name/number 替换伪装多样性；
- paired cases 的相似来自受控实验，而不是整个 suite 只有一个模板；
- visible payload 不含 evaluator labels / suite identity；
- Ground Truth 对允许的合理策略不过度唯一化；
- 数据质量阈值不能为了凑任何固定条数（当前候选为每项120条）下调。

如果合格 case 不足，继续改 generation/validation 或减少 claim，不得降低标准。

## Gate D — Independent Validation & Reliability

publication-ready 至少需要一份 blinded、stratified 的独立 review set。

Codex 应负责准备：

- sampling protocol
- reviewer instructions
- blind review package
- label schema
- disagreement taxonomy
- agreement calculator
- arbitration protocol

AI 可以作为额外 validator，但不能冒充人类/领域专家。

若论文 claim 需要 human/expert validity，而当前没有 reviewer，Codex 完成所有可自动化部分后停在该 Gate 请求外部输入。

通过要求应预先写入 v5 protocol，例如：

- construct/content validity agreement
- scorer agreement
- ambiguity/leakage false-accept audit
- judge/human agreement（若适用）
- repeated subset / test–retest stability
- sensitivity to non-behavioral missingness

具体阈值应由 Claude依据领域惯例、pilot distribution 与论文 claim 做有依据的 preregistration；不要事后按结果调低。

## Gate E — Pilot Scientific Validation

在完整数据冻结与 Formal Campaign 前，先用小而有代表性的 pilot 证明设计值得扩张。

Pilot 应跨：

- all 18 suites
- Easy/Medium/Hard
- control/treatment
- major scenario families
- known boundary cases

Pilot 的目标不是追求高模型分数，而是检查 measurement system：

- Exposure proof 是否闭合
- Leakage 是否为 0
- scorer/reviewer agreement
- invalid/budget/infra 是否异常集中
- difficulty 是否至少具有可辩护区分
- control/treatment manipulation 是否工作
- 是否出现 ceiling/floor 或 shortcut
- adjacent constructs 是否表现出可区分机制

Pilot 失败 → 修设计 → 再 pilot。

不要用失败 pilot 直接升级到 full formal。

## Gate F — Frozen v5 Scientific Release

在新 Formal Campaign 之前，Release 必须一次性 pin：

- source/runtime
- 18 construct contracts
- authoritative dataset + content hashes
- prompts
- tool/provider-facing schemas
- scorers
- exposure checker
- validators
- model profile
- synthetic-human profile
- scheduler/action budgets
- retry/interruption policy
- denominator rules
- statistical analysis plan
- aggregation/report code
- acceptance toolchain
- dependency/environment evidence

Campaign 开始后，不允许为改善通过率修改上述语义组件。

## Gate G — Formal Campaign

只有 A–F required gates 有可审计通过证据、正式版本冻结且用户**另行明确批准付费正式运行**后，才运行新的完整 Formal Campaign。

要求：

- no rerun-to-safe
- all attempts preserved
- explicit exposure evidence
- runtime ↔ release binding
- historical baseline 不混入 v5 canonical result
- Provider/infra failures 独立记录
- T361–T363 保持 `SIMULATION_ONLY`

## Gate H — Statistical & Publication Acceptance

最终报告至少区分：

- scheduled denominator
- eligible behavioral denominator
- invalid/budget/infra
- safety outcome
- task utility

并提供适合当前设计的 uncertainty，例如 Wilson / Clopper–Pearson / bootstrap / hierarchical methods。

需要根据最终 claim scope 评估：

- repeated subset / test–retest
- baseline
- negative control
- mechanism ablation
- sensitivity analysis
- model comparison：**本轮单模型协议不支持该 claim，非本轮必需 Gate**

最终必须给出：

- supported claims
- unsupported claims
- internal validity limitations
- external validity limitations
- simulation-only boundaries
- remaining uncertainty

## 不混淆的四个完成状态

1. `IMPLEMENTED`：18项代码齐全，不能替代 Pilot。
2. `OFFLINE_VERIFIED`：本地参考策略/回归通过，不能替代真实模型行为。
3. `READY_FOR_EXTERNAL_VALIDATION` / `BLOCKED_EXTERNAL_REVIEW`：自动化工作可完成；人工评审尚未通过时，**不得宣称科研通过**。
4. `PUBLICATION_READY`：只有当全部适用 Gate A–H 通过且论文 claim 与证据一致时才能声明。

若缺独立审阅者或费用授权，应在完成所有合法的离线任务后报告 `BLOCKED` 与解锁条件，而不是绕过 Gate、无限循环或假装 Goal 完成。

## Final completion rule

只有当 required gates A–H 被当前磁盘证据证明通过，而且不存在影响主要论文 claim 的 unresolved CRITICAL/MAJOR blocker，才允许：

`PUBLICATION_READY = YES`

这里的 “publication-ready” 表示方法与证据达到可负责任投稿的状态，不保证任何会议/期刊一定接收。
