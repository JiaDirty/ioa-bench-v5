# IoA-Bench v5 Publication-Grade Scientific Revision — Codex 长期 Goal

将 `D:\Project\ioa_codex_spec` 中**已经完成18项核心实现**的 IoA-Bench v5，推进到有可核验科学证据支持的 **publication-grade / submission-ready 单模型 Benchmark**。这是原有 `IoA-Bench v5 Publication-Grade Scientific Revision` 的继续执行：**不创建新 Goal，不升 v6，不从零重建18项**。

最终成果须证明：18项 canonical 风险测量与因果操纵符合各自构念；CONTROL/RISK 配对合理；模型确实接触目标刺激且有行动机会；安全/任务效用/恢复/无效执行分离；被测上下文不泄露 evaluator/GT；场景数据具有实质独立家族、可追溯真值和有效难度；评分可靠、独立审阅与统计不确定性有证据；正式数据、模型配置、接受工具和分析计划在 Campaign 前冻结，结果可复现且论断不超出证据。

唯一正式被测模型为 AIHubMix 的 `deepseek-v4.1-flash`（`PI-V5-005`）。历史四模型 Pilot 及 v4.1.13 均只读保留，不追认或混入新正式结果；T361–T363 始终 `SIMULATION_ONLY`。AI 辅助生成/复核模型可用于丰富数据，但不是被测模型，也不能单独定义 Ground Truth。所有新付费 Provider 调用（含 smoke、生成、复核、Pilot、正式运行）须事先获得用户对目标与费用的明确批准（`PI-V5-006`）。

以当前磁盘证据而非旧日志为准。先解决影响在线测评有效性的真实适配/运行/工具/Exposure/scorer缺陷；保留已通过的18项实现及已有候选数据；再小规模验证AI高质量场景生成与独立复核；随后完成 Gate D 专家审阅、Gate E 单模型确认 Pilot、Gate F 科学冻结、Gate G 正式 Campaign、Gate H 统计与论文交付。按 `NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/03_PUBLICATION_READINESS_CONTRACT.md` 的适用 Gate A–H 和当前 v5 正式协议核验，不要求跨模型比较。不要以模型分数、成功率或样本配额为理由降低科学阈值或反向调参。

执行要高效直接：优先复用现有代码与证据，先最小复现、局部修复与针对性测试；避免无依据的防御性编程、多层 fallback、无意义抽象、反复全仓审计与重复生成文件。必要的科研不变量与原始记录必须完整保存。普通工程事项自行推进，阶段状态记录到现有 v5 台账；每轮根据证据选下一项真正影响科学结论的工作。

**完成判据：** 全18项在冻结版本上满足 Gate A–H 所需的可审计科学证据，独立评审与可靠性指标成立，DeepSeek 确认 Pilot 和获批准正式测评完成，产出复现清单、分母/失败/不确定性完整的统计报告，并明确支持与不支持的论文 claim。若缺专家、用户费用批准、必要权限或关键原始证据，完成所有可自主推进的离线任务后明确记录 `BLOCKED`、已完成证据与最小解锁条件；**不得伪造通过，也不得无限重试**。
