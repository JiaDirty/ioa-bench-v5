# 整个工作区文件索引（2026-10-13）

本次逐文件检查整个`D:\Project\ioa_codex_spec`，不是只清缓存。当前项目入口是[WORKSPACE.md](../WORKSPACE.md)。

## 覆盖与处理

- 盘点34,405个原文件、6.11 GiB逻辑内容；本轮新维护输出与独占锁单独记录。
- 每个原文件都有分类、原位置、现位置、大小和SHA-256；整个目录没有未分类原文件。
- 10个根目录旧交付ZIP移至`archive/deliveries/`，5份旧会话移至`archive/conversations/`。
- 全量相同内容检查已完成；独立实验、冻结发布和审计副本保留各自路径，不用删除副本破坏复现。
- 代码依赖目录、18项科研定义、原数据/轨迹/证据和PI文档保留原结构。上一轮已移除缓存，本轮没有发现其他可判定为闲置的tmp/bak/stop残留。

## 全部顶层目录

文件数和MiB按原文件分类统计，不包含本轮新增文档/测试/维护清单。大小不是可释放空间。

| 目录 | 原文件数 | MiB | 用途与处理 |
|---|---:|---:|---|
| [NightGoalDoc/](../NightGoalDoc/) | 131 | 0.38 | PI目标与政策；不创建另一Goal |
| 根目录 | 8 | 0.03 | 入口、规范、项目配置及本机.env；不再散放历史ZIP |
| [adr/](../adr/) | 1 | 0.00 | 架构决策入口 |
| [archive/](../archive/) | 15 | 755.14 | 集中归档的旧根ZIP及旧会话 |
| [artifacts/](../artifacts/) | 14857 | 1212.65 | 验证、审计、失败证据和恢复包 |
| [config/](../config/) | 6 | 0.00 | 运行/模型配置 |
| [contracts/](../contracts/) | 60 | 0.34 | 冻结科研定义、18项构念和数据契约 |
| [data/](../data/) | 15825 | 4001.62 | 数据集、原始运行轨迹和本地状态；不清除历史记录 |
| [docs/](../docs/) | 63 | 0.50 | 当前说明与有版本语境的历史说明 |
| [exports/](../exports/) | 13 | 177.83 | 历次对外源码/审阅导出；按原生成版本保留 |
| [prompts/](../prompts/) | 19 | 0.00 | 生成/审核模板 |
| [release/](../release/) | 2411 | 107.45 | 发布清单与历史冻结内容；只读保留 |
| [roles/](../roles/) | 1 | 0.00 | 角色定义 |
| [scenarios/](../scenarios/) | 18 | 0.00 | 各项场景定义 |
| [scripts/](../scripts/) | 203 | 1.85 | 执行入口与历史恢复/审计工具；保留调用依赖 |
| [src/](../src/) | 353 | 1.99 | 运行代码；v5主线及仍被复用的基础模块 |
| [state/](../state/) | 20 | 0.66 | 最新状态、队列和历史验证记录 |
| [templates/](../templates/) | 2 | 0.00 | 说明和数据清单模板 |
| [tests/](../tests/) | 393 | 0.86 | 各版本自动测试；当前v5和模型适配测试均保留 |
| [worlds/](../worlds/) | 6 | 0.00 | 合成世界定义 |

## 所有二级文件分组

下面覆盖全部存在文件的二级分组。`data/runs`、`artifacts/audits`等内的具体版本/运行号在逐文件清单中查找，避免把数万行路径塞进说明。

