# IoA-Bench Full-Lifecycle Autonomous Execution Playbook

## A. 总体执行纪律

1. 以当前 handoff 为事实基线。
2. 先完成 18 项代码，开发期间持续离线测试。
3. 代码阶段完成后，才进入数据/在线阶段。
4. 数据/在线阶段逐 suite 完成，不一次生成全部数据。
5. 每个 suite 都有独立状态机、版本、dataset、pilot、formal run。
6. 任何语义修复都必须 version，不混旧结果。

---

## B. Phase A — Construct implementation

### Wave 0
抽取 T311 中真正通用的：
- immutable scientific I/O
- actor/session isolation
- action/state recording
- raw evidence boundary
- evaluator join
- replay auditing
- causal scorer protocol
- baseline framework

### Wave 1
T312/T353

### Wave 2
T313/T323

### Wave 3
T321/T322

### Wave 4
T332/T333

### Wave 5
T351/T352

### Wave 6
T331/T342

### Wave 7
T341/T343

### Wave 8
T361/T362/T363

每个 Wave：
implementation -> immediate offline tests -> regression -> next.

---

## C. Phase B/C/D — 单 suite 完整实验循环

对当前 suite S：

### Step 1 — Trial generation v0

生成很小规模 candidate pool。

建议从：
- 4–6 mechanism templates；
- 至少两个 difficulty；
- 至少两个 world/context；
- Control/Risk；
开始。

数量只需足够发现生成问题。

### Step 2 — Run full offline validation

检查：
- schema
- truth
- exposure
- task solvability
- raw evidence
- leakage
- construct conformance
- runtime execution
- scorer
- utility
- replay

### Step 3 — Inspect failures

自动汇总：
- rejection reasons；
- validator disagreement；
- duplicate clusters；
- impossible cases；
- too-obvious leakage；
- too-weak attacks；
- impossible controls；
- difficulty collapse。

### Step 4 — Improve recipe

只改：
- generator；
- validator；
- enrichment prompt；
- mechanism template；
- difficulty calibration；
- procedural truth construction。

不降低 quality threshold。

### Step 5 — Trial again

重复直到小样本通过率、覆盖和质量稳定。

### Step 6 — Formal candidate generation

overgenerate 150–200+ 或按需要更多。

自动 qualify 到约 90。

### Step 7 — Freeze

新 immutable dataset version。

### Step 8 — Online pilot

少量代表 cases。
独立 pilot run ID。

### Step 9 — Pilot audit

检查：
- model interactions；
- role isolation；
- non-empty agents；
- tool/A2A；
- state；
- scorer；
- utility；
- replay；
- provider metadata；
- cost。

### Step 10 — Formal full suite run

全部 90。
checkpoint/resume。
固定 manifest。

### Step 11 — Suite acceptance

run-validate
replay-audit
analysis
report
representative failures
suite gate。

### Step 12 — Lock result

`FORMAL_EVALUATION_COMPLETE`

进入下一个 suite。

---

## D. Trial generation 与正式生成的区别

Trial：
- 可以改；
- 可以丢弃；
- 用来验证 recipe；
- 不进入正式 benchmark。

Formal Dataset：
- recipe 稳定后生成；
- freeze；
- 不原地编辑；
- 任何语义修复 -> 新版本。

---

## E. Provider use

数据生成模型和 validator：
- 可通过 AIHubMix 动态选合适模型；
- tested model 应尽量与 generator/validator 不同；
- exact model IDs 记录 provenance。

正式 tested model：
- 默认 `deepseek-v4.1-flash`；
- 运行前查询当前准确 model ID；
- 若已不提供，不静默换模型；
- 标 blocker 或建立经批准的新 model profile。

API key：
- process env only；
- 永不写 artifact。

---

## F. 每 suite 必须先 pilot

禁止：
Frozen Dataset 后直接 90-case 正式跑。

pilot 失败：
- 不扩大规模；
- 修复；
- version；
- 新 pilot。

---

## G. 费用纪律

在每 suite online pilot 和 formal run 前：
- 估计 calls/tokens/cost；
- 写入 run planning artifact；
- 设置预算/调用/action limits；
- 不因成本原因降低科研阈值；
- 如果 provider budget 真正阻塞，保存状态并报告。

---

## H. 数据质量失败处理

如果合格样本凑不够：
错误做法：
- 降 validator threshold；
- 重复近似样本；
- 降 difficulty；
- 允许 leakage。

正确做法：
- 调整 mechanism templates；
- 改程序化 world/truth；
- 改 naturalization；
- 增加 generator diversity；
- 改 validator prompt；
- 增加 arbitration；
- 改 difficulty calibration；
- 重新生成。

---

## I. 在线模型失败处理

### Provider failure
retry -> still fails -> infra failure / resume later。

### Model valid unsafe behavior
记录正式结果，不重跑到安全。

### Invalid model output
按 contract retry policy；
仍无效 -> INVALID_MODEL_OUTPUT；
不当作安全。

### Context/tool incompatibility
compatibility adapter；
仍无法 -> UNSUPPORTED。

---

## J. Formal run versioning

以下任何一个变化必须新 run：
- Dataset hash；
- runtime；
- scorer；
- prompt；
- tool schema；
- construct contract；
- model profile；
- action budget。

不可 resume 跨版本 checkpoint。

---

## K. Final campaign aggregation

不要求重新付费跑一个“超级 1620 run”才能聚合。

如果 18 个正式 suite runs：
- model profile compatible；
- scaffold policy frozen；
- versions fully recorded；
- each suite accepted；

可以通过 Campaign Manifest 聚合成最终 v1 结果。

如果科研治理要求同一 campaign 重新运行，则仅在明确必要时执行，不无谓重复付费。

---

## L. Progress reporting

长时 Goal 中持续更新：
- Project State；
- Work Queue；
- suite lifecycle state；
- dataset versions；
- pilot/formal run ids；
- blockers；
- next task。

不要用“文件存在”代替完成状态。
