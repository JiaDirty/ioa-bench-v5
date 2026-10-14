# Retroactive Release Binding Protocol

## 目的

证明一个在 Release 冻结之前执行的 Formal Run，是否可以科学地追认绑定到该 Release。

时间先后本身不是唯一判据。

## 追认条件

每个 suite 必须至少满足：

1. Dataset exact content match；
2. Contract semantic match；
3. Runtime semantic match；
4. Scorer semantic match；
5. Runtime Prompt exact/semantic match；
6. Tool Schema exact/semantic match；
7. Tested Model identity 一致；
8. 影响模型行为的 sampling/profile 参数一致，或偏差被证明未实际生效；
9. invalid-output/retry semantics compatible；
10. Replay integrity；
11. Oracle/SUT isolation；
12. 无 Run 后被发现会改变该 Run 科研解释的 bug。

## 绑定等级

### STRICT_BINDING
运行时科研相关内容与 Release hash/内容严格一致。

### SEMANTIC_BINDING
整体 source hash 不同，但逐路径证明差异不会进入该 suite 科研行为或评分。

### BINDING_WITH_DOCUMENTED_DEVIATION
存在配置差异，但有直接证据证明该差异在本 Run 中未生效或只属于非语义元数据。

### UNPROVEN
证据不足。

### INCOMPATIBLE
存在已证明会改变模型行为、任务条件或评分结果的差异。

## 当前预期

上一轮审计预期：
- 4 suites STRICT_BINDING；
- 13 suites SEMANTIC_BINDING；
- T311 BINDING_WITH_DOCUMENTED_DEVIATION。

ZCode 必须独立验证后再固化。

## 正式输出

- `artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT.json`
- `artifacts/reports/retroactive_release_binding_audit.md`

每 suite 必须有：
- Run ID；
- dataset binding；
- source relation；
- relevant diff；
- prompt hash；
- tool hash；
- scorer/runtime evidence；
- profile evidence；
- binding level；
- rerun_required；
- evidence paths。
