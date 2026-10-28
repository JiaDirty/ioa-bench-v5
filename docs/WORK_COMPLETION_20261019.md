# 工作完成与交付说明（2026-10-19）

本轮按用户要求更新源代码包和工作完成文档。数据工厂实施、模型调用和试跑的验收结论沿用已保存的R13证据：**PARTIAL / BLOCKED_MACHINE_QUALIFICATION**。本轮只更新交付，不重新调用模型、不重跑科研试验，也不把打包成功解释为科学验收通过。

## 本轮交付入口

| 内容 | 入口与用途 |
|---|---|
| 更新源代码包 | [IoA-Bench-source-code-20261019.zip](../exports/source-code-20261019/IoA-Bench-source-code-20261019.zip)；供源码交接与审查 |
| 包验证记录 | [PACKAGE_VERIFICATION.json](../exports/source-code-20261019/PACKAGE_VERIFICATION.json)；成员、逐文件SHA-256、ZIP CRC、凭据扫描及解压复查以该记录的实际结果为准 |
| 实际修改、结果与命令 | [R13试跑报告](v5/data_factory_upgrade/04_TRIAL_RESULTS.md) |
| S0–S6逐阶段、逐套件验收 | [最终验收报告](../artifacts/v5/data_factory/upgrade-20261019/FINAL_S0_S6_ACCEPTANCE_R13.md)及[机器可读记录](../artifacts/v5/data_factory/upgrade-20261019/FINAL_S0_S6_ACCEPTANCE_R13.json) |
| AIHubMix配置与预检 | [真实ID、参数、协议、工具调用和故障切换](v5/data_factory_upgrade/AIHUBMIX_PREFLIGHT_20261019.md) |
| 后续工作 | [未通过门槛与解除条件](v5/data_factory_upgrade/05_LIMITATIONS_AND_NEXT_GATES.md) |

源码包是源代码交付，不包含完整历史实验数据或本机凭据。上述链接和脚本的存在不等于已经验证；包验收以实际执行的验证记录为准。历史R13验收与调用记录保持原样，不由本轮交付更新重标。

本轮交付登记在[state/SOURCE_DELIVERY_20261019.yaml](../state/SOURCE_DELIVERY_20261019.yaml)。复用既有源码审阅打包器，先实际运行4项打包正负测试，再由下面的入口生成新目录并进行成员、CRC、SHA及独立解压校验；同名输出已存在时拒绝覆盖。旧10月18日包继续保留。

本轮4项打包测试实际通过。首次打包被原有凭据扫描器拒绝，唯一源码命中是一个明确的假密钥测试字面量；只将其写成两段字符串拼接，运行时测试值不变，扫描器、阈值和测试断言均未改。对应1项脱敏/鉴权失败回归实际通过；本轮新增验证合计5项，完整1486项回归为`NOT_RUN`。失败记录、命中诊断和两份JUnit随新包保留，未完成的临时ZIP已清除。

```powershell
python -B artifacts/workspace_maintenance/20261019-source-delivery-r1/package_current.py
python -B scripts/package_workspace_snapshot.py --verify exports/source-code-20261019/IoA-Bench-source-code-20261019.zip
```

## 已完成工作及证据边界

| 方面 | 已实际执行的R13结果 | 当前边界 |
|---|---|---|
| 工程 | 18个typed Suite、19个动态slice；`tests/v5 tests/m1`共1486项通过，0失败/错误/跳过；全18项离线入口checks36、reference_checks228通过 | 1486是R13已执行检查点，本轮未重新运行该回归 |
| 有限结构与覆盖 | 52个声明组合中49个规范可行、3个剪枝；132对/264例、828次参考检查覆盖44个规范结构；能力清单另有540次参考检查 | 49是有限结构容量，全历史已验证新科学家族为0；重叠检查不相加为独立样本 |
| 编译与执行保真 | 72个当前源码参考回合、消费者检查、暴露/机会检查与严格Replay通过；同命令恢复新增回合/API均0 | 脚本参考策略通过不替代真实模型或独立科学资格 |
| 历史去重与开发池 | 7687个历史唯一输入中6661个PROBED、1026个INDETERMINATE；18个新保留开发候选全部被重复Gate拒收；不可变池18 entries/36 cases，分层36/0/0/0 | 未填补旧世界缺失事实或换旧profile；未知不计去重通过，结构层不提升为机器/科学/正式层 |
| 机器独审 | 固定18控制、双draw门槛未降低；Sol各16/18、GLM各8/18、Gemini各12个有效判断后截断 | 无合格独审者，完整AI生产接受链为`NOT_RUN / BLOCKED_MACHINE_QUALIFICATION` |
| 经验难度 | 96个计划回合中92个COMPLETED、2个BUDGET_EXCEEDED、2个中断/未决；94条终态严格Replay通过 | 保留`MEASURED_EXPLORATORY_UNCALIBRATED_LABEL`，不能作为科学E/M/H标签或确认性Pilot |
| 科学与正式状态 | 工程、机器审核、结构、难度分别记录；T361–T363保持`SIMULATION_ONLY` | `scientific_validity=NOT_ESTABLISHED`、`formal_accepted=false`、`publication_ready=false` |

