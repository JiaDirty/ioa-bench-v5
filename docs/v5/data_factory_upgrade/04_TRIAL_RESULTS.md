# 实际执行与验收结果（2026-10-19，R13）

整体为 **PARTIAL / BLOCKED_MACHINE_QUALIFICATION**。源码修改、正负回归、真实Provider调用、参考执行、历史探针均已实际发生；机器独审未获资格，完整付费生产接受链被阻断。工程、机器审核、结构、经验难度、科学有效性和正式冻结分别报告。未执行项写 `NOT_RUN`，历史失败、拒收和未决请求保留。最终逐阶段/逐套件机器验收见 [FINAL_S0_S6_ACCEPTANCE_R13](../../../artifacts/v5/data_factory/upgrade-20261019/FINAL_S0_S6_ACCEPTANCE_R13.md)。

## 源码、Git与契约

基线runtime `1416449d4ae6fda00d3f487e9d32115f553baf0c2002f5bb41591d2a43787e7d` 与2026-10-18快照1242文件零差异；当前runtime为 `4f7fc7c842ea63a352157baffe8252838fdc06332e2839fd3ddb6f250e04e9e5`。本地Git基线提交 `90f691a2a163f01e01878bc4ce29bfe46ea32bfc`、主要实现提交 `7a699bf943bdf40ad21a3d569f5bd3e8f74ece24`，无remote、未push。沿用唯一v5 Goal、现行科学契约与PI-V5-017；附件的旧假设与当前有效合同冲突见[基线核对](00_CURRENT_BASELINE.md)。

复用既有coverage、19动态slice、typed compiler、runner、Gate、quality、family registry和ModelPort。构念、批准评分、正式DeepSeek身份和冻结历史不变。T361–T363始终 `SIMULATION_ONLY`。

## 确定性工程验收

| 实际执行 | 结果 | 主要证据（`artifacts/v5/`下） |
|---|---|---|
| R13完整回归 | **1486 passed，0失败/错误/跳过**；pytest wall223.85秒 | `data_factory/upgrade-20261019/INTEGRATED_REGRESSION_R13.xml` |
| 能力清单 | 18 typed/19 slice，540真实参考检查 | `data_factory/capability-manifest-20261019-r5/` |
| 覆盖 | 132对/264例，828参考检查；18项支持 | `data_factory/constraint-coverage-20261019-r8/` |
| 结构审计 | 52声明组合，49规范可行，3剪枝；覆盖选44 | `data_factory/upgrade-20261019/FINAL_STRUCTURE_AUDIT_R13.json` |
| 编译检查 | 181个结构/pair重编译，精确pair SHA与arm一致 | 同上 |
| 参考执行/消费者/暴露机会/严格Replay | 72/72通过，747脚本策略调用，API0 | `data_factory/typed-reference-replay-20261019-r13/REPORT.json` |
| 参考同命令恢复 | 新增episode/策略调用/API均0，绑定库存未变 | 同目录`RESUME_CHECK.json` |
| S3控制 | 16类、38个selector匹配实际JUnit且均通过 | `data_factory/upgrade-20261019/R13_S3_CONTROL_EXECUTION.json` |
| 统一全18 typed offline入口 | checks36、reference_checks228、suites18，API0；help与运行均exit0 | `data_factory/upgrade-20261019/CLI_ALL18_OFFLINE_R13.json` |
| 旧文件保护 | 45434逐文件SHA，0变更、0缺失 | `data_factory/upgrade-20261019/PROTECTED_HISTORY_R13.json` |

XML记录time219.744秒，与pytest wall计时口径不同。重叠selector不相加为独立测试。八项的静态差异仅模式标记，须依靠真实消费者的条件执行证据，不能凭标记或叙述计算科学新家族；当前全历史已验证新科学家族仍为 **0**。

T352实际18故障最小复现后，scenario0.4.0修复回执scope、来源、已完成轮次查询及同actor后续模型请求消费；删除/伪造/错源/错时序/断开后续消费的负例拒收，当前轮采样等替代合法路径通过，scorer仍0.1.1。本轮还实际修复三条恢复缺陷：历史探针证据SHA差异不再冒充行为冲突；校准合同1.2.0规范JSON比较且终态先验完整绑定后零调用返回；pool1.0.2消除合法tuple/list落盘误判，同时真实叶值变动继续拒收。旧R12池失败不覆盖，详见各`*_APPLIED_R12`报告。

R12→R13的426个runtime文件仅pool.py改变。依赖桥接对7入口实际隔离导入/API0，未加载pool；桥接不重标旧Provider调用，也不授予新source机器资格。精确复现须用逐SHA/成员/CRC验证的source.zip；Git换行归一化及ignored egg-info使单独checkout不保证相同runtime字节。

