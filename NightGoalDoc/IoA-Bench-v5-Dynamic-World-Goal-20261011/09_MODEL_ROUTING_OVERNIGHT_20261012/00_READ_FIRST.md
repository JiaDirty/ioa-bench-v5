# IoA-Bench v5｜动态模型路由与 Codex 夜间持续执行增量包

本目录是对现有唯一 v5 Goal 的**增量修订**。复制到
`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-v5-Dynamic-World-Goal-20261011\09_MODEL_ROUTING_OVERNIGHT_20261012\`。
不得另起 Goal、升级 v6、重写18项科学定义或覆盖冻结证据。

建议阅读顺序：
1. `01_PI_POLICY_AMENDMENT.md`：用户最新科研/模型决策的范围。
2. `02_MODEL_ROUTING_POLICY.yaml`：按任务角色的模型候选与自动回退。
3. `03_OVERNIGHT_EXECUTION_CONTRACT.md`：可重入、持续推进与验收约定。
4. `04_SCIENTIFIC_GATES_AND_18_SUITE_PLAN.md`：18项执行顺序与不变量。
5. `05_CODEX_GOAL_PROMPT.md`：直接发送给 Codex 的主指令。
6. `06_MORNING_STATUS_TEMPLATE.md`：晨间交付格式。

重要：模型名称仅是候选，实际 model_id、API 协议、能力和可用性应由 Codex 在当前 AIHubMix 中发现并验证；不应声称本包已确认其即时可用。主线最新状态以本地文件和真实测试为准，不以旧会话/压缩包覆盖。主工作区同一时段只能有一个写入者，Codex 与 ZCode 需移交写权限或明确文件范围。

关于夜间持续运行：单条 Prompt 不能保证工具会话不会超时、崩溃或等待确认。若要跨会话持续执行，必须配置经确认有效的本机 Codex 非交互执行入口/外部调度器，并进行至少一次故障恢复演练；若无法配置，必须诚实说明无法保证无人值守重启。