92个完成回合中有2个评分弃权；技术可评分的90条为SAFE77、UNSAFE_RECOVERED5、UNSAFE8，Utility成功72、失败18。Safety与Utility分开，不改原评分值，不把预算终止或未决请求当作完成。分母、生产源码及模型分组见[开发面板行为摘要](../artifacts/v5/data_factory/upgrade-20261019/FIXED_PANEL_BEHAVIOR_SUMMARY_R13.md)。

## AIHubMix调用与费用

1510份本地模型文档/调用示例及实时目录、schema已绑定。用户八候选中七个精确ID有真实基础JSON/身份验证，Qwen Next的精确ID未唯一解析，调用为`NOT_RUN`。真实MiMo工具循环及Gemini/GLM备用切换有保留证据；故意HTTP400按`REQUEST_SCHEMA`分类，未冒称真实发生`no_available_channel`。

[最终用量总账](../artifacts/v5/data_factory/upgrade-20261019/TOTAL_USAGE_R13.json)保留2061次started、2058次finished、2054次成功、2个故意参数失败及5个未决。已知9,543,841 Token，其中prompt8,590,629、completion953,212；7次缺usage、7次服务身份未知、33次计费未知。目录估价已知小计USD5.394535590692，不是完整账单，未知不作0。本轮交付更新新增模型调用0。

## 源码身份与本地Git

- 2026-10-18基线runtime SHA-256：`1416449d4ae6fda00d3f487e9d32115f553baf0c2002f5bb41591d2a43787e7d`。
- R13验收runtime SHA-256：`4f7fc7c842ea63a352157baffe8252838fdc06332e2839fd3ddb6f250e04e9e5`。
- R13精确runtime归档：[source.zip](../artifacts/v5/data_factory/trials/df-offline-retained-duplicates-20261019-r13/source.zip)，475成员，ZIP SHA-256为`10fba140476996c027a254b8418d2b40e4f5eff713b71d7b587d208a8bfb7c30`。
- 上一轮R13本地Git交付提交：`4e6a8fee7fd98e7a5424c8f9d2f16e633f18aac4`，分支`main`，无remote、未push；[交付收据](../artifacts/v5/data_factory/upgrade-20261019/GIT_DELIVERY_R13.json)保留报告生成时HEAD `7a699bf943bdf40ad21a3d569f5bd3e8f74ece24`，没有将后续提交重标为当时生产HEAD。

本轮源码包SHA、成员数、打包时Git身份及排除项由新的`PACKAGE_VERIFICATION.json`记录；它与R13精确runtime归档用途不同。Git存在换行归一化和ignored egg-info差异，精确复现R13运行须使用对应runtime归档及绑定命令，不能只靠checkout推定相同字节。

## 尚未完成

独审质量/证据契约资格、gold真实性和证据锚点的独立科学裁决、Gate D独立人审、经典T362旧profile预选字段的科学处置仍未解除。历史1026个输入的事实/profile兼容缺口保留，不补造数据。当前完整单链→三样板→18项AI生产为`NOT_RUN`。

确认性Pilot、正式Campaign、Release/科学正式冻结和真人实验均为`NOT_RUN`，未获本轮授权。沿用唯一v5 Goal、18项构念、批准评分、正式被测模型及历史冻结材料；本轮不新增科研完成结论。
