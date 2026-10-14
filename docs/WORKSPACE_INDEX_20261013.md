# 工作区索引（2026-10-13）

当前主线是唯一IoA-Bench v5。先读[中文入口](../WORKSPACE.md)，再读状态和最新证据。历史资料保留自己的版本与结论。

## 当前资料

| 类别 | 入口 |
|---|---|
| 实现 | `src/ioabench/v5/`、`scripts/v5/`、`tests/v5/` |
| 真实运行和修复 | [本次研发报告](../artifacts/v5/overnight_runs/20261013-scoring-audit-r1/MORNING_REPORT.md)、[18项在线报告](../artifacts/v5/overnight_runs/20261013-authored-online-r1/MORNING_REPORT.md) |
| 状态与队列 | [项目状态](../state/PROJECT_STATE.yaml)、[当前v5队列](../state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml)、[v5进度](v5/V5_PROGRESS.md) |
| 当前案例 | [36条候选](../artifacts/v5/manual_18/20261013-authored-contract-fix-r1/cases_all18.jsonl)，不是正式冻结数据 |
| 系统操作 | [执行/续跑/回放/报告说明](v5/V5_SYSTEM_HANDOFF_20261012.md) |
| 数据工厂 | [数据工厂说明](v5/V5_DATA_FACTORY_HANDOFF_20261012.md) |
| 独立审阅 | [盲包](../artifacts/v5/overnight_runs/20261013-scoring-audit-r1/review-package/reviewer_materials.zip)，不提供sealed_key给审阅者 |
| 本次清理和恢复 | [清理报告](../artifacts/workspace_maintenance/20261013-r1/REPORT.md)、[恢复包](../artifacts/workspace_maintenance/20261013-r1/rollback.zip) |

## 顶层目录盘点

此处大小是整理前的文件逻辑字节数，不等于实际占用或可释放空间。

| 目录 | 文件数 | 文件合计MiB | 用途 |
|---|---:|---:|---|
| `data` | 15825 | 4001.62 | 数据、在线轨迹、本地状态；保留 |
| `artifacts` | 14848 | 1198.69 | 科研/工程证据、候选、源码快照；保留 |
| `[root files]` | 18 | 755.09 | 入口、配置与历史ZIP；仅更新README |
| `exports` | 13 | 177.83 | 历史对外包；保留 |
| `release` | 2411 | 107.45 | 发布与冻结证据；保留 |
| `src` | 456 | 3.32 | 运行源码；不改 |
| `scripts` | 213 | 2.04 | 工具与入口；只清缓存 |
| `tests` | 428 | 1.56 | 测试；只清缓存 |
| `state` | 21 | 0.70 | 最新和历史状态；闲置备份已归档 |
| `docs` | 62 | 0.49 | 说明与历史交付；新增当前索引 |
| `NightGoalDoc` | 131 | 0.38 | 用户目标文档；保留 |
| `contracts` | 60 | 0.34 | 原结构保留 |
| `.pytest_cache` | 5 | 0.09 | 可重新生成的测试缓存；已归档移除 |
| `claude_export` | 5 | 0.08 | 既有外部说明/导出；保留 |
| `config` | 6 | 0.00 | 原结构保留 |
| `prompts` | 19 | 0.00 | 原结构保留 |
| `worlds` | 6 | 0.00 | 原结构保留 |
| `scenarios` | 18 | 0.00 | 原结构保留 |
| `roles` | 1 | 0.00 | 原结构保留 |
| `templates` | 2 | 0.00 | 原结构保留 |
| `adr` | 1 | 0.00 | 原结构保留 |

## 根目录历史交付包

原路径被历史恢复工具、状态或索引使用，全部保留。没有将旧包当作当前v5交付；也没有未经核对删除“看起来重复”的包。

| 包 | MiB | SHA-256 |
|---|---:|---|
| [IoA-Bench-current-workspace-handoff-20260925.zip](../IoA-Bench-current-workspace-handoff-20260925.zip) | 84.58 | `078705973a45e8874662d02640c67aabeeec942134c93f2e12397fc61af1a1f9` |
| [IoA-Bench-current-workspace-handoff-20260926-current.zip](../IoA-Bench-current-workspace-handoff-20260926-current.zip) | 86.42 | `b4a47dd68fd2035fca70a28912eebb50a3f99c0659d0c3cc8a8c4c47ce3cf9b6` |
| [IoA-Bench-current-workspace-handoff-20260926-final.zip](../IoA-Bench-current-workspace-handoff-20260926-final.zip) | 86.43 | `68e2c7fd1f04c309337962bb6863afe8843a0b7c876f37e0ef3c075ee35aa838` |
| [IoA-Bench-current-workspace-handoff-20260926-readonly.zip](../IoA-Bench-current-workspace-handoff-20260926-readonly.zip) | 85.65 | `8c60eebb8015c9547e145941a0477cf71434f21eb30d6fbd6fc1f3fbf93779bb` |
| [IoA-Bench-current-workspace-handoff-20260926.zip](../IoA-Bench-current-workspace-handoff-20260926.zip) | 84.61 | `9cfcb1887b4b2d8eda9a2aebe76c2e71eb9efa90a17e227c63c3dc97bc406161` |
| [IoA-Bench-current-workspace-handoff-20260929-latest.zip](../IoA-Bench-current-workspace-handoff-20260929-latest.zip) | 107.82 | `a185ff90980ff983cdb560d3d13be9ba16d011a14d608a8890ed0f696d02ad8e` |
| [IoA-Bench-source-20260927.zip](../IoA-Bench-source-20260927.zip) | 0.57 | `66476c0bd8d403d3a8f888c8b6e12e0fd95ab4b0747ff9f8b259bf572defbaca` |
| [IoA-Bench-v1.0-research-prototype-workspace.zip](../IoA-Bench-v1.0-research-prototype-workspace.zip) | 48.82 | `4f927918e141a73261b1b5094335cdaa5a550d5eeed6b28d361c0252f817c749` |
| [IoA-Bench-v3-20260930-final-delivery.zip](../IoA-Bench-v3-20260930-final-delivery.zip) | 153.17 | `ad59d79f4c6cc44f460fd1bdf716225d617f4d845e85a1b937f6d3f632f7bbfa` |
| [IoA-Bench-v3.2-final-delivery-20261001.zip](../IoA-Bench-v3.2-final-delivery-20261001.zip) | 16.99 | `dc269294dab02e6e4fe427483f6440b5c3825344e6cb0e1befeedac67380a83e` |

## 本次移出的闲置文件

下列原文件被保存在恢复包的同名路径下，没有丢弃内容：

- `state/PROJECT_STATE.yaml.bak-preyamlfix`：旧YAML修复备份，读取输入未引用它。
- `artifacts/v5/overnight_runs/20261013-scoring-audit-r1.stop`：已退出工程锁助手的停止标记。

缓存仅清理当前src/scripts/tests的`__pycache__`和根目录`.pytest_cache`；历史artifacts/data/release内部文件不按名称推断为垃圾。
.env保留原路径，内容不写入索引、归档或报告。科研数据、原始调用、旧评分、冻结版本和恢复包都保留。
