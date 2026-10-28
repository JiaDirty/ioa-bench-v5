# 2026-10-19 数据工厂现场基线

唯一开发目录：`D:\Project\ioa_codex_spec`。沿用 `NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/GOAL_CONTRACT.yaml`，没有创建新 Goal。当前聊天的 Goal API 返回 null；这是线程状态，不等于项目 Goal 已完成或被删除。

改动前运行源码 SHA-256：`1416449d4ae6fda00d3f487e9d32115f553baf0c2002f5bb41591d2a43787e7d`。10 月 18 日源码 ZIP SHA-256：`ad8a5a0f41b04264ecf42706e75a52b04e481cc6a5d9b77bd693367197a88226`。ZIP CRC 通过，比较的 1,242 个源码/契约/文档文件零差异。45,434 个旧数据、发布及 artifact 文件已逐文件记录保护哈希；完整清单在 `artifacts/v5/data_factory/upgrade-20261019/BASELINE.json`。

原主目录没有 Git。用户随后明确授权初始化；建立本机 main 分支，基线提交 `90f691a2a163f01e01878bc4ce29bfe46ea32bfc`。`.env`、历史数据、artifact、Release、导出和归档由 `.gitignore` 排除。基线 1,239 个暂存文件的真实凭据扫描为零命中。未设置远程或推送。

启动时同目录旧聊天 `01a12bf2-911b-75c3-babf-64f81b0cc78b` 为 idle；进程命令行检查未发现引用主工作区的另一个执行任务。现有 OS writer lock 成功独占后释放。后续本聊天团队按文件范围分工，CLI 继续使用原 writer lock。

现有现场检查：`tests/v5` 852 passed（111.33 秒）；18 项离线工厂预检 36/36、228 个参考检查，Provider 0。原始 XML 为 `BASELINE_TESTS.xml`，工厂证据为 `artifacts/v5/data_factory/trials/df-baseline-20261019-r1/`。测试期间团队只修改独占的编译器文件，最终改动后的完整回归必须单独执行，不能复用此数字。

## 当前契约与冲突处理

- AGENTS、构念映射、现行评分与 Gate A–H 继续有效。附件是本轮实施要求，不能覆盖已冻结科学定义。
- 本轮直接用户授权及 PI-V5-017 覆盖旧“API 0/固定七模型/首故障停止”的工程限制；允许八候选预检、辅助生成、调试、独审、校准与有界小批试跑。质量拒收不触发更换裁判。
- DeepSeek 候选可做单独的连接预检；正式数据生产继续隔离被测家族。若探索性使用 DeepSeek 辅助角色，数据须隔离，不能晋升正式测评集。冻结正式被测配置不改。
- 附件的辅助面板难度属于开发期校准，不替代现有单模型确认协议中的设计 E/M/H 检验。不得用正式 SUT 结果选题、改难度或评分。
- 约 90 例是 AGENTS 的一般目标；当前有效统计草案是每项 60 对、30 家族。二者不是本轮放行配额，正式冻结前仍需 PI 确认最终抽样协议。
- GPT-6 Luna 文档协议说明有冲突；Qwen “Next” 身份不明确。记录为待预检，不猜 API ID。
- Gate D 无真人标签；确认性 Pilot、Campaign、Release 冻结没有本轮授权。T361–T363 继续 `SIMULATION_ONLY`。
