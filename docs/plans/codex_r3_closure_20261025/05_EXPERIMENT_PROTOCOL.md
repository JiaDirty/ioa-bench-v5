# 05｜真实试跑与冻结新旧对照：把改进效果测出来

## 目标

同一 `deepseek-v4.1-flash-1017`、同一批**已冻结**18个匹配任务机会（每套6个：T321/T331/T362），两条路径比较：

- Baseline：`tree_ir_runtime_v2`（R2兼容、预编译业务流）
- Treatment：`compositional_r3`（模型提合法WorkflowPlan DAG → 编译 → 执行）

采用已经存在的 `TASK_SET_FROZEN_R3.json`、`R3_AB_PREREGISTRATION.json`；不要另建一套“更好看”的冻结题目。已执行且终态确定的请求完全复用；缺失且**确认没发出过**的任务用新的request id续完。若协议改变过，按 `protocol_version` / `attempt_seq` 分组，不能把“后修复”冒充“第一次”。

## 候选生命周期和原因归因

对每个 `(suite, frozen_task_id, route)` 定义：

1. 第一发送意图/请求ID → 发出/终态（若未发出则 `NOT_SENT`）
2. Model returned? JSON schema合法? 工作流可编译? 能否Strict Replay?
3. Business witness/Mechanism assertions/Pair causal/Oracle/historical index 通过?
4. `DEV_AUDIT` high/max 是否一致、引用事实合同合法、有没有同源审核分歧?
5. `ADMISSION` 是 `DEV_ACCEPTED`, `QUARANTINED`, `REJECTED`, `FAILED`, `UNRESOLVED` 还是 `NOT_RUN`?
6. `repair_of` / `new_attempt_id` 指向修复尝试；没有首轮结果不得偷算首轮分母。

原始数据保存各类失败例，不用总结报告取代真正 `RESULT.json`、`REQUEST_LEDGER.jsonl`、`AUDIT_RESULT.json` 等。

## 报告最少指标

| 指标 | 定义 | 注意 |
|---|---|---|
| First-pass engineering success | 初始且发出并确认终态的机会中，通过所有确定性硬门比例 | 不把下游补跑混入 |
| First-pass DEV_ACCEPTED | 同一冻结首轮机会中最终研发入池比例 | 审核分歧应如实拒或隔离 |
| End-to-end effective throughput | 全部发送意图中最终新增的合法、非同构工作流家族/任务机会 | 隔离UNKNOWN独立记 |
| Workflow family richness | 在真实执行下类型化图非同构数 | 不把换ID/行业名字算新 |
| Mechanism diversity | 风险机制/执行签名实际差异 | 与业务DAG新颖性分列 |
| Domain/task diversity | 医药/金融角色-工具-证据链覆盖 | 语义非空但不自动算家族 |
| Model reliability | 模型完成/截断/JSON失败/连接中断/未知终态次数 | 同时记录有效分母 |
| Resource efficiency | 每有效独立家族的模型调用次数、总Token、总耗时 | 成本可观察但不约束 |
| Audit calibration | 程序负例/正例 + 真实模型误判分类 | 不称发表级独立审查 |

**真实探索数据太少，报告趋势即可**。可给配对差值+区间，但不能没有统计功效就写显著优于；效率看“每个真正新家族需要多少有效模型调用”，不追求最低成本。

## 冻结规则的实际边界

- 若原始R3冻结条件在本轮前已因 bug 修复改变，不删除错误样本；在报告里定义 `original_frozen` 与 `post_fix_exploratory` 两条清晰序列。
- 首轮 18×2 = 36 个潜在路由机会，不代表已经成功发送36次；按**真正的**账本检查。
- R3已有 T321多对入池无需清零；新颖性分类若使部分失去“新家族资格”，只需**新ID补缺**，不篡改既有准入收据。
- 审核改合同、字段或重新尝试，用新版本+新ID；不能把旧审核判决覆盖掉以提高通过率。
- 线上任何一条请求响应不确定，保留意图和 stop，不再次发送相同POST；仍可对其他合法新任务继续（除非Study的全局STOP依法阻止写同一run）。

## 必做消融（优先复用 `tf_r3_ablation.py`）

1. Tree-Off：非法跨域绑定被拒，不用模拟不存在的成功轨迹。
2. Composition-Off：相同能力目录、静态业务流最多能覆盖多少合法结构；对比组合器在实际执行下的增益。
3. Witness-Off：用已有恶例展示宽松事件计数可能造成的假阳性，与严格 receipt-actor-run 见证对比。
4. 删除fork分支/修改关键证据边：应同时改变合法性/执行事件与规范签名，不能只改变文本。

## 入池阈值

本轮每项测评至少2对 R3 `DEV_ACCEPTED`，且至少2个新的历史未覆盖、真实执行的工作流家族（分别独立统计），全部通过原有配对硬门+Oracle+Replay+历史去重+研发审核。**不为了达标改阈值**。如果发现有两个新家族但某个没有成功入池，则仍不算最终家族验收达标。
