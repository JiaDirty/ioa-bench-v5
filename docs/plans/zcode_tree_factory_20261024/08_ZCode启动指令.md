# 08｜ZCode GLM-5.3 启动方式

## 1. 设置环境

- 在 Windows 上用 ZCode 打开 `D:\Project\ioa_codex_spec`，选择 ZCode Agent，**GLM-5.3，思考强度 Max**。此Max是编码 Agent 的思考档，不是生产模型effort；生产模型使用包内 `04_AIHubMix_DeepSeek_模型配置.yaml`。
- 先将整个本包解压到工作区，例如 `docs/plans/zcode_tree_factory_20261024/`，或将这10个文件全部放到工作区可读目录。**不要只上传一个GOAL.md 而遗漏配套文档。**
- 需要文件编辑和运行测试的执行模式（官方建议 Full access/自动编辑用于长任务），但应坚持原工作区安全边界和禁push。ZCode文档：`https://zcode.z.ai/cn/docs/goal`。
- 在本机安全环境配置 `AIHUBMIX_API_KEY`，若用户已经在对话中公开过Key，请先轮换。**不要把Key粘贴进ZCode对话/Goal或存Git**。

## 2. 先发这条消息（非 /goal）

```text
请阅读本工作区 AGENTS.md、state/PROJECT_STATE.yaml、state/WORK_QUEUE.yaml、docs/PROJECT_PROGRESS_20261023.md，以及 docs/plans/zcode_tree_factory_20261024/ 下的 00_使用说明.md、GOAL.md 和 01–09 全部配套文档。后续以GOAL.md的G0–G7为验收依据，在既有v5源码上实作，不新建v6，不修改已封存历史，不绕开质量硬门。请特别区分：ZCode GLM-5.3 Max是开发Agent，生产调用AIHubMix deepseek-v4.1-flash-1017由ModelPort发起；Key只能读本机环境变量，不输出。尚未通过线上小探针前先完成离线任务。
```

## 3. 再发唯一 `/goal` 命令

```text
/goal 在现有IoA-Bench v5中按GOAL.md的G0–G7全部验收条件，完成T331/T321/T362树状依赖业务分支、typed MechanismIR、编译消费与执行见证、程序事实审核、有界新ID修复和AIHubMix deepseek-v4.1-flash-1017真实冻结A/B试点；每套件获得至少一对真实新DEV_ACCEPTED并证明结构不同，同时保证全量回归/严格Replay/历史不变/预算停机/证据和本地Git交接全部通过，任何401或终态未知必须停付费并报告BLOCKED，不允许虚报完成。
```

> ZCode官方说明：一个会话同一时间**只有一个**Goal，输入 `/goal <目标>` 就是设定；如果已有旧Goal，请先确认是否需要替换，命令 `/goal replace <目标>`；`/goal` 查看，`/goal pause|resume|clear`可控制。**不要指望GOAL.md文件自己自动生效**。不能在 Plan 模式里启用，需要换成可执行模式；运行中任务也不能另设Goal。

## 4. 后续执行控制

- 每轮结束ZCode会检查目标是否完成，证据不足则继续迭代。要求Agent维护 `GOAL_PROGRESS.json`，尽量每1–2轮输出一段有用的进度说明，但绝不因报告文本而宣称完成。
- 如果停止或断开，会话Goal通常可恢复；重新进入会话查看 `/goal` 状态，避免随意创建第二个Goal或重跑已完成请求。
- 只因为没有API Key/401/历史文件缺损的外部阻塞，才请求用户采取明确操作；软件缺陷、受限分支冲突、校验失败，应尽力自主推进离线代码与修复。
- 建议在将工作交给 ZCode 前保留工作区备份与Git提交；新工作允许创建隔离分支，但不得删除/重置已有历史或替用户发布仓库。

## 5. 每轮少量进度汇报模版

```text
当前阶段 Mx：实际完成(证据路径/命令)；失败或BLOCKED原因；线上付费请求x次、未知终态y次、目前累计预算估算范围；新增DEV_ACCEPTED z对（不含旧样本）；下一轮按GOAL.md应该继续做什么。
```

## 6. 结束时的交接

ZCode要把本地文件打包，而不是只贴窗口中的“已完成”；最少必须提交 `ROUND_REPORT.md`、`EVIDENCE_INDEX.json`、`NEW_POOL_INDEX.jsonl`、`AB_RESULTS.csv`、`AUDIT_CALIBRATION.json`、`STRUCTURE_CELLS.csv`、`COST_AND_YIELD.json`、完整回归与Replay证据、新旧源码SHA和可核ZIP。达到G0–G7后才能宣布此Goal完成。
