<!-- Historical workspace entry; relative links below originally resolved from the project root. -->

# IoA-Bench v5 工作区入口

2026-10-27 R16 已收口工程验证：T352/T353 接入共享树状流程，医疗库存和支付结算各跑通两对脚本候选；16/16 离线组合、96 条严格回放、2206 项 v5+m1 全量回归通过，外部/provider 调用0。源码冻结720个文件；当前树状路线7/18，剩余11项。没有新增真实模型数据或正式数据，R15未知请求保留且未重发，审核资格和18项正式交付仍开放。见 [R16报告](artifacts/v5/data_factory/main_quality_20261026-r16/REPORT.md) 和 [最终验收摘要](artifacts/v5/data_factory/main_quality_20261026-r16/FINAL_VERIFICATION.json)。

2026-10-26 物流业务已接入：现有树状流程覆盖5项、3个可执行行业根；新增物流目前只用于跨系统级联扩散。8个物流模块支持三种实际流程和数量差异真假分支；2157项完整回归、36条严格回放通过。真实模型新增1对可执行候选，首审通过、第二次审核终态未知，隔离保留，新增入池0；付费调用停止且未重发。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r15/REPORT.md)。[整体交付计划](docs/v5/IOA_DELIVERY_ACTION_PLAN_20261026.md)继续按18项完整项目推进；其余13项接入、审核资格和正式数据验收仍开放。

2026-10-26 审核2.3已加入逐次真实观察与分组引用，2141项回归、18条严格回放和历史兼容复核通过。6次完整响应、0失败/未知；3组对照结论均命中，但至少6处引用不支持原结论，审核资格仍开放。新增样本0，完整目标继续推进。测试临时目录删除被自动审批拦截，17069个文件保留。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r13/REPORT.md)。

2026-10-26 试跑准备已接入有限业务图覆盖报告：92份历史尝试参与比较，每组24种有限图中仍有23–24种未覆盖；52项相关测试和120条最终严格回放通过。本轮API调用0、入池0。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r12/REPORT.md)。审核可靠性、上下文整合与其余13项组合继续开放。

2026-10-26 数量与业务分支一致性修复：医疗库存/补货点和支付异常笔数现在决定检查标志，模块目录1.3.0。2130项回归、20组配对及80组查询/检查回执通过；新增0对研发样本，6次完整响应、0次失败、0次未知。旧封存输入与运行层保留；审核器资格、难度、长期稳定性和其余13项组合仍开放。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r11/REPORT.md)。完整目标继续推进。

2026-10-26 同一交易试跑：责任链工单、源文档和业务回执已关联到实际医疗/支付对象，单独记录业务完成。2126项回归通过，本轮新增2对研发候选，9次完整响应、1次已知截断失败、0次未知。逐工具调用/运行计数进入审核2.2；旧样本定点复核不代表审核器资格通过。当前5项业务组合、13项待接入，另外4项已支持组合的领域一致性仍待处理。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r10/REPORT.md)。完整目标继续推进。

2026-10-26 责任链断裂已接入共享业务组合，当前支持5项、另13项待推进。2104项回归、30组本地配对及204条最终严格回放通过；本轮2个真实生成机会，新增2对研发入池，9次响应完整返回、0未知终态。条件分支已补测；审核器资格、难度和长期稳定性仍开放。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r9/REPORT.md)。完整目标继续推进。

2026-10-26 审核计数续建：新版2.1协议已加入逐运行业务动作计数和调用前核对。2072项回归通过，8份真实审核完整返回；既有语义对照双审核符合预期3/3。24条历史精确源码回放和4份终态断网重入通过。本轮无新增入池；未见样本校准及其余14项业务组合仍待推进。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r8/REPORT.md)。

2026-10-26 最新进展：注册失真已接入共享业务组合，当前支持4项、尚余14项。2065项最终回归通过，30组本地组合矩阵覆盖两种证据交付与条件真假路径。本轮4个在线生成机会，新增2对研发入池；初批2个因机制见证漏接而拒绝，原记录保留，修正后使用独立新批次试跑。审核器资格、难度和长期稳定性仍待验证。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r7/REPORT.md)。完整目标继续推进。

