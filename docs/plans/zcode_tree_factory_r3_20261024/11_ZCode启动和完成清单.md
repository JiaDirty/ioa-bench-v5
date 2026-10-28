# 11 · 发给 ZCode 的使用与完成清单

ZCode 文档：`https://zcode.z.ai/cn/docs/goal`。在项目根目录打开可编辑执行模式，**直接发送**根目录 `ZCODE_GOAL_COMMAND.txt` 中的 `/goal ...` 命令。若在旧会话存在目标，使用 `/goal replace ...` 明确替换；不要把此包的14份内容全粘到聊天窗口中。

## ZCode 应第一时间做的事

1. 真正阅读 `GOAL.md` 与 `00`～`11` 以及 `config/*.yaml`，再检查本地 `AGENTS.md`/state/真实源码；告诉用户本地 HEAD 和 R2 差异的真实结果。
2. 先复现 T321 截断、跨 trace witness、静态 BUSINESS_FLOW 回查，针对性修补并测，**不要先花一小时重写计划**。
3. 一个完整合法多阶段 CONTROL/RISK 参考执行通过后，再提交可组合 DAG 模块；再给新结构产出真实数据。
4. 模型端仅在源代码/本地证据校验能正确工作后发起付费请求；资金不设人为上限。保留新 run 的失败与停机日志。尽可能自主推进工程，遇真正外部阻塞如实报告。

## 完成时输出的8行汇报

- 本轮最终 `HEAD` 全 SHA / 分支 / dirty 与 baseline diff。
- `R3-G0～G7` 每项 PASS/PARTIAL/BLOCKED+真实证据文件。
- T321 多阶段具体 `stage, actor, action_seq, evidence_id` 示例及负例位置。
- 3套件新 WorkflowPlan 家族数量、运行结构区别，以及哪些属于旧结构。
- 每套件**本轮新 DEV_ACCEPTED** 对数与对应家族 ID，不能混计 R1/R2。
- 真实 AIHubMix 请求成功、截断、UNKNOWN/失败及 usage，明确 max_tokens 只是上限。
- 最终 HEAD 完整回归数、失败与未跑，以及历史核验真实 files_checked。
- SOURCE/EVIDENCE ZIP 路径、大小、完整 SHA、敏感信息扫描以及可复现命令。

如果 Goal 验证器反复要求无意义的计划文档，不应以增加空文档来满足，而应提供代码执行结果；如果新家族能力未满足，就从真实错误继续修代码和生成，不允许降低规范。测试失败不要说“环境问题”而不附复现命令和原始日志。
