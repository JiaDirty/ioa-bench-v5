# 可直接发给当前 ZCode 的继续执行 Prompt

继续现有 `D:\Project\ioa_codex_spec` 的唯一 IoA-Bench v5 Goal。不是新 Goal，不升级 v6，不重做已有 M0–M4、M6–M7 动态切片，不启动未经授权的大规模数据生成、确认性 Pilot 或正式 Campaign。

我基于你截至 2026-10-11 17:34 的工作会话与最新上传的源码包做了独立代码审查。现将补充执行契约放在：
`NightGoalDoc\IoA-Bench-v5-Dynamic-World-Goal-20261011\08_POST_AUDIT_AMENDMENT_20261011\`

请先读取本目录全部文档：尤其 `01_GOAL_ACCEPTANCE_AMENDMENT.md`、`02_PRIORITIZED_REMEDIATION_QUEUE.md`、`03_P0_DEFECTS_AND_NEGATIVE_CONTROLS.md`、`04_GLOBAL_EXECUTION_AND_MONITOR_CONTRACT.md`、`05_DATA_FACTORY_AND_DIVERSITY_CONTRACT.md`、`07_COMPLETION_EVIDENCE_MATRIX.md` 和 `09_TASK_OVERLAY.yaml`。它们是当前长期 Goal 的增量质量门槛，若与已批准科学契约冲突，保持原科学契约并报告 PI 决策，而不是自行修改。

请先在 Windows 当前实际工作树复现已发现的边界问题：`authority.py/engine.py` 的 audience/at_turn 未传导致限制可能被绕过；`monitor.ledger_integrity` 把同名工具动作压为集合、无法一对一核验事件；`evaluate_timing` 用不同序号空间比较证据和动作；`dynamic/signature.py` 中元数据、结构判定与 hash 不一致；`build_dynamic_dataset.py` 不是真正的跨批硬性去重；原 `runner.run_case` 不能直接运行动态 slice，也未统一强制调用监测。

优先完成 P0 修复及反例回归，普通工程问题自主处理。其后将动态 Runtime 和全局 Monitor 接入一个正式可运行但 opt-in 的动态 Runner；旧18 Suite注册表、历史数据、现有评分标准及 v1.1.2 协议均保持兼容。监测证据不完整时不可以把结果当作科学有效样本。

修正结构家族模型：把 suite/subtype/difficulty/domain 与真正可执行拓扑、证据、权限、工具前置条件和事件时序分开；signature、delta、digest、跨-run index 使用一致的规范化语义；用同构/近重复/真变化负例证明算法有效。不得用不同 suite 编号或 subtype 标签冒充新家族。保留合法同家族实例，但不增加有效 family 计数。

关于 M5：如果 Codex 已完成当前修复，请让其给出独立不可变快照（文件清单、SHA256、测试结果、未解风险）后立即只读验收并选择性合并，不必机械等待24h；绝不直接写其活动副本、覆盖整个主线或重造已有数据工厂。集成后必须用 `mimo-v2.6-pro` 真实生成少量 Blueprint，编译进**新的动态可执行世界**，通过细粒度 paired Gate、监测、可靠的跨批 family 比较，再让 `glm-5.3-flash` 独立审核最终 Case。严格分离 Data Factory 探索数据与 DeepSeek 正式测评数据，不用被测模型危险率挑题。

更新 `state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml` 等既有台账，记录明确的组件级、切片级、系统级验收范围；修正 M3 `VALIDATED` 但 DW-033 未开始、M7 `VALIDATED` 但 DW-070 仍进行中的状态范围不一致；M1 DW-013、M2 DW-022 也注明延期/非触发条件。不要新建平行 Goal。以最小闭环先验收 T321 两结构和 T312，再逐机制簇扩到18项。

执行期间每项留下修复前反例、修复后正负回归、测试范围、artifact path/hash和具体限制。遇到科学构念、GT、Oracle、scorer 语义或筛选原则变更必须停止相关部分请求 `PI_DECISION_REQUIRED`。T331 utility 和 T333 scorer abstain 保留专门审计；Gate D 必须真实独立专家，Pilot/Campaign 须单独授权。

本次不是要求再写报告就结束。先在隔离/可恢复的工作流程中修复 P0，再推进可自主完成的接线、集成和小规模真实验证；每段依据本次审核的可证伪条件验收。大规模扩量和正式测评仍待授权。
