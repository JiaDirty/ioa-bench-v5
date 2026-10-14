# IoA-Bench v5 工作区入口

本目录继续唯一的 IoA-Bench v5 项目。测的是模型在18种 IoA 风险下的可观察安全行为。

## 当前工作

- 18项经典测评和19个注册动态结构已有工程实现。
- 最新数据生成流程修复对应852项v5测试通过、18项离线预检36/36；新版独审尚待在线正负控制。工程通过不代表独立科学审核完成。
- 行为推断的否定句、判断让渡的复核要求仍待独立审阅。18项审阅材料已经准备，真人标签尚未产生。
- 尚未完成批量高质量数据、广泛难度/可靠性验证和正式科研测评。涉及真人的三项仍为 `SIMULATION_ONLY`。

以上更新于2026-10-14；继续工作先读取最新状态，不继承这里的测试数字。

## 最常用入口

| 想做什么 | 从哪里开始 |
|---|---|
| 继续开发 | [AGENTS.md](AGENTS.md)、[项目状态](state/PROJECT_STATE.yaml)、[v5队列](state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml) |
| 看当前进度 | [v5进度](docs/v5/V5_PROGRESS.md) |
| 看最近修复与待解决问题 | [数据生成流程审查](artifacts/v5/data_factory/review/process-audit-20261014-r1/REPORT.md) |
| 看18项真实测评的原始结果 | [在线测评报告](artifacts/v5/overnight_runs/20261013-authored-online-r1/MORNING_REPORT.md) |
| 使用当前候选案例 | [36条输入](artifacts/v5/manual_18/20261013-authored-contract-fix-r1/cases_all18.jsonl)、[逐条来源](artifacts/v5/manual_18/20261013-authored-contract-fix-r1/CURRENT_INPUT_INDEX.json) |
| 执行、续跑、回放、报告 | [系统使用说明](docs/v5/V5_SYSTEM_HANDOFF_20261012.md) |
| 了解数据生成流程 | [数据工厂说明](docs/v5/V5_DATA_FACTORY_HANDOFF_20261012.md) |
| 开展独立审阅 | [审阅者盲包](artifacts/v5/overnight_runs/20261013-scoring-audit-r1/review-package/reviewer_materials.zip) |
| 查全部目录和文件的位置 | [整个工作区索引](docs/WORKSPACE_FULL_INDEX_20261013.md) |
| 查历史交付包与旧会话 | [历史归档](archive/README.md) |
| 回滚本次整体整理 | [整理记录与恢复说明](artifacts/workspace_maintenance/20261013-r2/REPORT.md) |
| 查前一轮缓存清理 | [缓存清理记录](artifacts/workspace_maintenance/20261013-r1/REPORT.md) |
| 发给网页版ChatGPT审查数据生成流程 | [当前审阅说明及可复制请求](docs/HANDOFF_20261014_CHATGPT.md)、[源码包目录](exports/chatgpt-source-review-20261014/) |
| 查本次整理与恢复 | [2026-10-14整理记录](artifacts/workspace_maintenance/20261014-source-review-r1/REPORT.md) |

审阅者只接收 `reviewer_materials.zip`；旁边的 `sealed_key.jsonl` 是研究团队保存的对应表。

## 文件放在哪里

| 目录 | 内容 |
|---|---|
| `src/` | 实际运行代码；当前主线在 `src/ioabench/v5/` |
| `scripts/` | 可执行入口；当前主线入口主要在 `scripts/v5/` |
| `tests/` | 自动测试；当前主线主要在 `tests/v5/`，模型适配测试在 `tests/m1/` |
| `contracts/`、`config/` | 科研定义、机器可读规则与配置 |
| `state/` | 当前状态、工作队列和变更记录；也保留旧版本的历史记录 |
| `docs/` | 使用、设计和交付说明；当前v5说明在 `docs/v5/` |
| `NightGoalDoc/` | 用户提供的目标与执行政策 |
| `data/` | 数据集、运行记录和本地状态；不是可随意删除的临时目录 |
| `artifacts/` | 验证证据、候选、审计、源码快照与恢复材料 |
| `exports/` | 已生成的对外审阅或交接包 |
| `release/` | 历史发布与冻结材料，保留原样 |
| `archive/` | 根目录旧ZIP与旧会话集中归档；原路径映射和恢复工具保留 |

旧资料中的v1、v3、v4说明适用于其各自版本，不能据此判断当前v5状态。旧交付包现位于`archive/deliveries/`；历史清单中的原路径通过归档映射查找，旧恢复辅助脚本已同步。

## 本地检查

从当前目录执行，下列命令不会调用模型API：

```powershell
python -B scripts/v5/evaluate.py --help
python -B -m pytest -p no:cacheprovider tests/v5 tests/m1 -q
```

`-B`避免写入Python字节码，`-p no:cacheprovider`避免创建pytest缓存。模型真实运行、正式数据冻结与科研实验需遵循当前PI决策和对应运行说明。`.env`留在本机，不进入清理归档或分享包。
