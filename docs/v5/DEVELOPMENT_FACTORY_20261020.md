# DeepSeek 研发生成与自动审核

本流程按2026-10-20用户最新授权启用：官方 `deepseek-flash` 可分别承担生成、自动审核和修复建议。它们使用不同请求ID和隔离上下文；同模型两次审核不构成科学独立验证。正式冻结、Gold、人审、PI和被测模型配置的旧规则没有被改写。

## 执行

在仓库根目录执行，密钥仅从环境或 `.env` 加载：

```powershell
python scripts/v5/run_development_factory.py --phase baseline
python scripts/v5/run_development_factory.py --phase prepare
python scripts/v5/plan_development_coverage.py --out artifacts/v5/data_factory/dev_auto_audit/round-20261020
python scripts/v5/run_development_factory.py --phase audit --plan artifacts/v5/data_factory/dev_auto_audit/round-20261020/plans/AUDIT_PANEL_V11.json
python scripts/v5/run_development_factory.py --phase calibrate
python scripts/v5/run_development_factory.py --phase generate --plan artifacts/v5/data_factory/dev_auto_audit/round-20261020/PLAN_COVERAGE_V1.json
python scripts/v5/run_development_factory.py --phase audit --plan artifacts/v5/data_factory/dev_auto_audit/round-20261020/plans/AUDIT_ALL_RETAINED_V11.json
python scripts/v5/run_development_factory.py --phase resume
python scripts/v5/run_development_factory.py --phase verify-history
python scripts/v5/verify_development_factory.py --out artifacts/v5/data_factory/dev_auto_audit/round-20261020
python scripts/v5/report_development_factory.py --out artifacts/v5/data_factory/dev_auto_audit/round-20261020
```

已经封存的计划与结果不能覆盖。新批次使用新的 `--out` 目录、任务ID和显式计划，并先执行该目录的 `baseline`、`prepare`，重新绑定当时的全历史；旧目录用于复现和恢复，避免把冻结索引当作持续更新的全局索引。已有终态仅校验并恢复，不发送请求。`--limit` 限制新增任务数。模型输出通过四阶段G2后，还必须通过编译、成对因果检查、参考执行、Oracle隔离、两臂全历史/同批去重和真实严格Replay，再独立发起high/max两次研发审核。任一硬门失败都不能由模型投票覆盖。审核引用逐个检查文件SHA-256和JSON Pointer。研发池通过 `DEV_POOL_INDEX.jsonl` 读取，不能把旧工程有效数当作本轮研发入池数。

## 审核协议版本

早期1.0协议的8次调用全部收到完整HTTP200终态，6次思考输出耗尽16384/32768预算，未得到最终JSON。这些结果保留为隔离终态，费用照实计入。1.1协议明确每条SUT观察所属运行/双臂和引用根路径；哈希完整性由程序验证，模型检查实际语义与反证。输出预算按原厂文档显式扩为65536，并绑定在每项 `AUDIT_SETTINGS.json` 和请求中。验收门槛不变。两种协议、预算与失败分母分别统计，不能把预算差异归为纯档位效果。

## 历史与多样性

保留原32对和全部原始证据。结构向量只计入运行时实际使用的工具、参与者、拓扑、事件时序和证据依赖；标题、领域、seed和文字长度不算结构新颖性。T362增加类型受限的证据传递图和释放时点，仍为 `SIMULATION_ONLY`。T322的120条旧版记录未恢复完整合同，当前版本候选只可进入版本隔离区，不能宣称全历史非重复。

`coverage-T321-01` 继续隔离：G2文字和task_graph中的gamma、延迟peer能力未兑现，实际执行为两个broker、初始可读peer能力；clean-close要求也只进入业务文字，现有utility未验证最终关闭。`deliveries_done` 计数broker发布，不代表业务数据送达，不能据此把空收据解释成Replay矛盾。该语义澄清不改原high拒绝、max接受和两审分歧，也不解除 `QUARANTINED`；naive参考策略v2仅影响后续源码。文件绑定、实际轨迹和限制见 [T321取证记录](../../artifacts/v5/data_factory/dev_auto_audit/round-20261020/T321_DESIGN_FIDELITY_LIMITATION.md)。

## 恢复与交接

UNKNOWN终态、鉴权/余额错误触发全局停止，不能自动重发或换模型绕过。完整响应的截断属于协议失败，保留真实usage并计费。软预算50元、硬预算200元，估算范围不等于账单。

`verify_development_factory.py` 负责只读证据验证、固定源码Replay和禁网恢复。解压后的零调用恢复可用 `run_development_factory.py --phase resume --out <解压位置内的本轮目录> --original-root D:/Project/ioa_codex_spec`，仅将原路径映射至当前仓库，不改封存内容。最终测试结果、未运行项目、费用及缺口以本轮 `ROUND_REPORT.md` 和 `EVIDENCE_INDEX.json` 为准。

在解压仓库中重新汇总报告时，使用 `report_development_factory.py --out <解压位置内的本轮目录> --original-root D:/Project/ioa_codex_spec`。映射只允许原工作区前缀；包内缺失证据会失败，不会回读原仓库。旧生成费用绑定实际账本、目录和复用来源，与本轮新增费用分别记账。

早期生成脚本漏存了T322范围转换前的完整索引原文。`recover_development_scope.py --out <本轮目录>` 仅用于核对冻结源码、计划和逐任务历史扩展后确定性补存该原文；必须与原范围报告、候选MANIFEST及已保存范围索引逐项相同。恢复收据明确标记为事后恢复、零调用，不提高T322历史资格。当前runner已在转换前持久化完整索引。

请求意图已写入、attempt尚未开始时中断，恢复仅复用内容完全相同的唯一意图；重复或参数变更会拒绝。已有started而无终态的attempt仍触发UNKNOWN停机。T321的naive参考策略v2等待offer并确认成功session，按实际成功发送结果判重；旧数据、正式SUT提示与评分保持原版本。

测试按源码版本分进程运行：当前工厂用 `python -m pytest tests/v5 -q`。旧 `tests/v4/conftest.py` 会在收集时切换至冻结v4源码，因此不能与v5放在同一pytest进程；误混合收集的失败证据保留，不改成PASS。非v5的旧测试中有直接写根目录实验产物的用例，应在独立的临时副本中执行，不能直接在受保护历史工作区扩大测试范围。
