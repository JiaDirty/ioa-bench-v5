# 02 · 可组合、可执行的业务 DAG：最小可行架构

## 设计核心

R2 最大进步是**模型声明必须被程序真正消费**；最大剩余障碍是**程序预设了整个流程**。R3 不再把完整行业流程作为静态常量，而是只登记**原子可执行能力和约束**，把组合关系交给生成器。模型不是生成任意代码，而是提出一个**基于能力模块的计划**；编译器负责合法化为真实工具/角色/事件/证据，并产生双臂同形业务基底。需分清：

- **语义层**：领域工作/任务目标，业务角色、资产、动作、可见材料、依赖和预期产物；不同领域的合理业务流程差别。
- **机制层**：IoA 套件的原有风险构念/干预、暴露、机会、违规/恢复事实。程序拥有 CONTROL/RISK 的真值及单槽区别；不可由模型自由更换。
- **实例层**：组织/病例/账单等名称与数据值，独立于抽象工作流家族。

建议最小新增 2 模块即可（名字仅建议，按现有项目风格定）：`workflow_modules.py`（可用原子节点目录）和 `workflow_compiler.py`（规划、约束、绑定、动态 runtime 投影），**改造原有** `business_binding.py`、`mechanism_ir.py`、`dynamic/business_tools.py`、`tree_factory.py`。不要重建 `ScenarioBranchTree`、ToolSpec 引擎或评分器。

## 最小 typed WorkflowModule 目录

目录注册的是**单个动作的可执行语义**，非写死的“步骤1→步骤2→步骤3”全套模板。例如：

```
module_id; version; industry; capability(read/verify/commit/notify/route/attest);
input_schema; output_schema; tool_factory/tool_id; role_eligibility;
requires_facts; produces_facts; evidence_consumed; evidence_emitted;
visibility_policy; deterministic_receipt_schema; precondition_error_code;
side_effects; allowed_suite_targets; oracle_visibility=public_only
```

目录可以沿用 R2 两个行业的工具语义，并在它们真正有用时加少量分支/交汇/二次核验能力（例如缺货时先补货再复核；多来源清算资料会合后确认）。增加新模块的最小证明是某种新 `WorkflowPlan` 可以消费它；否则不增加。严禁把 `MODEL_PROPOSED` 字段直接决定受测 agent 的 oracle。

## WorkflowPlan (模型建议部分)

建议 JSON 输出契约（以下仅示例，真实 schema 应包含 `additionalProperties:false`、最大 DAG 节点数量及允许值）：

```json
{
  "version": "ioabench.v5.workflow-plan/1.0.0",
  "industry": "industry.medicine_supply",
  "goal": "库存核对后根据真实批次核验结果完成补货确认",
  "stages": [
    {"id":"s1","module":"medicine.stock.read","role":"ward","inputs":{"lot_id":"lot_A"}},
    {"id":"s2","module":"medicine.lot.verify","role":"pharmacy","inputs":{"stock_receipt":"s1.receipt"}},
    {"id":"s3","module":"medicine.supply.confirm","role":"supplier","inputs":{"verification":"s2.receipt"}},
    {"id":"s4","module":"medicine.postcheck","role":"ward","inputs":{"confirmation":"s3.receipt"}}
  ],
  "edges": [
    {"from":"s1","to":"s2","type":"evidence"},
    {"from":"s2","to":"s3","type":"enables"},
    {"from":"s3","to":"s4","type":"evidence"}
  ],
  "branches": [],
  "public_narrative": "..."
}
```

说明：`lot_A` 等业务实例由程序绑定合法值，模型可建议但不能注入不可验证的真实权威；`s1.receipt` 是**类型化引用**，由 runtime 真实事件和回执绑定，不是模型随手编造的字符串。以上示例四段链可作为最小测试，但要在真实模型提议中进一步出现**原硬编码列表没有的、却由模块目录合法导出的新 DAG**；不要把这个示例固定进生产模板当做“完成自主生成”。

## 基础组合语法

R3 优先实现以下四种节点连接语义，按源代码可承受度实施：

1. `requires` / `happens_before`：先决事件必须真实出现且相应证据属于此 run；顺序按动作序列，不能仅用粗粒度 turn。
2. `fork + join`：两个合法事实源分别执行，汇合节点只在**两个都已完成**时可执行；故障注入缺一分支时 join 必须拒绝。
3. `conditional`：基于已有**程序可确定**的业务状态走不同合法子路；分支选择要留原始判定事实与不可见真值隔离，不能用 SUT 事后说法决定。
4. `handoff`：前一角色的输出按授权范围变成下一角色可见业务材料；非授权角色看不到，无假回执。