| 分组 | 文件数 | MiB |
|---|---:|---:|
| [NightGoalDoc/IoA-Bench-Codex-End-to-End-Completion-Goal-Pack-20261002/](../NightGoalDoc/IoA-Bench-Codex-End-to-End-Completion-Goal-Pack-20261002/) | 14 | 0.03 |
| [NightGoalDoc/IoA-Bench-Codex-Full-Lifecycle-Goal-Pack/](../NightGoalDoc/IoA-Bench-Codex-Full-Lifecycle-Goal-Pack/) | 8 | 0.04 |
| [NightGoalDoc/IoA-Bench-Codex-Full-Lifecycle-Goal-Pack-v2-20260927/](../NightGoalDoc/IoA-Bench-Codex-Full-Lifecycle-Goal-Pack-v2-20260927/) | 11 | 0.05 |
| [NightGoalDoc/IoA-Bench-Codex-Persistent-Goal-Pack-v3.1-20260929/](../NightGoalDoc/IoA-Bench-Codex-Persistent-Goal-Pack-v3.1-20260929/) | 15 | 0.03 |
| [NightGoalDoc/IoA-Bench-Codex-Scientific-Closure-Goal-Pack-v3.2-20260930/](../NightGoalDoc/IoA-Bench-Codex-Scientific-Closure-Goal-Pack-v3.2-20260930/) | 14 | 0.03 |
| [NightGoalDoc/IoA-Bench-ZCode-Scientific-Closure-Goal-Pack-v3.2-20261001/](../NightGoalDoc/IoA-Bench-ZCode-Scientific-Closure-Goal-Pack-v3.2-20261001/) | 14 | 0.03 |
| [NightGoalDoc/IoA-Bench-ZCode-v4-Corrective-Formal-Campaign-Goal-Pack-20261001/](../NightGoalDoc/IoA-Bench-ZCode-v4-Corrective-Formal-Campaign-Goal-Pack-20261001/) | 15 | 0.02 |
| [NightGoalDoc/IoA-Bench-v5-Dynamic-World-Goal-20261011/](../NightGoalDoc/IoA-Bench-v5-Dynamic-World-Goal-20261011/) | 28 | 0.10 |
| [NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/](../NightGoalDoc/IoA-Bench-v5-Publication-Grade-Goal-Pack/) | 12 | 0.04 |
| [archive/conversations/](../archive/conversations/) | 5 | 0.08 |
| [archive/deliveries/](../archive/deliveries/) | 10 | 755.06 |
| [artifacts/audits/](../artifacts/audits/) | 8055 | 288.53 |
| [artifacts/construct-offline/](../artifacts/construct-offline/) | 2 | 1.42 |
| [artifacts/datasets/](../artifacts/datasets/) | 2 | 0.01 |
| [artifacts/delivery/](../artifacts/delivery/) | 5 | 374.90 |
| [artifacts/gates/](../artifacts/gates/) | 162 | 12.29 |
| [artifacts/generation/](../artifacts/generation/) | 1 | 0.00 |
| [artifacts/handoff/](../artifacts/handoff/) | 8 | 4.00 |
| [artifacts/provider/](../artifacts/provider/) | 1 | 0.00 |
| [artifacts/reports/](../artifacts/reports/) | 11 | 0.04 |
| [artifacts/runs/](../artifacts/runs/) | 6 | 0.01 |
| [artifacts/scientific_closure_v3_2/](../artifacts/scientific_closure_v3_2/) | 689 | 29.23 |
| [artifacts/scientific_closure_v4/](../artifacts/scientific_closure_v4/) | 3638 | 17.75 |
| [artifacts/scientific_validity_audit_20261004/](../artifacts/scientific_validity_audit_20261004/) | 18 | 1.11 |
| [artifacts/suite-gates/](../artifacts/suite-gates/) | 21 | 0.01 |
| [artifacts/v5/](../artifacts/v5/) | 2213 | 456.81 |
| [artifacts/workspace_maintenance/](../artifacts/workspace_maintenance/) | 24 | 26.48 |
| [config/models/](../config/models/) | 1 | 0.00 |
| [contracts/constructs/](../contracts/constructs/) | 18 | 0.03 |
| [contracts/ddl/](../contracts/ddl/) | 13 | 0.05 |
| [contracts/python/](../contracts/python/) | 19 | 0.01 |
| [contracts/schema/](../contracts/schema/) | 7 | 0.02 |
| [contracts/v5/](../contracts/v5/) | 2 | 0.22 |
| [data/datasets/](../data/datasets/) | 686 | 62.87 |
| [data/reports/](../data/reports/) | 26 | 5.26 |
| [data/runs/](../data/runs/) | 14390 | 3877.24 |
| [data/trials/](../data/trials/) | 381 | 18.46 |
| [data/v5/](../data/v5/) | 341 | 37.79 |
| [docs/v5/](../docs/v5/) | 27 | 0.28 |
| [exports/20261001-223139/](../exports/20261001-223139/) | 3 | 165.95 |
| [exports/chatgpt-source-review-20261010/](../exports/chatgpt-source-review-20261010/) | 4 | 2.97 |
| [exports/workspace-source-20261011/](../exports/workspace-source-20261011/) | 2 | 2.52 |
| [exports/workspace-source-20261011-r2/](../exports/workspace-source-20261011-r2/) | 2 | 3.17 |
| [exports/workspace-source-20261011-r3/](../exports/workspace-source-20261011-r3/) | 2 | 3.21 |
| [prompts/generation/](../prompts/generation/) | 1 | 0.00 |
| [prompts/judges/](../prompts/judges/) | 18 | 0.00 |
| [release/ioabench-v1.0-research-prototype/](../release/ioabench-v1.0-research-prototype/) | 2391 | 106.67 |
| [scenarios/T311/](../scenarios/T311/) | 1 | 0.00 |
| [scenarios/T312/](../scenarios/T312/) | 1 | 0.00 |
| [scenarios/T313/](../scenarios/T313/) | 1 | 0.00 |
| [scenarios/T321/](../scenarios/T321/) | 1 | 0.00 |
| [scenarios/T322/](../scenarios/T322/) | 1 | 0.00 |
| [scenarios/T323/](../scenarios/T323/) | 1 | 0.00 |
| [scenarios/T331/](../scenarios/T331/) | 1 | 0.00 |
| [scenarios/T332/](../scenarios/T332/) | 1 | 0.00 |
| [scenarios/T333/](../scenarios/T333/) | 1 | 0.00 |
| [scenarios/T341/](../scenarios/T341/) | 1 | 0.00 |
| [scenarios/T342/](../scenarios/T342/) | 1 | 0.00 |
| [scenarios/T343/](../scenarios/T343/) | 1 | 0.00 |
| [scenarios/T351/](../scenarios/T351/) | 1 | 0.00 |
| [scenarios/T352/](../scenarios/T352/) | 1 | 0.00 |
| [scenarios/T353/](../scenarios/T353/) | 1 | 0.00 |
| [scenarios/T361/](../scenarios/T361/) | 1 | 0.00 |
| [scenarios/T362/](../scenarios/T362/) | 1 | 0.00 |
| [scenarios/T363/](../scenarios/T363/) | 1 | 0.00 |
| [scripts/v5/](../scripts/v5/) | 37 | 0.37 |
| [src/ioa_bench.egg-info/](../src/ioa_bench.egg-info/) | 6 | 0.01 |
| [src/ioabench/](../src/ioabench/) | 347 | 1.98 |
| [tests/closure/](../tests/closure/) | 2 | 0.01 |
| [tests/construct/](../tests/construct/) | 28 | 0.17 |
| [tests/gates/](../tests/gates/) | 19 | 0.03 |
| [tests/integration/](../tests/integration/) | 3 | 0.00 |
| [tests/isolation/](../tests/isolation/) | 4 | 0.00 |
| [tests/m0/](../tests/m0/) | 16 | 0.01 |
| [tests/m1/](../tests/m1/) | 12 | 0.03 |
| [tests/m10/](../tests/m10/) | 14 | 0.01 |
| [tests/m2/](../tests/m2/) | 20 | 0.02 |
| [tests/m3/](../tests/m3/) | 19 | 0.02 |
| [tests/runtime/](../tests/runtime/) | 2 | 0.01 |
| [tests/t311/](../tests/t311/) | 12 | 0.01 |
| [tests/t312/](../tests/t312/) | 11 | 0.01 |
| [tests/t313/](../tests/t313/) | 11 | 0.00 |
| [tests/t321/](../tests/t321/) | 9 | 0.00 |
| [tests/t322/](../tests/t322/) | 11 | 0.00 |
| [tests/t323/](../tests/t323/) | 11 | 0.00 |
| [tests/t331/](../tests/t331/) | 9 | 0.00 |
| [tests/t332/](../tests/t332/) | 9 | 0.00 |
| [tests/t333/](../tests/t333/) | 9 | 0.00 |
| [tests/t341/](../tests/t341/) | 9 | 0.00 |
| [tests/t342/](../tests/t342/) | 9 | 0.00 |
| [tests/t343/](../tests/t343/) | 9 | 0.00 |
| [tests/t351/](../tests/t351/) | 9 | 0.00 |
| [tests/t352/](../tests/t352/) | 11 | 0.00 |
| [tests/t353/](../tests/t353/) | 11 | 0.00 |
| [tests/t361/](../tests/t361/) | 13 | 0.01 |
| [tests/t362/](../tests/t362/) | 13 | 0.01 |
| [tests/t363/](../tests/t363/) | 13 | 0.01 |
| [tests/v4/](../tests/v4/) | 11 | 0.04 |
| [tests/v5/](../tests/v5/) | 51 | 0.41 |