2026-10-26 最新质量修复：跨系统级联扩散的终端现在实际收到回执任务，只有成功发送才计入确认，正向见证要求真的确认，并修复重复回执循环。4份受影响方案重跑、2份可选分支方案覆盖真假路径；2040项最终回归、66条新版严格回放和42条旧源码回放通过。新6次语义审核完整返回，2/3组达到双审核预期；审核器资格仍未通过，本轮不新增入池。测试临时文件已按精确路径清理，原数据与结论保留。见[新版报告](artifacts/v5/data_factory/main_quality_20261026-r6/REPORT.md)及[上一轮混杂因素](artifacts/v5/data_factory/main_quality_20261026-r5/REPORT.md)。完整目标继续推进。

2026-10-26 最新试跑：硬事实由程序先检，模型审核业务与风险因果；8个机会全部工程通过，新增6对研发候选，覆盖协商污染、跨系统级联扩散、讨论扭曲各2对。4对具备所有业务步骤的执行见证，2对仍缺可选分支见证。28次请求完整返回、0未知终态，2028项回归、48条精确源码Replay、8个审核终态断网重入通过。原拒绝保留，讨论扭曲编译器1.2.0补齐运行时映射记录。完整目标仍在推进，语义校准、难度、长期稳定性及其余15项可组合支持未完成。见[本轮报告](artifacts/v5/data_factory/main_quality_20261026-r4/REPORT.md)与[审核分工决策](docs/v5/ADR_AUDIT_RESPONSIBILITY_20261026.md)。

2026-10-26 审核流程续建：证据引用改由程序绑定，增加原始响应重建、校准摘要一致性与逐项Schema验证。25次模型请求完整返回、0未知终态；2012项最终主线回归和116项相关检查通过，12个审核终态禁网重入保持文件不变。发现当前精确模型在请求严格Schema时仍会返回违约内容，审核稳定性尚未验收。本轮没有新生成样本，6个新机会未发送；完整目标继续推进。见[审核续建报告](artifacts/v5/data_factory/main_quality_20261026-r3/REPORT.md)和[协议说明](docs/v5/REGISTERED_AUDIT_20261026.md)。

2026-10-26 续建收尾：本轮6个机会有4个工程通过，新增协商污染和跨系统级联扩散各1对研发样本；2个隔离、1个历史重复拒绝、1个未运行。审核对照与生成共29次请求，28次完整返回、1次中断后终态未知，已停批且未重发。1995项主线回归、最后入口修正后99项相关检查和24条严格回放通过；禁网终态重入保留437个文件及既有入池记录。审核可靠性校准仍FAIL，原规则成功拦截已知错误；其余15项可组合支持与科研验收未完成。见[本轮报告](artifacts/v5/data_factory/main_quality_20261025-r2/REPORT.md)和[流程说明](docs/v5/MAIN_QUALITY_AUDIT_20261025.md)。

2026-10-25 数据生成续建：main上的共享生成器已到1.2.1，先核对实际负载与编译语义，再规划业务步骤，角色绑定使用实际候选，后续批次接入既有研发入池样本。首批6候选有5个工程通过、2对入池；修正后的单候选也入池，共新增3对研发样本。25次生成／审核请求完整返回、0未知终态；最终1991项回归、36条严格回放和零网络续跑通过。最新说明与复跑入口见[本轮生成流程](docs/v5/MAIN_QUALITY_TRIAL_20261025.md)，实际收据在`artifacts/v5/data_factory/main_quality_20261025-r1/`。科研接受与其余15项可组合支持仍未完成。

2026-10-25 Git整理：R3的3个提交已快进合入 `main`（`a18db13`），`codex/r3-closure-20261025` 已删除。原有未提交修改、未跟踪资料和历史数据保留；本轮离线检查、缓存清理及保护核验见 `artifacts/workspace_maintenance/20261025-merge-r3/`。首次回归1984通过、1项因测试临时路径失败，改用仓库外临时目录后相关模块24项通过；未调用模型，科研接受状态不变。

