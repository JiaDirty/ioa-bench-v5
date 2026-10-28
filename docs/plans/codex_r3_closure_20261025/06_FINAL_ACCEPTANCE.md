# 06｜收尾验收与独立审阅交接清单

## 必须是同一个最终版本

最后所有实证材料都绑定：`git_head`、`working_tree_diff_sha256`（若dirty）、`runtime_source_sha256`、`run_id`、`model_id`、`base_url`、`generation_profile`、`audit_protocol`、`history_index_binding`。

**历史JUnit 1949项是历史结果**，不得冒充本轮最终HEAD的验证；HEAD有变化必须重跑受影响套件，最终交付前对全部原有范围做一次统一回归。若本地tracked tree含用户原先未提交改动，先识别，必要时以独立工作树/仅add本轮文件精确提交，不要覆盖其修改；要如实标注最终对未提交工作区的源码hash。

## 最终验收 C0–C7 核查表

| Gate | 实物 | 可复核检查 | 成功要求 |
|---|---|---|---|
| C0 | R3_RESUME_STATE, git diff, provider state | HEAD/dirty/runs/旧UNKNOWN独立索引 | 未误清除/覆盖用户工作 |
| C1 | 强制见证源代码+单测+BUSINESS_WITNESSES | assertions=[]真实run + W1–W9反例 | 不再有静默漏检且合法例PASS |
| C2 | WORKFLOW_NOVELTY_AUDIT, STRUCTURE_FAMILY_INDEX | 非同构/同构/跨版本基线复核 | 不用hash不同代替新家族 |
| C3 | R3_DEV_POOL_INDEX + 候选完整证据 | 每套≥2对+≥2可执行历史新家族 | 三个试点都达标 |
| C4 | Model contract + request ledger | 模型/域名/思考/输出/SSE/终态 | 无人为美元停机，无截断误接收 |
| C5 | R3_AB_RESULTS, R3_AB_REPORT, R3_ABLATION | frozen任务/route/首次vs修复/失败分母 | 对照诚实完整 |
| C6 | JUnit+StrictReplay+保护哈希 | 最终版本下重跑与非零核验范围 | 没有伪PASS或历史替代 |
| C7 | Commit + 双ZIP+manifest+handoff | ZIP CRC / 成员SHA / Git/源码引用 | 独立评审无需问“文件在哪” |

## 最终输出目录建议

新产生的结果仍按仓库已有命名约定写入R3工作区；结束时独立给审查者：

```text
exports/codex-r3-closure-20261025/
  R3_CLOSURE_REPORT.md
  R3_GOAL_STATUS.json
  REVIEW_FILE_INDEX.json
  PACKAGE_VERIFICATION.json
  FILE_SHA256.json
  IoA-Bench-v5-Codex-R3-SOURCE-REVIEW.zip
  IoA-Bench-v5-Codex-R3-EVIDENCE-REVIEW.zip
```

SOURCE应覆盖本轮变动源码+完整依赖链+测试+合规配置/协议+commit/diff，EVIDENCE应覆盖**候选全分母**（包括失败/拒绝/隔离/原始审核/回放）、新家族证明、AB任务冻结与结果、JUnit、历史索引绑定、请求匿名化账本、运行参数与限制。无需复制20万历史文件，给出有意义的已核验文件范围、原清单与命中证据；**但不能拿无法访问的老路径当作真的能复核**。

文件如涉及凭据使用，不把密钥字面值放进ZIP，替换发生在导出副本内，记录被替换文件原件和导出件的hash差异，不动原来的代码与实验账本。

## 代码和运行验证命令（实地确认再执行）

```powershell
cd D:\Project\ioa_codex_spec
python -B -m pytest tests/v5/test_workflow_composition_r3.py tests/v5/test_tree_ir_runtime_r2.py -q
python -B -m pytest tests/v5 tests/m1 -q --junitxml=artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1/FULL_REGRESSION_FINAL.xml
python -B scripts/v5/tf_r3_pool_index.py
python -B scripts/v5/tf_r3_history_protection.py
python -B scripts/v5/tf_r3_ablation.py
```

注意：这些脚本可能依赖完整历史资料（该资料不包含在上次源码审阅ZIP），必须先检查本机运行环境和脚本实际参数；`tf_r3_finalize.py` 只在结果完整、测试已执行并核对过代码后运行，不要抢先输出GOAL PASS。

## 最终报告必须回答的问题

1. 这次究竟改了哪些文件，业务见证漏检怎样复现和修复？
2. 当前真实 `api.inferera.com/v1` 调用是否稳定？实际允许的高输出参数、推理消耗、完成率是多少？
3. R3 现有7对里每对究竟属于什么图家族，哪些不算新？最终新增合格对与新图家族各几种？
4. T321/T331/T362各有哪些至少两种历史未覆盖的**可执行**结构？实际trace怎么证明？
5. A/B有多少冻结首轮机会、修复、失败、阻断、UNKNOWN？是否存在协议漂移？
6. 审核误判与证据不足是否仍有案例？怎样隔离？
7. 当前最终版本的完整回归、Replay、历史保护是否有原始收据？
8. 其余15项后续分别需要哪些 capability/module/slice work？不用现在改完。
9. 正式科学审核未完成项、SIMULATION_ONLY的边界是什么？
10. 现在下一步应该进入15项推广，还是仍因真实技术缺口阻塞？

## 完成/阻塞语言

只有 C0–C7 每一项真实PASS才报 `COMPLETED`。如果两个ZIP生成了但A/B未完成、C2新颖性仍不确定或C1漏见证，那叫 `PARTIAL`。如外部请求无法完成但代码/离线核验已完成，准确标 `PARTIAL` + 附具体证据和继续条件，不能为结题补假回执。