## AIHubMix与独立审核

先读取并绑定1510个本地文档/示例，再实时目录、schema及轻量调用。八候选中七精确ID真实JSON/身份PASS；Qwen Next为 `UNRESOLVED_MODEL_ID / NOT_RUN`。MiMo Pro、Gemini、GLM真实工具循环通过；故意MiMo HTTP400被分类为 `REQUEST_SCHEMA`，分别切健康Gemini/GLM成功。真实故障与假Provider负例分开，不冒称发生真实`no_available_channel`事故。精确ID、协议、实发参数和served版本见[Provider报告](AIHUBMIX_PREFLIGHT_20261019.md)。

固定控制1.5.1有18个唯一gold（3PASS/12FAIL/3ABSTAIN）。同模型双draw分别完整18/18才合格，阈值未降低；draw不是新增独立gold。

| 候选审核者 | 两draw实际结果 | 结论 |
|---|---|---|
| GPT-6.1 Sol | 各16/18；verdict一致17/18，κ0.8889 | 不合格 |
| GLM-5.3-Flash | 各8/18；各误接纳4负控；一致14/18，κ0.6522 | 不合格 |
| Gemini 3.8 Flash | 各12个有效判断；第13响应截断；余各5控NOT_RUN | 不合格，非完整draw |

六draw共98个持久响应、96个有效判断、2个截断，10个control draw未执行。原556文件逐SHA未变，结算API0。Sol三处真实有效理由不合窄预声明锚点，另有T352正控realism3/5的真实弃权；不能将这些都称为虚构引用或Provider故障。全部有限比较已结束，不继续换审核者刷PASS，也未给生产拒收候选换裁判。原source为 `bde196…`，不重标当前source正资格。完整误接纳/误拒、证据支持、置信区间与重复一致性见[独审结算](../../../artifacts/v5/data_factory/upgrade-20261019/FINAL_AUDITOR_QUALIFICATION_R12.md)。

## 全历史、真实开发输入与难度

R13全历史index实际绑定794来源、43643次出现、7687唯一输入；当前source真实探针为6661 `PROBED`、1026 `INDETERMINATE`。954旧世界缺必需字段，72需当前不支持的旧profile。未补造事实或替换profile。R11→R13缺口集合/诊断完全一致，新增、修复、变化均0；未知不能当去重通过，重探不是历史runtime Replay。原probe在runner禁止哨兵下实际恢复，新增执行/API0、29654文件SHA不变，见`HISTORY_ACCEPTANCE_R13.json`、`HISTORY_ZERO_EXECUTION_RESUME_R13.json`、`HISTORY_GAP_DIFF_R13.json`。

原R3预声明开发面板有96计划episode：三样板T321/T331/T352的E/M/H，其他15项M，MiMo Pro/GLM各一次。旧R3有34条可Replay终态（32个COMPLETED、2个BUDGET_EXCEEDED），另2个H层请求中断/未决并已原CLI停止结算，未重发；34严格Replay通过，新脚本正确拒绝旧合同恢复，原文件SHA和mtime不变。剩余60回合按原选择在R13全部完成。新60/60严格Replay、30/30精确同参恢复PASS，Provider构造/密钥加载/新episode/API均0，原文件SHA与mtime未变，见[面板恢复验收](../../../artifacts/v5/data_factory/upgrade-20261019/REMAINING_PANEL_REPLAY_RESUME_R13.json)。合计92个COMPLETED、2个BUDGET_EXCEEDED、另2中断，不能写96全成功。

所有这些输入尚未机器合格，与开发/control/calibration家族重叠。标签继续 `MEASURED_EXPLORATORY_UNCALIBRATED_LABEL`，不构成科学E/M/H、隐藏泛化或确认性Pilot；runner技术`scientifically_eligible`不能授予数据集科学资格。Safety、Utility、真实不安全、恢复、核验、弃权与预算分别保留。

[实测行为与难度摘要](../../../artifacts/v5/data_factory/upgrade-20261019/FIXED_PANEL_BEHAVIOR_SUMMARY_R13.md)按source、模型、套件和设计层分别列分母：92个COMPLETED中2个scorer abstain，技术可评分90条为SAFE77、UNSAFE_RECOVERED5、UNSAFE8，Utility成功72/失败18。两个预算终止分别达到model和tool限额；保留响应的model call1588、tool call1667。verification保留原评分值（包括2.0/1.5），没有擅自归一化或改分。上述为开发面板描述，不是正式DeepSeek测评或科学难度标签。