本目录继续唯一的 IoA-Bench v5 项目。测的是模型在18种 IoA 风险下的可观察安全行为。

## 当前工作区与源码快照（2026-10-25）

接口补充更新：按用户提供的大陆访问方式，当前AIHubMix适配器、预检与树状工厂默认使用 `https://api.inferera.com/v1`；控制台和历史来源链接不改，也不改系统代理。81项相关离线测试通过，未联网验证接口。新研发策略为1.2.0，旧1.1.0海外策略保留验证兼容。下方源码包是本次接口更新前的维护快照，不含这一后续改动；旧包不覆盖。再次在线运行前必须重新绑定端点与源码，不将新结果混入旧冻结比较。

当前主线为 R3 可组合业务工作流工厂，仍为 `PARTIAL`，不是科研正式接受。按已落盘入池记录去重，R3 新增研发配对为协商污染5对、跨系统级联扩散1对、讨论扭曲1对；每套两种新工作流家族、冻结对照和最终交接尚未验收。旧状态中的“网关持续不可达”已被后续成功调用记录超越，但本次没有联网验证当前网关。

本次仅清理22个开发缓存目录、330个文件（7,945,788字节），保留原始实验、旧包、未提交源码和未跟踪资料。源码快照以 `7e35bc1` 加当前工作区内容为基础，不冒充干净提交；一份历史收尾脚本的凭据字面量只在包内脱敏，原件未改。51项维护测试通过，未重跑完整业务回归或严格Replay。

先看[整理与交接说明](docs/WORKSPACE_STATUS_20261025.md)、[新版源码包](exports/source-code-20261025-r1/IoA-Bench-source-code-20261025-r1.zip)和[独立包验收记录](exports/source-code-20261025-r1/PACKAGE_VERIFICATION.json)。清理、保护基线与核验记录在 `artifacts/workspace_maintenance/20261025-r1/`。包是否验收通过以独立验收记录为准；旧交付不覆盖。

## 历史交付（2026-10-23）

官方DeepSeek研发闭环已交付：四阶段生成→硬门与历史去重→隔离上下文high/max审核→研发入池。当前19对/38条、12项测评，其中旧样本复用16对、新生成3对；原32对全部保留。讨论扭曲新增3种真实结构，互操作失配仍受120条旧版合同缺口限制。负例有效双拒绝4/6，校准FAIL；难度和长期稳定性未验证，正式科学状态不提升。

本次清理84个开发缓存目录、869个文件（约10.2 MiB），保留历史和未提交资料，运行源码不变。51项打包/报告回归通过；1844项全量回归和272次包内Replay为10月20日已验证检查点，本次未重跑业务全量。AIHubMix最近实测为10月20日HTTP401，今天未联网复验。

先看[当前进度与18项覆盖](docs/PROJECT_PROGRESS_20261023.md)、[新版源码包](exports/source-code-20261023/IoA-Bench-source-code-20261023.zip)、[包验收](exports/source-code-20261023/PACKAGE_VERIFICATION.json)。继续运行看[研发工厂说明](docs/v5/DEVELOPMENT_FACTORY_20261020.md)、[研发交接报告](artifacts/v5/data_factory/dev_auto_audit/round-20261020/ROUND_REPORT.md)和[完整重放包](exports/development-factory-handoff-20261020-r2/IoA-Bench-v5-Development-Factory-HANDOFF-20261020-R2.zip)。清理核验位于`artifacts/workspace_maintenance/20261023-r1/`。

## 历史交付（2026-10-19）

R13后续八模型工作已真实执行，整体`PARTIAL / BLOCKED`。见[本轮完成与阻塞](docs/WORK_COMPLETION_20261019_R3.md)。八模型均有JSON/工具实测；固定修复24/24通过，生成192计划中39对工程有效，78例均匹配历史行为、新科学家族0。真实401后停止新调用；Gold独立裁决及独审资格仍阻塞，机器合格样本0。开发面板11/48完成，难度未校准。以下R13/R2记录保留为历史检查点。

