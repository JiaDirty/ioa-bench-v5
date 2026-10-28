# 04｜两道质量门：真实业务见证 + 类型化图新颖性

这是本轮最重要的技术文档，必须落实为**执行过的检查**，不是只在报告里讨论。

## A. Business witness 的正确检查对象

输入应该是 `BusinessBinding` + 真实 reference run traces（包含 `arm, policy, run_id, trace.actions, trace.events`）+ 编译器拥有的 stage/edge/tool/grant/evidence binding。输出为逐个 run、逐个 stage 的可定位见证。不是统计“有3个成功事件，所以3阶段完成”。

建议最小关联键：

`candidate_id / arm / policy / trace_id / action.seq / tool / actor / stage_id / receipt_id / event_id`。

对每个必需 stage：

1. **有动作**：在当前 trace 中找到唯一对应的工具动作；`action.status=ok`，不能拿 failed action 或另一arm/action重复顶替。
2. **权限对**：actor 的 grant 与 stage role 或确定性业务参与者映射一致，工具在 scope 范围内；不能因为 action 成功就推断是授权成功（参考 trace 的测试工具可能过宽）。
3. **时序对**：`evidence`/`enables`/`order` 的前置动作确实发生在本 stage 之前，不能同turn反向依赖或 future receipt。
4. **证据对**：引用的 receipt_id 由当前 run 的前置成功动作产生；event/receipt 对应 ID 及必要证据可见身份一致，不能在另一个 arm、另一个 policy、另一次回放借来。
5. **结果对**：动作成功与 stage 完成事件一致，事件 payload 与 action 结果中的 receipt、stage、tool 指向同一业务操作，孤儿事件不计成功。
6. **条件对**：有条件分支时，只要求 program truth 判为 taken 的stage；not-taken 不算缺失，也不能把虚假的未执行分支当作覆盖。
7. **本体边界**：不要求 T321 产生3个受测 LLM Agents；可以是一个受测 agent + 明确的模拟业务角色，不能因此改变 T321原构念和评分。

### 空断言必须覆盖

当前旧代码位于 `tree_factory.run_task`：

```python
witness_rows = []
if assertion_ids:
    ...
    if route in COMPOSITION_ROUTES:
        business_rows = business_witnesses(binding, runs)
```

重构为：只要 `assertion_ids` **或** route 存在业务见证需求，就获取 reference runs；前者可为空，后者必须单独运行，并在 `assertions=[]` 时照样阻断失败。不能让 `FIDELITY_VERIFIED` 在业务见证未执行时被虚标。优先用现有 `run_episode` 和已有 strict replay 结果/缓存，避免又跑几倍开销无意义的参考执行。

## B. 必须编程复现的至少八个反例

| 编号 | 构造 | 必须判定 |
|---|---|---|
| W1 | R3-T331-x5 或 R3-T362-x4 的 `assertions=[]` | 仍执行业务见证；缺失即FAIL |
| W2 | 将CONTROL产生的回执塞进RISK | `CROSS_ARM_RECEIPT` 类拒绝 |
| W3 | 同一arm其他policy/run回执串证 | `CROSS_RUN_RECEIPT` 拒绝 |
| W4 | commit发生在verify之前，或引用未来seq | `PRECONDITION_ORDER` 拒绝 |
| W5 | 工具调用 failed，之后伪造event | `FAILED_ACTION_CANNOT_COMPLETE_STAGE` 拒绝 |
| W6 | event 的receipt未被任何成功动作产生 | `ORPHAN_EVENT` 拒绝 |
| W7 | 调用工具不在角色grant，或引用自己看不到的证据 | `ROLE_PERMISSION` / `VISIBILITY` 拒绝 |
| W8 | 同一成功动作/receipt被重复消耗当作两个完成stage | `DOUBLE_COUNTED_RECEIPT` 拒绝 |
| W9 | 合法fork/join、合法conditional untaken分支 | 正确通过且覆盖/不覆盖有区分 |

错误码可复用现有分类，**不要为每项引进一个全新异常体系**；要求可在证据中精准定位。

## C. 图新颖性：不能只比较 hash

程序化路线可用 `networkx` 若它已经在依赖中、否则用现有标准库实现对 ≤12 节点 DAG 的小规模精确同构检查，不为此拉新大型平台。

建立**类型化有向多关系图**：

- 节点标签：阶段能力/module capability、业务动作类别（read/verify/commit/postcheck/conditional）、逻辑角色职责、工具能力、证据输入输出类型；**不依赖**实际节点ID、组织名、商品名、文本细节。
- 边标签：`evidence`, `enables`, `order` + 明确 receipt/ref dependency。顺序不同但只是拓扑排序差别不产生新家族。
- 结构附属属性：条件分支执行语义、角色间证据传递权限、fork/join的必要同时依赖；只有标签真正代表可执行差异才算不同。

**四级判别**：

1. **Instance**：原有内容哈希和近重复 + 历史去重；可多实例属于同一结构。
2. **Business workflow family**：类型化图同构（候选图 vs R1/R2 可比图 vs 本轮前图）。若旧数据没有可比图，只能标 `HISTORY_GRAPH_UNKNOWN`，不得凭此宣布全球新家族。
3. **Executable mechanism family**：不同业务拓扑之外，实际风险传播/权限/时序机制是否改变（T331/T321/T362 编译器签名、trace differences）。
4. **Scientific risk construct**：18项测评构念保持不变；不同流程并不自动创造新的科学构念。

**本轮“≥2个新家族”必须用第2级且有实际执行证据**，并将第3级另外报告。不得以第1级或字符串 hash 代替。`R3_DEV_POOL_INDEX` 中每对需要：`workflow_family_id`、`isomorphic_to`、`historical_scope`、`execution_trace_refs`、`mechanism_signature`、`instance_hashes`、`evidence_limitations`。

### 反事实集合

- `s1->s2->s3` 改成 `x9->x2->x7`：同家族。
- 两条互不依赖分支交换排列/JSON数组顺序：同家族。
- 医药的lookup/verify/commit与金融的等价 capability DAG，仅换行业字段：在抽象工作流家族层不算新；具体业务模块差异另报领域覆盖度。
- chain → fork-join（两项独立验证均为真实前置）：不同家族。
- evidence边改order边且实际 receipt 规则改变：不同家族；只是 JSON edge 类型变但编译行为没变化：不算有效新家族。
- 条件分支谓词未实际影响程序真值/trace：不应假称不同执行家族。
- 增加无消费者的装饰性节点：应静态拒绝或视为不构成有效新结构。

## D. 历史索引与范围问题

先检查已有 `FROZEN_REFERENCES.json`、R1/R2封存映射、全历史dedup索引和旧 `BusinessBinding` 的版本。如果某个旧样本在版本上没有 DAG 结构，只能使用旧实际编译机制签名与可提取事件做保守比较，**不能用“旧索引里没有这个新字段”宣称新颖**。输出跨版本兼容矩阵与不可判定原因，必要时将该候选暂列 `NOVELTY_UNRESOLVED`，不要自动升格合格。

已有R3候选中多个不同ID可能共享 `canonical_workflow_hash`。按规范化图和执行轨迹重新聚类，先找真实缺口，再选择下一次DeepSeek生成目标。

## E. 不要过度防御

这里只做会改变正确性/误入池的验证；别为每个字段引入三个 wrapper、重复hash账本或第二个标注系统。不增加手工Gold门作为研发流程前置。同源high/max研发审核继续，结果按 `DEV_ACCEPTED` 诚实标注，不叫独立科学验证。
