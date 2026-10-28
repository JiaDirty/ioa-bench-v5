# 01｜审阅基线、最新变化与禁止重复造轮子

## 可信的基线材料

- `WORKSPACE_STATUS_20261025.md`：本轮状态与历史记录、工作区维护边界；旧快照并非最终接手时状态。
- `PROJECT_STATE.yaml`、`WORK_QUEUE.yaml`、`AGENTS.md`：现场工程约束优先；文件不存在时请找实际项目入口，不要机械创建替身。
- `artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1/`：真实R3 run。已有 `BASELINE_R3.json`、`TASK_SET_FROZEN_R3.json`、`R3_AB_PREREGISTRATION.json`、`R3_ABLATION.json`、`T321_MULTISTAGE_PROOF.json`、`NEGATIVE_WITNESS_CASES.json`、`FULL_REGRESSION_R3.xml` 等部分材料；最终 `R3_DEV_POOL_INDEX.jsonl`、`WORKFLOW_NOVELTY_AUDIT.json`、`R3_AB_RESULTS.csv`、`R3_AB_REPORT.md`、`R3_GOAL_STATUS.json` 在2026-10-25快照仍缺。
- `scripts/v5/tf_r3_*`：脚本已有，优先适配并运行；存在 `tf_r3_pool_index.py`、`tf_r3_finalize.py`、`tf_r3_history_protection.py`、`tf_r3_ablation.py` 等。
- `src/ioabench/v5/ai_generation/workflow_modules.py` / `workflow_compiler.py`：已有 12 阶段以内 typed DAG module+edge grammar；不能再次开“自由 Python 代码生成器”。
- `tree_factory.py`：三种 route 的主链已实现，`compositional_r3` 把模型提出的 WorkflowPlan 编译成 binding，再经 IR/编译器/执行器，关键路径不应拆掉。

## 最新已有成果（不冒充全部验收）

| 项目 | 2026-10-25记录 | 仍需证明 |
|---|---:|---|
| R1原有新研发入池 | 7对 | 历史只读 |
| R2原有新研发入池 | 10对 | 历史只读 |
| R3 T321 | 5对 | 新图家族数、历史覆盖、逐条完整业务见证 |
| R3 T331 | 1对 | 新增≥1对及至少两种历史未覆盖图家族 |
| R3 T362 | 1对 | 同上；保持SIMULATION_ONLY |
| R3 严格 Replay | 每对记载6次 | 当前 HEAD 上的重跑/签名绑定 |
| R3模型调用 | 97意图、94完成 | 2未解决、1无终态，不能再发同ID |
| 回归 | 历史1949 JUnit pass | 当前最终 HEAD 重新跑 |

## 先核对而不是覆盖

`2026-10-25` 快照（HEAD `7e35bc1...`）记录 `aihubmix_study.BASE_URL` / `tf_r3_pilot.POLICY.base_url` = `https://aihubmix.com/v1`；**用户随后已让本地Codex改为 `https://api.inferera.com/v1`**。这是新的真实用户变更，不在旧档案中。接手时读取 `git diff` 与真正运行时配置，若已全链一致，就不要做多余修改；若只有半条链改了，以最小差异修正剩余冲突。

R3以前自动化里 `T331-x5`、`T362-x4` 的 `assertions=[]` 正好是业务见证漏触发的定点红测材料。不要只写一个人工构造的测试绕开 `run_task()`。

## 代码级事实与推断界限

1. 旧快照 `tree_factory.py` 的 `if assertion_ids:` **直接包住** `business_witnesses`；这是真正代码缺陷，应修。
2. `tf_r3_pool_index.py` 已存在用于生成入池索引与 workflow-hash 新颖性表，但需要确认“归一同构”的字段覆盖与历史样本基线，不能因为文件叫 `NOVELTY_AUDIT` 就相信它完成。
3. 既有 `workflow_compiler.py` 兼容合法声明/编译机制，工作重点在 **执行能力扩容与见证真实性**，不是推翻编译器。
4. 最新源码包没有完整封存历史去重库；Codex 本地机器可能有，请以真实路径检查。若缺失，用既有历史交接材料合法恢复，不要用仅7对R3样本充当全历史去重。
5. “用户不考虑费用”不意味着可以把未知终态请求随意重发；保留请求身份与不可重复性是为了防止数据溯源混乱。

## S0 只需完成的五件事

- `git status --short`、`git rev-parse HEAD`、关键 `git diff --name-only`。
- 检查工作区最新 `.env`/环境变量能用（只输出是否存在，不输出值），新 `api.inferera.com` 路由是否对齐；不要擅自启动 VPN 或改系统代理。
- 枚举各候选的 `ADMISSION.json`，按候选 ID 去重，并统计真正可回放的 `DEV_ACCEPTED`。
- 检查 frozen 18 tasks、AB 本轮已跑的机会和失败分母，不重置已落盘的实验。
- 明确最新 HEAD 与源码运行 SHA；快速进入 S1 修见证，不必写一套新的“基线平台”。