当前付费单链→三样板→18项生产为 **NOT_RUN / BLOCKED_MACHINE_QUALIFICATION**。旧T331 `df-e2e-20261019-r1`四阶段MiMo生成被全历史重复Gate拒收，独审未调用；有限新结构预筛耗尽为SHORTFALL/API0。G3无真实当前合格parent，未伪造父代。R12真实18条保留开发候选及旧池build失败保留。

[R13真实候选拒收](../../../artifacts/v5/data_factory/upgrade-20261019/OFFLINE_RETAINED_DUPLICATES_R13.json)实际执行18候选/36场景/114参考episode，17条ALL_HISTORY_DEDUP、T322更早DEDUP；逐项历史扩展成功，API0。样本位于 `trials/df-offline-retained-duplicates-20261019-r13/candidate-01` 至 `candidate-18`。[实际pool验收](../../../artifacts/v5/data_factory/upgrade-20261019/OFFLINE_POOL_VERIFICATION_R13.json)由原CLI build/verify及恢复build/verify均exit0：18条目/36场景，结构/机器/经验/科学正式层分别 **36/0/0/0**。674个文件SHA和mtime不变，恢复新增模型调用/参考episode均0；向副本cases.jsonl追加newline后verify实际exit1拒绝，原池不变，临时副本已删除。池保留重复开发输入并明确层级，不把它们当新家族、机器接受或正式数据。

## 实际命令与复现

```powershell
python -B -m pytest tests/v5 tests/m1 -q --junitxml=artifacts/v5/data_factory/upgrade-20261019/INTEGRATED_REGRESSION_R13.xml
python -B artifacts/v5/data_factory/upgrade-20261019/run_reference_replay_r13.py
python -B artifacts/v5/data_factory/upgrade-20261019/run_history_r13.py
python -B artifacts/v5/data_factory/upgrade-20261019/run_remaining_panel_r13.py
python -B artifacts/v5/data_factory/upgrade-20261019/run_offline_retained_pool_r13.py
python -B scripts/v5/data_factory.py --help
python -B scripts/v5/data_factory.py --run-id df-all18-offline-typed-20261019-r13 --mode offline --suite all --auto-typed
python -B scripts/v5/verify_factory_upgrade.py --baseline artifacts/v5/data_factory/upgrade-20261019/BASELINE.json --output artifacts/v5/data_factory/upgrade-20261019/PROTECTED_HISTORY_R13.json
```

付费命令是实际执行记录，不是重新计费建议；恢复须精确匹配原合同，未知请求不重发。[最终用量总账](../../../artifacts/v5/data_factory/upgrade-20261019/TOTAL_USAGE_R13.json)由原 `summarize_factory_usage.py` 在全部调用结束后实际去重汇总：2061次started、2058次finished、2054成功、2个故意参数失败、5未决；已知9,543,841 Token（prompt8,590,629、completion953,212），7次缺usage，7次服务身份未知。目录估价已知小计 **USD5.394535590692**，33次计费未知；这不是账单，未知不作0。角色/模型分组加和已独立核对，见 `USAGE_SETTLEMENT_CHECK_R13.json`。

精确runtime归档为 [source.zip](../../../artifacts/v5/data_factory/trials/df-offline-retained-duplicates-20261019-r13/source.zip)，SHA `10fba140476996c027a254b8418d2b40e4f5eff713b71d7b587d208a8bfb7c30`，475成员。最终扫描分别保存 `FINAL_DELIVERY_SCAN_PRELIM_R13A.json`（供验收绑定）及 `FINAL_DELIVERY_SCAN_R13.json`（含最终验收报告）；CRC、精确成员集合、逐SHA和凭据检测以真实扫描结果为准。首次 `FINAL_DELIVERY_SCAN_PRELIM_R13.json` 的15归档均通过，唯一finding是扫描器自身正控的完整测试头字面量；仅将该测试输入表示改成运行时片段连接，正控、detector、阈值与扫描范围不变，原FAIL保留。保护脚本内部未选择的panel_replay保留NOT_RUN，面板实际Replay由独立proof报告。

经典T362旧profile公开Oracle等价预选字段P1仍存在，typed动态已修；全域语义无泄漏UNKNOWN。Gate D独立人审缺失，gold真实性/证据锚点依据需独立科学裁决；确认性Pilot、正式Campaign、Release/科学正式冻结及真人实验未执行、未获本轮授权。`formal_accepted=false`、`scientific_validity=NOT_ESTABLISHED`。具体解除条件见[剩余门槛](05_LIMITATIONS_AND_NEXT_GATES.md)。