最新辅助参数修正：按文档完整输出上限和用户思考档位调用，6个模型新JSON/身份预检PASS；DeepSeek精确输出整数与Qwen Next ID仍待确认。见[参数实测](docs/v5/V5_AUXILIARY_FULL_PARAMETERS_20261019.md)和[新版交付说明](docs/WORK_COMPLETION_20261019_R2.md)。旧包及以下R13结论保留；新配置独审资格NOT_RUN。

数据工厂R13已实际实现与试跑，整体为`PARTIAL / BLOCKED_MACHINE_QUALIFICATION`：18 typed Suite、19动态slice，1486项R13回归通过；49个有限可行结构，全历史已验证新科学家族0。无合格机器独审，完整AI生产链`NOT_RUN`；科学有效性未建立，正式冻结未授权，T361–T363保持`SIMULATION_ONLY`。

最新入口：[工作完成与交付说明](docs/WORK_COMPLETION_20261019.md)、[S0–S6验收](artifacts/v5/data_factory/upgrade-20261019/FINAL_S0_S6_ACCEPTANCE_R13.md)、[更新源码包](exports/source-code-20261019/IoA-Bench-source-code-20261019.zip)、[包验证记录](exports/source-code-20261019/PACKAGE_VERIFICATION.json)。该R13交付记录属于上一检查点；当前参数修正与新增6次预检见上方R2说明。源码包验收以对应验证记录的实际结果为准。

主工作区现已初始化本地Git；R13交付提交`4e6a8fee7fd98e7a5424c8f9d2f16e633f18aac4`，`main`，无remote、未push。下方852项测试等历史检查点适用于2026-10-18及以前；当前状态以本节和最新交付证据为准。

## 历史工作检查点（2026-10-18）

- 18项经典测评和19个注册动态结构已有工程实现。
- 最新数据生成流程修复对应852项v5测试通过、18项离线预检36/36；新版独审尚待在线正负控制。工程通过不代表独立科学审核完成。
- 行为推断的否定句、判断让渡的复核要求仍待独立审阅。18项审阅材料已经准备，真人标签尚未产生。
- 尚未完成批量高质量数据、广泛难度/可靠性验证和正式科研测评。涉及真人的三项仍为 `SIMULATION_ONLY`。

2026-10-18重新核对：运行源码与2026-10-14一致；本次归并、清理和测试结果见[当前工作区检查](docs/WORKSPACE_STATUS_20261018.md)。继续工作先读取最新状态，不继承历史测试数字。

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
| 审查最新源码与完成情况 | [当前交接](docs/WORKSPACE_STATUS_20261025.md)、[最新源码包](exports/source-code-20261025-r1/IoA-Bench-source-code-20261025-r1.zip)、[包验证记录](exports/source-code-20261025-r1/PACKAGE_VERIFICATION.json) |
| 查本次整理与恢复 | [2026-10-14整理记录](artifacts/workspace_maintenance/20261014-source-review-r1/REPORT.md) |
| 查三个外部目录的去向及本轮清理 | [2026-10-18整理记录](docs/WORKSPACE_STATUS_20261018.md)、[检查或恢复原目录](artifacts/workspace_maintenance/20261018-r1/restore.py) |
| 查旧数据生成原型 | [已归档的隔离副本](archive/external_workspaces/20261018/ioa_codex_spec_ai_generation_probe/)、[原交付快照](archive/external_workspaces/20261018/ioa_codex_spec_ai_generation_probe/deliveries/) |
| 查Git与历史GitHub副本 | 主目录为本地Git仓库（main，无remote、未push）；[10月14日历史工作副本](exports/github-private-20261014/repository/)、[历史私有仓库](https://github.com/JiaDirty/ioa-bench-v5) |

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
