# 08｜Codex 高效执行风格：少过程、多交付

这是一组**工作偏好**，不是额外的验收门槛；GOAL.md 的C0–C7仍是唯一完成合同。

## 核心循环

**Read just enough → reproduce the actual bug → edit the owning code → targeted test → inspect actual output → next bottleneck → final broad regression**。

- **已有同类实现，先补原实现**。`tree_factory`已是唯一 online pipeline；`workflow_compiler`已是 parser/compiler；`AihubmixStudy`已有 request ledger；`tf_r3_pilot`已有 frozen task list；不要再次做 `tree_factory_next.py`、`reviewer_v999.py`、`api_client_2.py`。
- **小步执行不是步步请示**。一次只聚焦最短的关键改动，把最少的相关测试跑通，直接继续下一个核心缺口。无需每个阶段让用户回答“是否继续”。
- **不要把测试当任务本身**。若某测试通过却没有覆盖真实 `run_task` 或真实 trace，补一条定点端到端测试；不要靠几十个 mock PASS 掩盖运行时没动的事实。
- **并行用于独立信息，不用于共享状态**。查历史索引、阅读见证代码、整理模型错误分母可以并行；不要两个Agent并发写同一个`REQUEST_LEDGER.jsonl`、`WORK_QUEUE.yaml`或 Git HEAD。
- **不乱清工作区**。当前有未提交修改，这可能是用户让 Codex 刚做的 Inferera URL 改动；不要因“想要干净 Git”就 `reset --hard`、`clean`、覆盖旧zip。
- **不因预算而偷工减料**。DeepSeek输出空间给足、默认SSE高思考，在语义任务本身值得时用max；费用不是Stop条件。性能瓶颈是有效新结构/高质量样本的**时间和可靠性**，不是一美元多或少。
- **不靠无限重试掩盖坏设计**。如果某候选无法编译、图同构已有覆盖，先调整计划/能力路径再生成下一条。只有明确完成的被拒请求才可以用**新ID、有区别的输入**做有因果理由的修复；`UNKNOWN` 不重发原POST。
- **质量门是内核，不是防御性负担**。权限与证据真实、配对Oracle、全历史新颖性、Replay是科研可信度要求；简化实现不是删除这些验证。

## 维护一个极简进度文件就足够

在现有R3 run里保持1份`R3_GOAL_STATUS.json`：每个 C 项填状态、最新证据、下一动作。可另写一个不超过一页的`NEXT_ACTION.md`，但不要每修一处就新增一份几十页规划。终局交付按 `06_FINAL_ACCEPTANCE.md` 一次总结。

## 每次输出给用户的进度应该长这样

> 已修 `[真实源码路径]` 的 `[问题]`，复现测试 `[命令]` 从 FAIL→PASS；下一步直接做 `[具体工作]`。本轮候选池新增 `[真实数字]`，图家族 `[真实数字/待审]`。失败或未知请求 `[精确数量]` 保留不重发。

避免一段接一段宣布“设计完成”却没有任何真实代码、有效新样本或验收结果。
