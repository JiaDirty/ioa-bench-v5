# Codex Goal｜IoA-Bench v5 · R3 收口、质量证明与稳定试跑

**适用仓库**：`D:\Project\ioa_codex_spec`  
**执行器**：新 Codex 会话，允许直接编辑和运行命令；不依赖 ZCode 的状态。  
**基线**：以启动时本机**最新工作区**（含未提交修改）为准。`2026-10-25` 源码审阅包仅是已知基线，**不是**让你覆盖本机文件。  
**数据生成/研发审核模型**：AIHubMix `deepseek-v4.1-flash-1017`，国内优先 `https://api.inferera.com/v1`。

## 唯一交付目标

**接着现有 R3 做完工作，不另起 R4、不重造框架。** 修复当前生成链的业务见证漏执行及其可信性缺口；以真实运行和历史比对严格确认可组合工作流的新颖性；补齐 T321/T331/T362 各≥2 对本轮 R3 `DEV_ACCEPTED`，且**各≥2种历史未覆盖、执行确证、非同构的新工作流家族**；把已冻结的18个匹配任务机会的两条路线完成为公平且可追溯的 A/B、加离线消融；最终在**同一个最终源码版本**上重跑全量测试、Strict Replay、历史保护、完成本地提交和可独立复核的 SOURCE/EVIDENCE 交付。随后形成其余15项推广的可执行优先级，而**不在本轮盲目改完15项**。

目标是高质量、丰富、真正多样且稳定的**自动数据生成闭环**，不是堆 Token、堆文件、堆“PASS”文字。

## 事实起点：先核验，再动手（只需一次）

已知 `2026-10-25` 工作区快照：Git HEAD `7e35bc1591d970c4fd66765008000d4e0b637615`，当时 tracked tree **有未提交修改**；R3 记录 T321 5 对、T331 1 对、T362 1 对 `DEV_ACCEPTED`；其中部分工作流哈希复用，**不等于每对是一个家族**。R1+R2 的 17 对是历史，不能计为本轮新增。已有 1949 测试的历史 JUnit，但不是新 HEAD 的完成证据。上述数据来自旧快照，本机可能更新。`WORKSPACE_STATUS_20261025.md`、真实 run、账本、最新 Git 状态为权威。

关键原代码落点（实际路径若已改，以本地为准）：

- `src/ioabench/v5/ai_generation/tree_factory.py`：`run_task()` 的 `business_witnesses` 目前嵌套在 `if assertion_ids:`，断言为空可能跳过。先写红测，**立即修复**。
- `src/ioabench/v5/ai_generation/compiler_capabilities.py`：`business_witnesses()` / `_witness_plan()`，追踪每个 run/arm/policy/action seq、receipt、权限、事件、前置引用。检查是否只在某条 legacy 分支有效。
- `workflow_modules.py` / `workflow_compiler.py` / `business_binding.py` / `mechanism_ir.py` / 3个 suite 编译器和动态 slice：只针对真实未支持的合法结构扩展；保持 `Tree → WorkflowPlan → BusinessBinding → Mechanism IR → Compiler → Runtime` **不可绕过**。
- `scripts/v5/tf_r3_pilot.py`、`tf_r3_pool_index.py`、`tf_r3_ablation.py`、`tf_r3_history_protection.py`、`tf_r3_finalize.py`：优先修正/复用，不造第二套 runner。
- `src/ioabench/v5/ai_generation/aihubmix_study.py`：旧源码快照仍写 `https://aihubmix.com/v1`；用户已在本机改为 `https://api.inferera.com/v1`。**先核实本机改动并保留**，保证 Adapter、policy、catalog/preflight、记录使用一致域名。

## 交付通过条件 C0–C7（全部由真实文件证明）

**C0 工作区接管**：记录 Git HEAD+dirty+现有变动、R3 run 与请求账本、已经入池的 ID、三项缺口。先保护现有用户修改，不用 `git reset --hard`、`git clean -fdx`、无差别 checkout。所有新付费实验用新 request ID；保留旧请求的终态，绝不重复发起未决 POST。

**C1 业务硬门修复**：所有组合工作流（包括 `assertions=[]`）必须实际运行 `business_witnesses()`，任何关键业务见证缺失/失败不得标 `DEV_ENGINEERING_VALID` 或 `DEV_ACCEPTED`。从真实 trace 验证跨阶段 receipt/actor/role/grant/visibility/因果事件顺序。用反例证明：空断言、跨 trace 串证、越权、乱序、伪回执、失败动作假成功至少六类全拒绝；正确参考执行通过。不要让验证器自己制造成功事实。

