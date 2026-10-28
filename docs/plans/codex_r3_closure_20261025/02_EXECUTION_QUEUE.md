# 02｜Codex 执行队列：六步直接完成 R3

**原则**：每一阶段产出代码/测试/结果，不要反复写“准备做什么”。执行日志可以简短；真进展由测试与入池证据表达。允许并行只读检索，禁止并行写同一运行目录、同一账本、同一冻结文件。

## S0｜接管现场（快速完成，不重建）

检查 `git status` / diff、`AGENTS.md`、最新 run 证据、R3池、T331/T362缺口和预注册A/B是否已跑。检查 API base URL 当前值，确保用户新修改为 `api.inferera.com/v1` 贯穿 Adapter + Study + Policy + Runner + 证据记录。将结果写成简短 `R3_RESUME_STATE.json`（HEAD、dirty、run、入池ID、未终态ID、缺失项、API配置可用性）。不要大面积扫描/复制20万历史文件，不做新脚手架。马上进入S1。

可用检查（根据Windows Shell适配）：

```powershell
cd D:\Project\ioa_codex_spec
git status --short
git rev-parse HEAD
rg 'BASE_URL|base_url|api.inferera.com|aihubmix.com/v1' src/ioabench/v5/ai_generation/aihubmix_study.py scripts/v5/tf_r3_pilot.py src/ioabench/models/aihubmix.py
```

## S1｜业务见证必经（最高优先级，先红后绿）

**必改**：`src/ioabench/v5/ai_generation/tree_factory.py:run_task()` 的 `assertion_ids` 空值不应屏蔽 `business_witnesses`。把 reference run 收集移动到需要它们的公共路径；只对机制断言按需调用 `execution_witnesses`，但对三个 route 的组合业务候选强制调用业务见证并保存结果。成功的业务见证凭 trace 不凭设计文本，失败禁止 `DEV_ENGINEERING_VALID`。

- 红测：用真实 `run_task(... route='compositional_r3', assertions=[])`、本地 FakeStudy/已存合法 proposal，不发模型请求，查业务见证是否落盘并影响准入。
- 扩负例：跨trace假收据、工具失败但 event 成功、同一 action 被复用完成两个stage、提前证据释放、角色无grant、可见性不足、错误 arm/policy、无接收者的事件等；至少六大类验证失败。
- 保留已有 `workflow_compiler.py`、`_witness_plan` 与旧流程兼容；不引入第二套流水线。
- 完成条件：修复测试 green、`tests/v5/test_workflow_composition_r3.py` 及相关 R2 兼容测试 green、原有有效参考案例不被误拒。

## S2｜图新颖性/结构多样性（真正关键的第二瓶颈）

**优先修改**：`scripts/v5/tf_r3_pool_index.py` 和已有 `BusinessBinding.canonical_workflow_hash` 的规范化投影。使用现有模块标签、能力类型、依赖边、role-tool-evidence 关系，计算**类型化图同构或等价的可核证规范签名**。不要无条件依赖 plan 序列顺序或stage ID；如果 hash canonicalization 存在标签碰撞，精确比较同构，保留 witness 映射。

逐对区分：`case-level duplicate`、`executable-mechanism duplicate`、`workflow-graph isomorphism duplicate`、`new-family-vs-frozen-history`、`new-instance-within-known-family`。把 R1/R2 封存可比实例导入索引，说明旧格式不含 DAG 详细信息时只能达到何种证据级别，不能臆测不存在。图同构与执行签名由程序计算；人工语言评价只提供附加解释。

必须有反事实测试：同图不同节点 ID、交换独立阶段顺序、行业同构工具等价改名、同拓扑不同因果证据边、条件分支实际消失、新业务动作增加且被执行。确保前四类按预期去重/区分，后两类真实执行可见。

**交付**：`WORKFLOW_NOVELTY_AUDIT.json`、`STRUCTURE_FAMILY_INDEX.jsonl`、`NOVELTY_COUNTEREXAMPLES.json`，全都含 candidate、run、来源、hash/signature、执行证据索引。

## S3｜只补缺口的真实生成/研发审核

