# Formal Campaign Execution

Provider 调用前必须用户明确批准。

推荐编排入口：
`python scripts/run_online_campaign.py --start T311 --max-resume 6`

并发：
`IOABENCH_CONCURRENCY=3`

执行前必须确认当前 CLI 与 dataset-pack 参数真实语义。

新 Run ID 必须和历史目录区分，建议：
`deepseek-v4.1-flash-TXXX-<dataset-version>-v4-formal`

Model:
- deepseek-v4.1-flash
- temperature 0.0
- max_tokens 8192
- concurrency 3

T361–T363 永久 SIMULATION_ONLY。

T362/T363 SH：
glm-5.3-flash + sh-personas-1.0.0 + temp 0 + max_tokens 2000 + deterministic assignment + isolated context。

T353 保存 primary/honest/manipulated 三分支完整 Replay。

禁止 cherry-pick、rerun-to-safe、按结果重跑、用历史 Run 填 v4 缺口。
