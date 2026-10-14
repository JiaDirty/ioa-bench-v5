# Provider Approval Template

v4 Release 与 18 个正式 Run Manifest 已冻结，离线验证全部通过。

准备进入 Provider 阶段。

预计：
- Phase D smoke：约 6–12 次调用；
- Phase E：18×90=1620 cases；
- tested model：deepseek-v4.1-flash；
- concurrency：3；
- 预计被测模型调用约 19,000–22,000；
- SH 辅助调用约 1,045；
- 总体约 2.0–2.4 万次 Provider 调用。

请选择：
A. 仅批准 Phase D；smoke 后再确认 Phase E。
B. 同时批准 Phase D + Phase E。
C. 暂不批准。

未明确批准前不得调用 AIHubMix。
