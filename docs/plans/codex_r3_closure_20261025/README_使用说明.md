# IoA-Bench v5 · Codex R3收口执行包

这是**继续完成已经开工的 R3** 的文件，不是让 Codex 从头做 R3，更不是开始一个声势浩大的 R4。

## 使用方法

1. 解压整个目录至 `D:\Project\ioa_codex_spec\docs\plans\codex_r3_closure_20261025\`，使 `GOAL.md` 路径存在。
2. Codex 的工作目录必须是 `D:\Project\ioa_codex_spec`（项目根目录），选择允许执行/修改的模式；用 `/status` 检查当前会话设置。
3. **推荐直接复制 `CODEX_START_PROMPT.txt` 整段发送**。如果 Codex CLI 版本支持 Goals（官方文档：0.128.0起支持），复制 `CODEX_GOAL_COMMAND.txt` 中的 `/goal` 指令更适合长期执行。若版本不支持 `/goal`，直接发普通启动提示，**不必因为 Goal 功能而卡住开发**。
4. 新会话先通读仓库现有 `AGENTS.md`、`PROJECT_STATE.yaml`、`WORKSPACE_STATUS_20261025.md`、本包 `GOAL.md`；需要时查对应任务文档，不要求第一步把所有历史材料反复读完。
5. 本包**不包含密钥值**；Codex 复用你本机已配置的 `AIHUBMIX_API_KEY`。你已经改过大陆可用的备用域名，Codex 先核实本地最新代码，避免覆盖为旧域名。

## 最重要的当前事实

- 2026-10-25 源码审阅快照：HEAD `7e35bc1591d970c4fd66765008000d4e0b637615`，当时有未提交修改；本地当前版本可能已更新。
- R3 已记录 `DEV_ACCEPTED` 共7对（T321×5、T331×1、T362×1），但图家族和全历史新颖性未闭环；不是7种机制家族。
- 当前最先修的是 `tree_factory.run_task()` 中 `if assertion_ids:` 包住业务见证的问题；然后完成结构去重与尚缺的试点数据。
- R3 原有模型请求有97次意图、94次完成，2条明确 REQUEST_UNRESOLVED、1条无终态审核意图；**不重发那些请求**。
- 历史1949通过的 JUnit 不能证明最新未提交工作区已经全绿。

## 本轮“快而不草率”

直接用现有源码动手；最小复现→最小修复→回归→真实生成→证据收口。省掉没有价值的层层审批、美元停机、重复写计划和复杂抽象。科学真值、严格回放、历史只读和请求不重复属于**数据有效性的组成部分**，不是可以去掉的防御性编程。

## 文件导航

| 文件 | 作用 |
|---|---|
| `GOAL.md` | 唯一完成合同 C0–C7 |
| `01_CURRENT_BASELINE.md` | 事实与未验证项，阻止误读历史快照 |
| `02_EXECUTION_QUEUE.md` | S0–S5 顺序、代码落点、命令与退出条件 |
| `03_MODEL_AND_ENDPOINT.md` | `api.inferera.com` 与 DeepSeek 参数策略 |
| `config/deepseek_quality_first.yaml` | 可机器读取的目标参数与合规约束示例 |
| `04_NOVELTY_AND_WITNESS.md` | 见证与图同构/新颖性具体算法和负例 |
| `05_EXPERIMENT_PROTOCOL.md` | 匹配A/B、修复与分母统计、消融 |
| `06_FINAL_ACCEPTANCE.md` | 最终证据、校验与交付目录 |
| `07_NEXT_15_SUITES.md` | 18项能力推广优先级，不擅自批量改动 |
| `08_CODEX_FAST_WORKSTYLE.md` | 少过程、多交付的编码执行习惯 |
| `CODEX_START_PROMPT.txt` | 普通 Codex 会话直接发送 |
| `CODEX_GOAL_COMMAND.txt` | 支持 `/goal` 的 Codex 发送 |
| `ACCEPTANCE_MATRIX.csv` | C0–C7 验收映射 |

## 版本备注

本包按用户2026-10-25上传的 R3 源码和工作区快照撰写。用户之后已让 Codex 切换 AIHubMix Base URL 至 `https://api.inferera.com`；**该最新本机改动不在旧ZIP里**，所以必须以本机当前值为准，避免写回旧版本。公开模型规格来自 AIHubMix 页面；最大输出上限的“参数接受”和“实际可持续输出”是两回事。