## 当前主线与历史的边界

当前实现入口：`src/ioabench/v5/`、`scripts/v5/`、`tests/v5/`；模型适配和共享基础模块仍在旧目录中，被当前v5复用，不能按目录年龄删除。

`docs/v5/`与`state/PROJECT_STATE.yaml`中的v5字段描述当前研发；旧版本报告和旧发布保留当时结论。`exports/`是历史已生成的对外包；文件日期不代表当前源码。

旧ZIP和会话的内容没有重写。历史报告仍记原路径，查找时用[移动映射](../artifacts/workspace_maintenance/20261013-r2/RELOCATION.json)；读取旧ZIP的辅助脚本已修正，必要时可回滚原布局。

## 全量清单、验收和恢复

- [所有原文件的分类与现位置](../artifacts/workspace_maintenance/20261013-r2/FILE_CATALOG.json)
- [整理前全部文件大小与哈希](../artifacts/workspace_maintenance/20261013-r2/INVENTORY_BEFORE.json)
- [全部相同内容分组与保留决策](../artifacts/workspace_maintenance/20261013-r2/DUPLICATES.json)
- [处理结果及验收报告](../artifacts/workspace_maintenance/20261013-r2/REPORT.md)
- [最终校验结果](../artifacts/workspace_maintenance/20261013-r2/VERIFICATION.json)
- [原布局恢复工具](../artifacts/workspace_maintenance/20261013-r2/restore_layout.py)

`.env`留在原位置，内容不输出、不进入归档。科研进度和正式验收条件不因整理而改变。
