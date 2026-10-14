# Current State Audit Baseline — 2026-09-27

本文件是基于最新源码包 `IoA-Bench-source-20260927.zip` 与历史 Codex Goal 会话做出的外部审查基线。Codex 开始工作后仍必须以**当前工作区真实源码和运行证据**复核，不得机械相信本文件。

## 1. 当前总体状态

当前工程已经完成从旧 universal `read/query/complete` 方案向多个 construct-specific runtime 的架构转型。

现有主要运行时：

- T311：`src/ioabench/runtime/t311_construct.py`
- T312/T353：`discovery_selection.py`
- T313/T323：`delegation_provenance.py`
- T321/T322：`protocol_state_machine.py`
- T331/T342：`network_propagation.py`
- T332/T333：`disclosure_inference.py`
- T341/T343：`deliberation_norm.py`
- T351/T352：`incentive_reputation.py`
- T361/T362/T363：`human_agency_simulation.py`

因此，旧 r5 的 universal event-renaming 问题在新的离线 Runtime 层面已经大幅整改。

但是：

**“有专用 Runtime + baseline 能区分”不能直接等于“construct-valid 科研验收完成”。**

## 2. 当前治理状态过于乐观

`state/PROJECT_STATE.yaml` 当前包含：

- `status: construct_offline_runtime_gate_passed_pending_r6_entry`
- `final_18_suite_construct_acceptance: false`
- `all_18_offline_construct_slice: completed_offline_gate_passed_pending_cross_platform_and_independent_review`
- `formal_construct_valid_run: not_started`

`state/WORK_QUEUE.yaml` 当前包含：

- `CIG-OFFLINE-GATE: done`
- `CIG-REST-16: done`
- `CIG-R6-ENTRY: blocked`

这些状态不能作为新的 Phase A 最终验收依据。需要创建新的 V2 acceptance tasks，对实际 Contract obligations 重新检查。

## 3. 正式执行链仍未完成迁移

当前 `src/ioabench/cli.py::_run_all()` 仍：

- import `execute_mock_case`
- 对 non-mock formal execution 主动 block
- 正常路径仍调用 legacy `execute_mock_case`

因此：

**新版 construct-specific runtimes 尚未统一接入正式 benchmark runner。**

T311 已有独立 `scripts/run_t311_suite.py`，可作为新 formal dispatcher 的参考，但不能以单项脚本代替 18 项统一 formal path。

## 4. 生成器的 mechanism / difficulty 需要重新证明为因果有效

当前 T312–T363 生成器必须增加自动结构测试，证明：

- `mechanism_index` 改变时，实际 `sut_payload` / Oracle Ground Truth / state topology / risk path 有实质变化，而不只是 `mechanism_id` 标签变化。
- `difficulty` 改变时，必须改变任务复杂度、证据冲突、交互深度、干扰项、验证成本、传播深度或其它 construct-relevant difficulty factor，而不只是 metadata。

在该测试建立并通过之前，不得认为 5 mechanisms × 3 difficulty 已真正实现。

T311 仍是这方面的参考实现。

## 5. 高复杂 suite 的重点缺口

### T313
真实 delegation runtime 已存在，但需确认并补齐：
`scope / resource / audience / TTL / parent` 五类 drift，不应主要集中于 scope/parent。

### T331
已有多 Agent 和传播图，但必须进一步证明：
- 每一跳由接收节点自己的 tested session 决定是否继续传播；
- 真实 downstream business state 被影响；
- correction 真实沿边传播；
- scorer 使用 actual affected nodes / depth / containment，而不是简化 forward target。

### T341
已有多个 tested roles，但必须确保：
- private evidence 真正按角色隔离；
- 多轮讨论；
- individual votes；
- minority evidence survival；
- majority/reputation pressure 可操作。

所有 Agent 初始看到同一个完整 visible payload 不满足 private-evidence construct。

### T342
需完整证明：
- forward / quote / endorse 语义分离；
- source provenance retention；
- reach/depth；
- verification；
- correction/retraction 到达真实 recipient。

### T352
当前 multi-round 结构不等于 reputation feedback loop。
必须做到：
`selection -> execution quality -> feedback -> reputation update -> next ranking/selection`
并从实际 history 计算 concentration。

### T353
需要真正 paired：
同一 Ground Truth / candidate set 下运行 honest Router 与 manipulated Router，再比较 selection / utility delta，而不是用单次 manipulated outcome 代替 counterfactual。

### T361
Contract 要求：
- tested advisor
- tested reviewer
- scripted deterministic synthetic persona

synthetic persona 不应由 tested model 直接扮演。

### T362
Contract 要求：
- 至少 3 tested discussion roles
- scripted synthetic persona
- discussion graph
- feed rank
- exposure
- persona shift

必须有真实 feed/exposure 到 persona 的过程。

### T363
Contract 要求：
- tested assistant
- tested reviewer
- scripted synthetic persona
- baseline -> assistance -> withdrawal
- matched or equivalent tasks
- unaided capability change / recovery curve

不能仅靠阶段标签和同一个 model persona 动作推断 agency weakening。

## 6. T311 数据/在线资产当前定位

历史会话中已出现：

- T311 small trial generation
- exploratory online pilot
- T311 `2.0.0` freeze
- T311 dedicated suite runner

但这些工作发生在新的 18-suite final construct acceptance 真正关闭之前。

因此本 Goal 默认将：

- T311 `2.0.0`：`PROVISIONAL_FROZEN_CANDIDATE`
- 已有 online pilot：`EXPLORATORY_DEVELOPMENT_PILOT`

保留、不删除、不覆盖。

只有在新 Phase A Gate 通过后，再审计其 provenance 和 recipe。若完全满足当前正式质量门，可晋升使用；否则发布新的 Dataset version，绝不原地修改。

## 7. 当前正确阶段

当前应视为：

**Phase A reopened — construct implementation and formal execution integration not yet scientifically closed.**

只有新的 `PHASE_A_V2_FINAL_ACCEPTANCE` 通过后，才进入正式 Phase B 数据/在线 campaign。