先在现有R3的7对和最新本地入池记录里筛选**真正合格且家族新颖**的；如 T321 已有两种新家族则无需再浪费时间做T321重复样本。**优先补 T331、T362 的数量+家族缺口**，必要时补T321的合法新家族。

生成前本地先试：目标计划是否通过 WorkflowPlan Schema/目录、IR、Compiler 能力预检、严格 BUSINESS_WITNESS 和参考策略。失败先修编译或模块使用设计，再发线上模型。AI只负责需要语义创造的 WorkflowPlan/提案和研发审核；确定事实用程序。使用当前 `scripts/v5/tf_r3_pilot.py` 的 frozen task set，优先复用合法的原 task 而不是无限制造全新 seed；旧未决请求不重发，新任务/修复必须新ID。

每个候选依序落 `WORKFLOW_PLAN_MODEL_DOC.json`、`COMPILED_WORKFLOW.json`、`MECHANISM_IR.json`、`IR_CONSUMPTION_TRACE.jsonl`、`BUSINESS_WITNESSES.jsonl`、`REFERENCE_RESULTS.json`、`HARD_GATE.json`、`REPLAY.json`、`HISTORY_DEDUP.json`、`DEV_AUDIT` 和 `ADMISSION.json`，实际路径可按现有命名映射。不要为写这些证据再造全新 wrapper。

成功标准**每套≥2对R3新入池，同时≥2个历史未覆盖、执行证明的新家族**，优先质量、多样性，而不是总候选数；所有失败和拒绝保留原始分母，不能挑成功样本。

## S4｜冻结 A/B + 消融收尾

使用 `TASK_SET_FROZEN_R3.json`、`R3_AB_PREREGISTRATION.json`，检查原本18 matched opportunities 在两条 route 中各有哪些原始第一轮。已有终态有效记录一律复用；中途更改的协议作为探索性补充而非重算冻结首轮。对**确实尚未执行、未发起过**的机会按原合同补跑；对 UNKNOWN 不重发原请求。完成 `R3_AB_RESULTS.csv` 和 `R3_AB_REPORT.md`，用 task_id + route + first_attempt_id 锚定公平比较。

运行 `scripts/v5/tf_r3_ablation.py` 的现有消融，有需要才修；将 Tree-Off、Composition-Off、Witness-Off、删分支/改因果边的结果与真实执行 trace 对齐。不需要发表级统计显著性，报告描述统计、置信区间/不确定性即可，不能用修复后成绩偷换 first-pass。

## S5｜一次完整回归 + 交付（收口）

先补测试覆盖，然后串行跑全量 v5/m1、新的见证与新颖性测试和 Strict Replay。在最终源码版本下出新的JUnit，不用2026-10-25历史1949通过充数。做有意义的原文件 SHA 保护检查（可复用已有保护基线与范围，必要时只新增受影响范围校验，不能 `files_checked=0` 还写PASS）。

运行/修复既有 `tf_r3_pool_index.py`、`tf_r3_history_protection.py`、`tf_r3_finalize.py`，最后生成当前工作区与Git状态绑定的 SOURCE/EVIDENCE 两个zip和校验manifest；合规地提交本轮代码至本地分支，**不能把用户之前8个未提交修改吞掉或丢掉**。报告 `R3_GOAL_STATUS.json` 中C0–C7逐项PASS/PARTIAL/FAIL的真实证据路径。

如真的因外部账号/网关持续故障不能完成付费审核，不要因没有钱而停，不要掩盖；交付已经完成的代码与离线成果并标`PARTIAL/BLOCKED`。

## 允许但不强制的提效

- 以 `rg` 搜索调用链，优先测试局部变更，直到关键路径green才跑全套；避免每改一行跑2000项。
- 相互独立的源码定位和只读取证可并行；同一账本、模型run、Git 提交不能并发写。
- 长上下文无需人为限制；按实际局部任务选相关文件提供模型，而不是无谓拼几十万Token历史数据。
- 先修最痛的漏洞再开付费生成；让每个花费的模型调用拥有明确要解决的结构缺口。