暂不做循环 DSL、任意第三方网络访问或用户可生成工具脚本。这不是保守，而是防止把三项本可完成的目标拖进造虚拟机的大工程。若实际需求必须循环，先建 bounded state-machine 子构件再明确扩容。

## 强制消费路径与编译后权威

```
FrozenSuiteTarget + TreeSelection + CapabilityCatalog
            ↓
    AI WorkflowPlan candidate (MODEL_PROPOSED; no risk truth)
            ↓
  normalize → typecheck → capability/grant/evidence/DAG validation
            ↓
   WorkflowCompiler → CompiledBusinessPlan (PROGRAM_VALIDATE)
            ↓
       BusinessBinding (now driven by compiled plan)
            ↓
MechanismIR + truth ownership + explicit BusinessBinding endpoints
            ↓
validate FULL IR + binding consistency → suite adapter/compiler (unchanged scoring)
            ↓
ToolSpecs + staged actor schedule + attachments from compiled plan (NOT BUSINESS_FLOW lookup)
            ↓
Reference CONTROL/RISK executes → per-action receipt/event witness → strict Replay
```

**不允许的旁路**：先生成 `BLUEPRINT` 然后只把 `WorkflowPlan` 作为附属旁证；模型提议新 DAG 但 `dynamic/business_tools.py::_flow` 仍从 `BUSINESS_FLOW[root]` 反查完整静态三段；通过一个演示脚本却不接真正 `run_task`；未经编译端批准自动给受测 agent 无关高权限；重复用最终 audit verdict 自我证明事实。

## 什么叫“新结构”，什么不算

- 算：新 `read→verify` 串联升级为 `read→(verify_A,verify_B)→join→commit`，实际出现两份先行证据、join 屏障，CONTROL/RISK 两臂有一致业务 DAG；另有合法 `read→conditional→route→audit` 且条件对运行时真实生效。
- 不算：将 `ward` 改名 `merchant`，把 T331 “chain” 改字符串名称，在 `WorkflowPlan` 里声明 fork/join 但 trace 只有一条事件，把 `3` 个 stage 变成3个聊天段落，或者老字段自由组合但不改变可执行拓扑。

使用结构归一：以**标签化 DAG 同构**对业务角色/能力/依赖类型/数据可见边做 canonicalization。可以先对单轮≤12节点用稳定的图哈希 + 明确拓扑同构验证，避免爆炸搜索；输出 `normalized_workflow_graph`、`workflow_family_hash` 与与历史差异证据。和原有 `executable_structure_signature`（suite 机制拓扑）并列报告，不要混成一个分数。

## 弱监督的质量反馈，而非降门槛修数据

对每个候选：

`MODEL_PROPOSED → TYPECHECK → COMPILE → CONTROL/RISK EXECUTE → WITNESS → HARD GATES → DEDUP → DEV REVIEW`。

失败要产出短 `failure_feedback`（错误代码、出问题 stage/edge、允许的替代 module/role/evidence，不泄漏 oracle），下一次**新的候选 ID** 可让模型提出替代 DAG；不要无限修补同一证据目录。最多根据确定性问题做局部修复，避免错误数据被模型“说服式解释”为正确。

## 评估消融（实现不可绕过的证明）

同一 seed、目标格、机制控制参数：

- 移除业务模块/切换 join 依赖：真实 trace 和 normalized DAG 必须相应改变，否则检测为声明未消费。
- 合法 root 切换：工具、证据、角色应按行业改变，但**纯语义换皮的抽象拓扑哈希不应改变**。
- 欠授权/证据损坏/循环依赖/不匹配 module：应在 static/compile 或 tool runtime 失败，不能通过双臂硬门。
- 同一个 WorkflowPlan 下 CONTROL/RISK **只改变允许的机制 slot**；新增行业层变更应同步两臂且不接触 oracle/scorer。

## 面向18项的接口边界

R3 的模块编译器对 suite 暴露 `SuiteWorkflowCapabilities`：受测 actor 列表、确定性环境角色能力、支持的工具暴露模式、事件消费/前置点、是否能承载业务 DAG、oracle 不变量。对于尚未适配的15项返回 `UNSUPPORTED_WITH_REASON`（不暗示已自动支持），不能默默借 T321 的编译路径跑其它 suite。`09` 文档定义推广顺序。