**C2 新颖性真实可信**：至少三层独立报告：实例去重（原有 case/history）、执行机制签名、工作流**类型化图同构**。归一化忽略名称、ID、组织词，保留阶段能力类型、边类型、角色职责、工具/证据可见性、条件分支和可观察执行差异；不能只凭 `sha256(plan)` 说新家族。每条入池数据必须提供相对 R1/R2 封存基线和本轮先前数据的匹配/非匹配证据，以及执行 trace 链接。

**C3 三试点真正达标**：T321/T331/T362 各≥2对属于 **R3** 的、全新 ID 的 `DEV_ACCEPTED` 配对，且每套 ≥2 个经 C2 判定为历史未覆盖的**执行过**的家族。充分复用当前已合格候选；只补缺口，不能为了凑配额降低科学或工程门槛。T361–363 保持 `SIMULATION_ONLY`；同一 DeepSeek high/max 双档只算研发审核。

**C4 模型调用质量**：`deepseek-v4.1-flash-1017` 使用 `https://api.inferera.com/v1`（若本机确有更新，以本地合同为准）；不设美元预算上限、不以省钱降低模型思考/上下文/输出。原生上下文可用约1M，公开最大输出约393K；按接口真实支持且任务必要选 131072、262144、393216 `max_tokens`，不能锁死16K/32K。默认 high，复杂 max，SSE 严格收流至终态 + 验 JSON/usage/model identity。上限被接受不等于实际生成了该长度。401/403、终态未知按事实隔离；**不要重复发送旧未决请求**。保留全部成功/失败分母和 usage，不以费用作停止理由。

**C5 R3 冻结比较**：沿用已冻结的同题任务/种子/行业/难度/机制条件与同模型，至少每套6个匹配机会，分别跑 baseline=`tree_ir_runtime_v2` 和 treatment=`compositional_r3`。区分**首次尝试**与“新ID修复/补跑”，不能混在一起算公平 A/B；历史未决不重发。交付两路线的：工程有效率、审核入池率、独立图家族数/有效候选、平均请求数、耗时/截断/网络故障和实际分母。完成已有 Tree、Composition、Witness 消融；实验规模有限，不写统计显著。

**C6 最终工程证据**：所有相关 R3、v5、m1 测试在最终一致版本上跑完、记录真实 JUnit；Strict Replay 对本轮有效样本重算；历史保护必须检查实物和哈希（`files_checked>0` 或明确标为未完全可核验，不能空计数 `PASS`）；零网络恢复核验不应真的发请求。保留原来的18项构念、CONTROL/RISK单点干预、Oracle隔离、评分真值和硬门。

**C7 完成交接**：本地合理提交当前任务代码（不提交用户无关修改、不强推 GitHub）；一份 `R3_CLOSURE_REPORT.md`、`R3_GOAL_STATUS.json`、`R3_DEV_POOL_INDEX.jsonl`、`WORKFLOW_NOVELTY_AUDIT.json`、`R3_AB_RESULTS.csv`、`R3_AB_REPORT.md`、`R3_ABLATION.json`、失败漏斗/请求账本/版本绑定、SOURCE/EVIDENCE两个ZIP、逐文件SHA清单与验证。将源码、任务清单、实验 run ID、commit、测试、证据互相绑定，向审查者说明缺失或局部证据。

## 工作方式：像高效工程师，而不是流程机器人

1. **Inspect → Reproduce → Edit → Test → Run → Verify → Commit**。先看现有代码，第一小时优先解决一个真问题并跑过测试，而不是写长篇路线图。
2. 每次只改直接相关的实现；复用已有工具、队列、schema、runner；**不要**为简单变量搭新抽象、给每个异常再套三层回退、创建影子工厂或十套重复日志。可以并行读代码/跑互不冲突的只读任务，但不要并发改同一文件/写同一冻结 run。
3. 遇到普通代码/格式/审核契约问题，自己定位并修，定点测试后继续；只有缺少真实授权、无法解析的外部账户故障、历史库确实不可获得等不可解决边界才汇报阻塞。
4. 不将输出 Token 设小来规避问题；也不要求所有请求真的输出384K。使用大容量+完整SSE终态+任务切分，减少废弃候选，而不是靠无限重试。
5. 不把静态设计文本、AI审核赞同、模型声明、多次提交、未执行测试或历史绿色 JUnit 冒充实际完成。
6. **完成标准是 C0–C7 有对应证据，不是把任务列表勾满。** 有真实外部不可解阻塞标 `PARTIAL/BLOCKED` 并交付现有成果；不得假 PASS。

## 执行顺序

按 `02_EXECUTION_QUEUE.md` 的 S0→S5：接管 → 业务硬门 → 图新颖性 → 只补试点缺口 → 冻结比较/消融 → 最终回归与交接。参照 `03_MODEL_AND_ENDPOINT.md`、`04_NOVELTY_AND_WITNESS.md`、`05_EXPERIMENT_PROTOCOL.md`、`06_FINAL_ACCEPTANCE.md`。全过程不要请求我逐步批准普通实现细节。
