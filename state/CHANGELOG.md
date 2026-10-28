# Specification Changelog

## 工作区整理与GitHub源码同步 — 2026-10-28

- 更新当前工作入口并保留旧入口；仅清理可再生开发缓存，历史数据、包与未提交材料保留。
- 现有仓库公开；按远端历史追加当前源码、测试、文档与R22脱敏摘要，旧本地历史仅留本地分支，不上传新增实验原始数据或私人材料。远端已有数据与发布记录保留。
- 移除旧扫描脚本的真实凭据字面量，以格式扫描替代；有凭据与无凭据输入检查通过。运行源码不变，未重跑完整2295项测试，无模型调用或科研验收变更。远端提交核对详见本地维护回执。

## R22代表资格漂移接入只读结算业务树 — 2026-10-28

- 在现有树状入口接入T313-S4。中介与执行者实际分开运行，签发、派发、当前授权链读取、执行与只读业务回执关联同一子授权和结算资源；复用五个已有读取/核验/检查模块。原授权、修订、Oracle、评分、预算不变，超期执行仍由原评分器识别。
- 50项相关测试、2295项全量回归、8组全历史共享入口及48条严格回放通过；覆盖两种授权链查看方式、连续/并行汇合/条件真假结构。1233个源码等文件及ZIP核对通过，39829个历史文件未改，外部调用0。
- 当前12项本地路线、11项共享入口工程通过、23个套件与行业组合；新增真实模型调用/研发入池/正式数据均为0。只覆盖现有有效期修订和两名代理交接，不代表所有漂移维度或正式合格数据。下一项为结构暴露，T322历史合同及T343未知审核另行保留。证据 `artifacts/v5/data_factory/main_quality_20261028-r22/REPORT.md`。

## R21历史整理提速及晨间验收 — 2026-10-28

- 沿用原合并方法，把40对案例一次并入历史索引，修正两个脚本及对应测试。8259条完整记录与附带信息相同，只忽略数组顺序；一次本机测量105.18秒降至6.54秒，不推算模型或整条生成耗时。
- 当前源码2280项回归、12组结构及88条严格回放通过，0外部调用；1230个源码等文件与归档一致，38950个历史文件未改，R21新增模型调用/研发入池/正式数据均为0。
- 已更新晨间汇报、18项业务矩阵、行动计划、展示案例及项目状态；早晨9点工作窗口结束，整体目标仍未完成。下一轮先接真实多跳授权，T322旧合同与T343审核连接问题分别跟踪。证据 `artifacts/v5/data_factory/main_quality_20261028-r21/REPORT.md`。

## R20业务接入与模型试跑结果 — 2026-10-28

- 规范漂移接入药品订单与支付结算，两名operator共享请求金额、审批、执行、撤回和业务回执；互操作失配接入支付结算，源指令、网关映射、原生记录及生效/补偿回执关联同一结算号。评分、Oracle、基础提示、预算与风险槽不变。
- 12组离线组合完成88条严格回放；规范漂移8组通过共享生成流程，互操作失配4组本地执行通过，但因120条旧案例缺原运行合同被历史门拒绝，未计入池。
- 修正T343机构、行业和同事活动一致性，最终2279项回归通过。新药品候选1对6步执行及8条回放通过；审核发送时curl55连接重置，终态未知而隔离，支付机会未运行。批次3请求/2完整/1未知，新增研发入池0、正式数据0；未知未重发。极小新请求100token验证单列，费用上界USD0.000398；批次完整响应8560token、上界USD0.044792，未知请求费用与账单未知。
- 1230个源码等文件核验，14909个历史文件未改；结束批次重进0外部调用、121个文件内容及mtime不变。用户要求推进至北京时间09:00，续办ID ioa-9保留于状态；实际夜间窗口已在R21收尾，整体项目未完成。证据 `artifacts/v5/data_factory/main_quality_20261028-r20/REPORT.md`。

## R19真实生成小批完成 — 2026-10-28

- T311/T351药品与支付4对真实生成候选全部通过工程检查、两轮研发审核和严格回放，新增4对DEV_ACCEPTED、8条案例；每对所有业务步骤都有参考执行见证。4个实际计划包含并行汇合、连续处理和条件处理三种结构，支付条件另做真假两侧验证。
- 编译器1.2保留T311生成背景，明确T311/T351/T353程序业务内容与中性文字的合成映射；新增来源、运行路径、文字保留和审核入口检查。评分、预算、真值与质量门不变，原拒绝与隔离不改。
- 最新源码2252项回归、112条离线组合回放、28条新候选脚本参考回放、12条真实计划分支回放通过。16个请求全部完整，0失败/0未知；usage1323894token，费用上界USD3.524616，实际账单未知。
- 1225个源码等文件与归档一致，12013个历史文件不变；完成批次重进0新请求、443个文件内容及mtime不变。当前树状9/18、19个套件与行业组合，另外9项、独立审核可靠性、难度校准与正式全系统交付仍开放。证据 `artifacts/v5/data_factory/main_quality_20261028-r19/REPORT.md`。

## R17接入、暂停对账与R18结构来源修复 — 2026-10-28

- T311资格伪装、T351激励错配接入共享业务树；当前9项、19个套件与行业组合，另9项待接入。R17全量2248项通过，16组离线候选、112条严格回放通过；保留该源码快照，不将它当作R18回归结果。
- 对账暂停批次：8个请求、7份完整响应、1个未知终态；1对物流案例研发入池、1对药品案例隔离、3个机会未运行。暂停前206个原文件未改；未知请求未重发。恢复批次另生成4对，8个请求均完整，因案例缺顶层结构来源映射在语义审核前全部拒绝。
- 修复T311/T351/T353编译器实际映射的状态与持久化，版本1.1；新增从共享生成到审核前检查的测试，检查来源与运行路径真实存在。39项定向测试、16组业务结构和112条回放通过；R18全量回归、新批4对真实生成正在进行。原拒绝、暂停和历史数据不改；评分、预算、质量门和隐藏真值隔离不变。
- 6份真实计划的目标与业务背景能保留，步骤、依赖、条件解析前后相同。正式数据仍新增0；审核资格、难度校准和完整18项交付未完成。R17报告见 `artifacts/v5/data_factory/main_quality_20261027-r17/REPORT.md`。

## R16 树状业务扩展与离线稳定性验收 — 2026-10-27

- 为10月28日汇报整理现状、完整案例展示、小批真实生成和剩余路线的推进顺序，见 `docs/v5/REPORT_BRIEF_AND_PRIORITIES_20261027.md`；不新增数据或提升验收状态。
- T352 声誉垄断、T353 节点操纵接入共享树状工厂，医疗库存和支付结算两类业务根各跑通两对脚本候选；16/16 组合通过，96 条严格回放通过。
- 新增流式证据路径的路由、失败保留、测量池和历史校验衔接；相关 88 项测试通过。全量 v5+m1 回归 2206 项通过，失败/错误/跳过均为0，外部调用0。
- 源码冻结720个文件，源哈希 `f4d846e9996c4cfede214e851bba2a6bd9f7e597d8a6f4ef843758c2579ee9d3`。18项业务适用矩阵登记18行、35条源码映射；当前树状路线7项，剩余11项。
- R16无新provider调用、无新正式数据、正式接受仍为false；R15未知终态请求保留且未重发。QDIV-005工程范围完成，QGEN-005、QAUD-002、QCOH-001、Q18-001继续进行中。证据见 `artifacts/v5/data_factory/main_quality_20261026-r16/REPORT.md`。

## Executable logistics workflow expansion — 2026-10-26

- Tree1.1/module1.4/T331 compiler1.5/tree factory1.6/trial2.8/capacity1.1 add shipment reconciliation and local handover to the existing pipeline. Three business roots, five suites, eleven supported suite/industry groups; logistics currently T331 only. Manifest/scan quantities and variance agree, and the T331 ledger uses the same shipment's declared manifest quantity.
- Three structures and both variance branches executed;2157full regression and36current-source strictReplay PASS;695source files verified,694baseline files preserved. Existing frozen data, scorers, SUT base prompts, budgets and thresholds unchanged. Older omitted optional when fields remain usable in planning without dropping real conditions.
- One fresh model-generated pair passed engineering/history/replay. High reviewACCEPT;max reviewREQUEST_UNRESOLVED, quarantined,0newadmissions. Four intents/3complete/1unknown;unknown not resent and new paid calls stopped.193549complete-response tokens,USD0.616580complete-response upper bound;unknown request cost and invoiceUNKNOWN. One terminal reentry adds0requests.
- QDIV-004 complete for engineering expansion and recorded trial outcomes only;QGEN-005 starts on explicit business goals/natural context and lossless plan parsing. QAUD-002/QCOH-001/Q18-001 and full18-suite goal remain open. Root project status now reflects active v5 work, while historical v4 campaign records remain intact. Evidence main_quality_20261026-r15/REPORT.md.

## 完整IOA测评项目交付行动计划 — 2026-10-26

- 登记单一交付目标：18项完整数据、树状业务多样性、真实被测模型运行、评分、严格回放、报告与团队数据/源码交接。
- 明确当前树状生成入口仅覆盖T312/T321/T323/T331/T362和药品/支付两个业务根；8类既有行业素材中6类未接入可执行工作流。旧5.1.x候选保留作历史来源，不混报当前正式接受数据。
- R14离线证据为46项定向与2149项完整回归通过、外网调用0；来源最终核验、真实审核控制、新版候选生成/冻结仍未完成。无代码生成或模型试跑由本计划文档本身完成。
- 行动顺序：收口R14、建立18项适用背景矩阵、扩树与模块、接入剩余套件、18项小批验证、每套约90条并按难度校准、全量真实模型评测和交付回放。风险定义和正式质量门不在本行动计划中自行修改。

## Observation-grounded audit protocol — 2026-10-26

- Audit2.3 adds verbatim per-action recorded/actually observed receipts and native document-group citations; preflight1.3 rebuilds the sealed packet. Trial preparation2.6.0; old protocols preserved. No scorer, SUT prompt, budget, gate or frozen-data change.
- 2141complete/27focused checks PASS with0external attempts;18current strictReplay and6legacy+3new terminal zero-call resumes PASS. R12 1852/R11 1507/older15388 files unchanged.
- Six complete real responses,0failed/0unknown,779570reported tokens,USD2.210080complete-response bound;invoiceUNKNOWN. Three paired expected-label matches and6native Schema passes do not establish semantic qualification: at least6literal citation errors across2reviews, role-count overstatement and infrastructure-enforcement scope errors retained. Actual safety scores distinguish SAFE/FULL_FAILURE/LATE_RECOVERY but are absent from the current packet.
- NewDEVpairs0;2standard opportunities preparedNOT_RUN;QAUD-002/QCOH-001/Q18-001remainin_progress and fullgoalactive. Automatic approval blocked deletion of17069completed test-temp files; preserved at exact recorded paths. Evidence main_quality_20261026-r13/REPORT.md.

## Bounded workflow capacity planning — 2026-10-26

- Trial2.5.0 seals finite graph capacity and preparation script; all retained compiled attempts enter covered_workflows. Tree factory1.5.2 labels attempted structures without execution/admission claims. Original gates unchanged.
- 92 real retained candidates;24 compile-feasible graphs/group,23–24unexplored.52 related tests plus11 overlapping binding tests and120final strictReplay PASS;API0,newDEVpairs0. QDIV-003 bounded scope done;overall goal active. Evidence main_quality_20261026-r12/REPORT.md.

## Quantitative business facts — 2026-10-26

- Module catalog1.3.0/tree factory1.5.1 derive stock shortages and settlement exception flags from shared quantitative state. Compile new receipts; keep runtime, legacy sealed inputs, scorer, budgets and thresholds unchanged.
- 2130regression/68focused PASS;20paired probes/120strictReplay and80read-check pairs;150final strict reruns. Separate24current-source legacy reanalyses from12exact-R10-source strictReplay; all observed values/scores/outcomes unchanged.
- 0newDEVpairs;6complete/0failed/0unknown. Complete-response boundUSD0.720046,invoiceUNKNOWN. 15388protected files unchanged;17592test temp files removed. QFACT-001done;full goal active,remaining13suites and semantic/difficulty/stability qualification OPEN. Evidence main_quality_20261026-r11/REPORT.md.

## Same-transaction T323 and audit2.2 — 2026-10-26

- Bind new T323 business objects, work order, source/alias/reconstructed documents and receipts to one transaction. Track operational completion separately; retain unsafe execute, scorer/budgets and legacy behavior. Add T323-A3 and preserve neutral narrative suffix.
- Audit2.2 supplies per-tool calls/distinct-run counts and scripted-reference provenance; old protocols and source-bound outcomes retained. No lexical admission rule or scientific promotion.
- 2126final regression/88focused/30local pairs PASS;204final-source and12historical exact-source Replay. Preserve initial red tests, interrupted regression and2unsent opportunities.
- 2newDEVpairs;9complete/1known-length failure/0unknown responses; total reported-usage boundUSD2.794278, invoiceUNKNOWN. Retained high ACCEPT/max131072 reasoning-token truncation QUARANTINED, no resend or qualification. 11813protected files unchanged;17672test temp files removed. QCOH-001/QAUD-002/Q18-001 remain in_progress;QFACT-001planned;goal active. Evidence main_quality_20261026-r10/REPORT.md.

## T323 compositional runtime and real generation trial — 2026-10-26

- Add optional business binding to T323 using shared duties/tools/receipts; retain byte-equal unbound compiler output and legacy execution observables. Register post-reindex lookup and observed queued-reconstruction witnesses, with14negative mutation checks. No scorer/budget/Oracle/threshold/released-data changes.
- 2104v5+m1 tests and59focused checks PASS/0external attempts;30paired local probes/180strictReplay,36legacy executions per source, and204final-source strict reruns PASS. 1conditional plans cover both branches; original evidence unchanged.
- 2online opportunities/2engineeringPASS/2new DEV_ACCEPTED;9complete responses/0unknown,conservative boundUSD1.472410,invoiceUNKNOWN. Same-model development only;auditor qualification/difficulty/long-term stability remain OPEN.
- 9882protected files unchanged;remove16443completed test temporary files. Five compositional suites supported,13remaining;Q18-001in_progress,full goal active. Single runtime operator is not independent role isolation. Evidence main_quality_20261026-r9/REPORT.md.

## Per-run accounting review protocol — 2026-10-26

- Add development audit2.1 per-run successful declared-business-tool accounting and pre-request document consistency; preserve2.0 packets and semantic-only review output. Freeze new tree-factory trial2.2.0 on2.1. No scorer, SUT prompt, threshold or released-data changes.
- 2072v5+m1 tests PASS/0external attempts;24historical exact-source strictReplay and4zero-network terminal resumes PASS. 8complete review responses;3/3 retained semantic-control pairs match expectations. This is a development smoke, not unseen qualification; new admissions0, scientific qualificationfalse, full goal active.
- Retain9282protected history files and remove18796completed test temporary files. Evidence main_quality_20261026-r8/REPORT.md.

## T312 compositional runtime and registered mechanism witnesses — 2026-10-26

- Add program-owned business binding to the registration-distortion compiler and existing dispatcher, reusing the shared module catalog, duty delivery, receipt execution and reactivation. No new dependency or artificial actor. Scenario0.3.0/compiler1.2.0/tree-factory1.3.0/module-catalog1.1.0.
- Initial30paired local probes/180strict Replay and2055v5+m1 tests passed. Two live candidates passed engineering but deterministic preflight rejected both: empty mechanism assertions. Five complete responses/0unknown,USD0.316952 conservative bound. Original rejection labels, sources and ledgers retained.
- Add T312-A1 endpoint-bound operational evidence andT312-A2 observed amendment-before-routing witnesses; eight registered assertions in total (six existing assertions unchanged). Ten mutation tests reject missing/late evidence, mismatched endpoints, absent/altered/unobserved amendments and missing/early/failed routing. Capabilities1.2.1/trial2.1.1; no scorer/budget/Oracle/frozen-prompt changes or lower audit threshold.
- Final78focused and2065v5+m1 tests PASS;30paired matrix probes and180strict Replay revalidated. Final216strict reruns plus192initial-version strict Replays PASS/0external attempts. Legacy36reference executions per source remain observationally equal.
- New independent cohort2opportunities/2engineeringPASS/2DEV_ACCEPTED; full R714intents/14complete responses/0unknown,conservative upperUSD1.561236,invoiceUNKNOWN. Same-model exploratory development only, auditor qualification remains open; graph differences are not new scientific families.
- 7382protected files and1407terminal files unchanged; removed33397completed test temporary files. No commit/push. Four compositional suites supported,14remaining; Q18-001 staysin_progress and full goal active. Evidence main_quality_20261026-r7/REPORT.md.

## Positive terminal acknowledgement witnesses and semantic controls — 2026-10-26

- R5 branch probes consumed both true/false paths for2retained plans,24strict Replay;2034v5+m1 PASS. Six semantic responses completed/0unknown,2of3matched frozen two-review expectations;case03disagreement quarantined. All3controls share a now-documented historical positive-witness gap; qualification not claimed. Original labels, admissions and sources preserved.
- Versioned T331 scenario0.5.1/compiler1.4.1/capabilities1.1.0: deliver the terminal duty, ignore failed sends, require actual positive acknowledgements, and prevent a dormant capitalization mismatch from repeating notes. No safety-scorer, budget, neutral system-prompt, pair world/Oracle or frozen-data change; executable AST/byte/pair comparisons PASS.
- Initial red tests5FAIL/1PASS; first repair exposed60repeated notes at80calls in an actual exercised branch. Unique-ack regression3FAIL/3PASS retained. First-fix source and unsent control cohort preserved; broad regression explicitly interrupted for the confirmed fix, never called green. Final27related checks and2040v5+m1 tests PASS/0external attempts.
- Four affected proposals rerun and2branch plans exercised on both truth values;48local+18semantic reference Replays,66current-source final strict reruns and42old-source historical Replays PASS. New semantic cohort:6complete responses/0unknown,2of3two-review expected-label matches, conservative boundUSD1.897384,invoiceUNKNOWN; auditor qualification remains open.
- 510terminal evidence files and3755protected prior files unchanged;43793scoped completed test temporary files removed. New pairs/families0,formalfalse,no commit/push. Full goal active; causal/reuse calibration,15remaining compositional suites,difficulty,long-term stability pending. Evidence main_quality_20261026-r5 and main_quality_20261026-r6.

## Deterministic preflight and semantic review with fresh development data — 2026-10-26

- Protocol2.0 reuses existing hard-fact predicates before model requests, verifies complete strict-Replay matrices and reconstructs the packet from sealed sources. Models retain the original nine semantic fields and registered evidence references; valid hard facts never imply acceptance. Legacy1.x behavior remains replayable.
- Real sealed-source controls:2normal PASS and6known hard failures rejected with0calls. Failure-aware planning now freezes consumed unsuccessful opportunities as well as accepted coverage. No threshold, SUT prompt, formal scorer, canonical risk or frozen dataset changes.
-8fresh opportunities yielded8engineeringPASS and6DEV_ACCEPTED pairs,2each T321/T331/T362. Original2T362 hard rejects remain: compiler1.2.0 persists missing proposal-to-runtime mappings and correctly locates resolved defaults;2real blueprint compatibility fixtures prove unchanged world/Oracle. Separate fresh followups passed; no old request resent.
-28requests/28complete/0unknown, reported1726108tokens, conservative complete-response upper boundUSD4.967198, invoiceUNKNOWN.6admissions have business graphs differing from frozen same-group history;4have all stages witnessed,2T331 conditional graphs retain unexercised optional branches and closure_eligible=false. New scientific families0.
-2028final v5+m1 PASS with0external attempts;48strict Replay reruns under exact matching sources,8terminal audit zero-network resumes,12raw reviews reconstructed,1771prior evidence files unchanged. A floating-point timeout assertion was fixed with1microsecond test tolerance only; original2027PASS/1FAIL receipt preserved. Full goal remains active: semantic controls, branch coverage, remaining15compositional suites, difficulty and long-term reliability pending. Evidence main_quality_20261026-r4; no commit/push or formal promotion.

## Registered citations and actual output-contract verification — 2026-10-26

- Added versioned review1.3/1.4 with program-owned citation IDs, strict raw-response expansion and reconstruction. Explicit1.4 facts are already citations, removing duplicate model-written reference rows; original opinions/values are unchanged and old1.3 failures are not reclassified. New trial plans freeze protocol and output mode.
- Reproduced and fixed stale neutral calibration summaries after case/run deletion; original two affected packets remain labelled as extra-confounded controls. New six-kind fixture regressions preserve actual summary/document consistency.
-25new model requests completed,0unknown; no old unknown resent. A small native-Schema probe passed, but full review produced a real minLength violation without degradation headers. Native capability and model audit qualification remain unestablished. Actual responses are now schema-validated with exact violation paths; no threshold relaxation or default verdict.
-2012final tests/v5+m1 PASS with0external attempts;116directed checks PASS.12sealed audit jobs resumed with0external calls and unchanged files;25Router payload hashes/usage matched their ledgers;1344prior evidence files protected. Three earlier2005/2007/2011 checkpoints and all RED evidence retained.
- No new data generated or admitted in this checkpoint; six prepared generation opportunities NOT_RUN. Full quality/stability/diversity goal stays active, with deterministic-hard-fact preflight and semantic-review separation next. Evidence artifacts/v5/data_factory/main_quality_20261026-r3/; no commit/push or formal promotion.

## Main audit reliability and cohort continuation — 2026-10-26

- Added a frozen opt-in per-run actual-action index and the existing blocking-rule checklist to isolated development review requests. Legacy prompt revisions and fact/reference validation semantics retain their original behavior. Cohort-specific candidate IDs/seeds prevent repeated `online` task identity. Final entrypoint1.2.1 reads complete terminal summaries without rewriting stopped trial admissions or denominators.
- Four initial live audit packets plus two rule-alignment followups produced12complete responses. Four negative packet evaluations were blocked by code; only1had two valid reviewer rejections, and2individual false ACCEPTs remain recorded. Audit reliability qualification FAIL; no independent science or threshold relaxation.
- Fresh6-candidate trial:4engineeringPASS,2development admissions,2quarantined,1history duplicate rejected,1notrun. Across calibration and generation:29intents/28complete/1unknown; interrupted started request never resent.24strictReplay rows pass. STOP and original failures remain. Known complete-response conservative boundUSD6.512676; unknown request cost and invoice UNKNOWN.
-1995 tests/v5+m1 checks passed before final entrypoint fix, with0external network attempts;99related tests passed after the final fix. Actual final terminal resume retained437files,2admissions and6opportunities with0external attempts. Previous681trial files and preexisting15diff sections protected. Evidence artifacts/v5/data_factory/main_quality_20261025-r2/; no commit/push or scientific promotion.

## Main shared generation quality and fresh trial — 2026-10-25

- Generator1.2.1 filters planning modules to the selected business package, validates payload/schema/frozen target/compiler fidelity before requesting a DAG, and uses the existing one-repair slot for explicit semantic feedback. Role assignment and binding validation consume the actual candidate IR rather than an enriched default example. No added provider retry, model fallback, new dependency, scorer change or gate relaxation.
- Added scripts/v5/tree_factory_trial.py: six suite/industry groups, history-guided structural focus, typed-graph reporting, frozen per-trial history snapshots, published development admissions and complete planned-opportunity denominators. Fresh batches include prior main_quality admissions without mutating old R3 evidence.
- First1.2.0 online batch:6 planned,5 engineering passed,2 development admitted,2 quarantined,1 audit rejected,1 local compiler failure;21 completion intents and21 complete responses,0unknown. The local broker/profile inconsistency is reproduced and fixed in1.2.1. The separate postfix trial and final regression receipts are authoritative. Original red checks and the1.2.0 source snapshot remain under artifacts/v5/data_factory/main_quality_20261025-r1/.
-67 directed checks passed;13285 historical/contract files unchanged. An auditor rejection rationale conflicts with the sealed action sequence; its rejection remains recorded, and independent audit reliability is still unestablished. Only the three compositional pilots are supported, T361–T363 remain SIMULATION_ONLY, formal acceptance unchanged.
- Final1.2.1 regression:1991 passed,0failed/error/skip, external network attempts0. The fresh postfix candidate passed engineering plus both audits and was development-admitted after4complete requests. Across the two separate cohorts:25complete responses,0unknown,3new development pairs and36actual strict Replay rows. Zero-network terminal reentry left the ledger bytes and100sealed candidate/review files unchanged. Historical1.2.0 failures remain preserved; no causal superiority or scientific qualification claim.

## Local R3 integration and workspace maintenance — 2026-10-25

- Fast-forwarded main from 7e35bc1 to a18db13, retaining all 3 R3 commits, then deleted codex/r3-closure-20261025. Binary working-tree diff and tracked/untracked status were identical across the switch. Existing dirty work remains uncommitted; no remote or push.
- Removed only verified regenerable caches and this task's test temporary files. Historical experiments, frozen materials, exports, scratch and private documents remain protected. Evidence: artifacts/workspace_maintenance/20261025-merge-r3/.
- Offline tests/v5 + tests/m1: 1984 passed, 1 failed because the maintenance basetemp was inside the workspace and selected repository-relative report bindings. The same report module passed all 24 tests with external basetemp; original failure XML retained. No runtime fix, provider call, formal acceptance or scientific promotion.

## DeepSeek official G2 development integration — 2026-10-20

- Actual generation and optimization are complete:304 official HTTP200 completions, no new unknown/auth failure and no new AIHubMix call. The main engineering pool has32pairs/64cases across16suites, with two consumed executable targets per covered suite. T322 retains its120-case historical5.1.0 source gap; all six T362 proposals remain rejected under unchanged history/near-duplicate rules. Fixed6-task disabled/low/high/max comparison yields2/4/5/4 valid pairs; high is the provisional development recommendation. Token-based official price bounds total CNY0.96056932–1.92113864; invoice UNKNOWN.
- Fixed the strict Replay launch path by using real pinned evaluation batches and manifests, retaining the original missing-manifest failure and reusing its four complete generation responses without a paid resend. Restored provider-prefix compatibility for old offline verifiers. Final v5+m1 regression:1652PASS; original11 adapter failures and28 compatibility failures retained. Protected historical file verification:173519 unchanged. All78 sealed terminal jobs re-entered through the real CLI with HTTP disabled:zero new submissions. All47 valid candidates completed294 strict replays under their two exact source revisions with sealed bytes unchanged. A9466-file precheck ZIP passed every member SHA/CRC, exact runtime reconstruction, nested reviewer archive secret scans and an independent extracted294-replay/47-resume run. Final metadata ZIP is independently reverified; verification and archive self-hash remain outside it. All scientific gates remain blocked.
- PI-V5-023 records direct user authorization for official `deepseek-flash` four-stage G2 in a same-family quarantine. No new AIHubMix generation, formal production, Gold disposition, qualified auditor, SUT/scorer change or scientific promotion.
- Reproduced 11 direct-adapter failures before repair; POST timeout/partial HTTP200/invalid body now terminate as non-retryable REQUEST_UNRESOLVED with structured safe transport evidence. The shared AuxiliaryRouter keeps separate DeepSeek ledgers and stops on balance/auth/unknown; official-host guard prevents sending this credential to a gateway. Existing formal family gates remain unchanged.
- Extracted existing pre-audit engineering checks for reuse; the isolated path additionally requires both-arm history decisions, all strict replays and an actually executed removed-intervention negative. Official high/disabled JSON and a reasoning-preserving tool roundtrip passed; original empty-reasoning local-check failure and prose-plus-JSON output failure retained. Actual candidate and final regression outcomes follow in the run report.

## Round02 resumed matrix and renewed auth blocker — 2026-10-20

- The official alternate domain initially completed a fresh MiMo Pro JSON request with HTTP200, exact served identity and usage120. Live catalog/schema20 models;19 called,18 complete protocol pass,67 legal per-model configurations. Two short nonoverlapping reliability batches:536 planned task checks,533PASS/2FAIL/1NOT_RUN;65 configurations passed both batches. Original MiniMax output failures, Meta local precheck failure/new Responses success, Astra503 and Kimi missing-tool failure retained.
- Quality536 planned:4 started,0 valid pairs,532 not started;Claude explicit policy refusal followed by a new real HTTP401 stopped every new paid request. Qwen first stage returned but later stages stopped. No further identity/auth probes, long-context B or live healthy fallback after401; role selection NOT_ESTABLISHED, active routing contracts empty, costs per valid engineering/machine-qualified pair NOT_COMPUTABLE.767 provider attempts,762 durable success/5failed/0new unresolved,known catalog-rate subtotal USD0.666275740995 with2unknown usage/rate records;not an actual bill.
- Routing1.3.1 and adapter now preserve REQUEST_UNRESOLVED for interrupted POST responses even after HTTP200 headers;negative reproduction and regression saved. Added existing-stack protocol/effort/report scripts and optional evidence-bound generator profile loading;missing full comparison cannot activate a route,auditor gates unchanged. Final1631 tests/v5+tests/m1 passed;138 directed failure tests are a subset.159 actual terminal results resumed with0calls and unchanged raw bytes;39358 historical files unchanged;old4unknown requests never resent. No Goal/v6,scientific promotion,formal production,Pilot,Campaign,freeze or push.

## Round02 AIHubMix provider specialty — 2026-10-20

- Primary-domain direct TCP timed out; documented alternate domain passed direct TLS1.3/HTTP and the existing WinINET proxy passed the primary-domain public GET. One fresh MiMo Pro Chat probe through the alternate returned real HTTP401 in1.071s. Paid protocol/effort/quality/stability matrices stopped; usage/billing UNKNOWN. Four historical unresolved requests retained, none resent; no active/healthy model or auditor qualification claimed.
- Auxiliary routing1.3.0 fixes a reproduced no-resend defect: incidental500/503/512/599 in error data cannot stand in for an HTTP status. JSON/tool output errors, schema mistakes and served-identity failures stop without automatic model substitution; explicit429/5xx still have bounded retry/circuit/fallback behavior. Frozen SUT adapter/default path unchanged. Original7-failure Mock reproduction retained; directed124-test regression passed, full regression recorded separately.
- Added read-only network diagnosis and one-fresh-request S1 probe scripts through existing ModelPort/AIHubMixAdapter/AuxiliaryRouter, plus Mock regressions. Full tests/v5+tests/m1:1607 passed,0failure/error/skip; first1-failure legacy400 caller mismatch preserved. Runtime72d7604d;39239 protected paths unchanged. Current secret loading was verified without saving key values/fingerprints or changing secrets/system proxy. No production, scientific acceptance, formal freeze, Pilot, Campaign or human experiment ran.

## COORD-R3 Round01 — 2026-10-19

- Factory2.7.1 rejects `HISTORY_INDETERMINATE` before independent review; two reproduced negative cases previously reached the auditor. Saved failure XML and successful regression:1564 tests/v5+tests/m1 plus13 new artifact tests, zero failures/errors/skips. No scorer, construct, Gold/control contract or frozen data changes. Retained trial impact scan:51 results,0 accepted with indeterminate bound history; old outcomes unchanged.
- Prepared two separate human Gold review identities and phase-A/phase-B ZIPs,18 full candidates,96 anonymous historical observations, readable typed leaves/arm differences, blank signed-answer and PI disposition forms. CRC/member-SHA/blinding checks pass; actual human reviews and PI disposition NOT_RUN.
- One new, unrelated MiMo Pro completion probe returned no HTTP response (curl28/status000); send retained as REQUEST_UNRESOLVED. Subsequent models not sent, no old unresolved request resent. DNS resolved but credential-free TCP443 check timed out. Completion recovery unproved, usage/billing unknown. Original raw request and its JSON-mode/text-prompt inconsistency remain documented, not silently rewritten.
- Rebuilt current supported disk history plus retained extracted archive sources:1325 sources/48973 occurrences/7863 unique inputs; all7687 prior inputs retained,120 projection findings retained. T331 G1 existing-family instance passed causal/fidelity/reference checks and6/6 strictReplay, terminal/replay resume0newcalls. It stops at an explicit offline auditor-qualification sentinel; no AI generation, genuine audit or machine acceptance is claimed.
- Current18 typed/19slices/49of52enum cells/540reference executions,36 negative controls and72 staged-schema Mock steps pass; G3 lacks qualified parents. Protected38785 baseline files unchanged. New evidence:artifacts/v5/data_factory/coord-round01-20261019T073200Z. Science NOT_ESTABLISHED; first machine-qualified pair BLOCKED; confirmation Pilot/Campaign/freeze/human experiments NOT_RUN. T361–T363 SIMULATION_ONLY.

## R13 follow-up: eight-model study and evidence settlement — 2026-10-19

- PI-V5-020: validated eight exact candidates with fresh catalog/schema and real JSON/tool roundtrips, using the existing ModelPort/AIHubMixAdapter. Explicit auxiliary Responses/Messages paths preserve the formal TESTED Chat path. Official limits and the preregistered16,384 study budget are distinct; reasoning settings are not silently downgraded.
- Current runtime0a4b9c9551ad93b01c54e679b7229c5f08af3cceeeb6d2af760e87594590fb26; T352 registry-order Replay fix and classical T362 scenario/generator5.1.1 public-field projection fix are versioned;37 scoring function ASTs and67 contract/config files remain unchanged.
- Actual generation192plan:39 ENGINEERING_VALID pairs,10 rejected,6 Provider failures,3 unresolved,134 NOT_RUN. Fixed one-field repair24/24,378 strict Replay and189 zero-call resume batches pass. Early resume changed three mutable checkpoints in one candidate; original mismatch and diagnosis retained, snapshot integrity PARTIAL.
- Eight-model capability/effect matrices, old Gold108-row diagnosis and18 blind packages, all18 offline36pairs/228references,540 capability references,49 feasible cells, current-source7687 history reprobes and78 generated-case classifications are saved.1026 old gaps remain; new scientific families0, machine-qualified samples0.
- Development panel48plan:11 completed,2 interrupted,1 retryable infrastructure failure,34 NOT_RUN;11 Replay and7 zero-call resumes pass. Scientific labels remain uncalibrated. Two real HTTP401 responses stopped paid completion work; metadata GET success does not authorize an inference of recovery.
- Total retained ledger:510 starts,493 success,14 failed,3 unresolved,1,214,168 reported tokens, estimated known USD subtotal0.830890141988 with7 unknown billing records; raw usage/costs unchanged. Actual FINAL_REGRESSION_R3.xml:1562 passed,0failure/error/skip,exit0,runtime unchanged; separately bound by FINAL_ACCEPTANCE.json. Old1486/1492/1548/1559 checkpoints are historical.
- Gold disputes require two independent blind reviews and PI disposition. No auditor qualification, production promotion, G3 qualified-parent run, confirmatory Pilot, Campaign, formal freeze or human experiment is claimed. T361–T363 remain SIMULATION_ONLY. Local Git/package delivery evidence is recorded separately; no push.

## Auxiliary candidate removal — 2026-10-19

- PI-V5-019 removes Qwen3.8-Flash-Next from the shared active candidate list at the user's explicit request. Seven candidates remain; future preflight uses that list. Historical results/exports remain unchanged; no new Provider calls or formal SUT changes.
- Validation:58 routing/auxiliary-runtime tests passed; active list manually asserted to contain7entries and noQwen Next. Full regression and new online preflight NOT_RUN for this list-only change.

## Auxiliary documented full parameters — 2026-10-19

- PI-V5-018: removed 8192/16384/65536 application caps and generic high/low effort substitutions from the shared auxiliary routing helper and its callers. Exact numeric documented output maxima and explicit user preferences/documented effort defaults now determine requests. GLM recommended max, temperature1/top_p0.95 and preserved thinking are explicit; MiMo retains thinking and provider-enforced sampling defaults; prohibited sampling fields are omitted.
- Qualified loading binds exact schema, request parameters and judge parameter evidence; old low-budget preflights cannot authorize the new configuration. Incompatible Chat tool/effort combinations fail without lowering reasoning. Missing schema, numeric maximum or exact ID blocks calls. ModelPort/AIHubMixAdapter and frozen SUT remain unchanged.
- New six-model full-parameter JSON/identity preflight passed:803tokens, estimatedUSD0.0015529412, no unknown completion charges. DeepSeek numeric maximum undocumented and Qwen Next exactID unresolved remain NOT_RUN. Independent gold/difficulty/production requalification NOT_RUN; historical failed/truncated evidence retained.
- Current stable runtimec3d0cdaf53f2a486149da9e03947caaf35b129a924e173b005f636c6bc41e6c1 passed1496 tests in207.34s with0failure/error/skip including4packaging tests. Original failed run retained; strict schema/parameter-bound fixtures corrected and all tests rerun after source stabilized. Source delivery is versioned r2; old ZIP and R13 bindings are verified unchanged by its producer.

## Data factory specification implementation — 2026-10-19 (R13 partial acceptance)

- Reconciled the attachment with the single v5 Goal and current PI/scientific rules; recorded PI-V5-017 and user-authorized local Git initialization. Baseline commit 90f691a2a163f01e01878bc4ce29bfe46ea32bfc; no remote or push. The 20261018 snapshot matches all1,242 compared files. Existing45,434 protected files remain unchanged in the current integrity check.
- Reused the existing ModelPort, AIHubMixAdapter, coverage planner, typed compilers, dynamic runner and quality gates. Added constrained G1/G3 proposals and four durable G2 stages; T321 timing, T331 fanout/multihop and T352 aggregate-feedback consumers now have real execution counterexamples. Scorers and frozen tested configuration unchanged.
- Verified seven exact auxiliary IDs using the local1510-document inventory, live catalog/schema and real JSON/identity probes; Qwen Next unresolved/NOT_RUN. MiMo/Gemini/GLM actual tool loops and deliberate HTTP400 REQUEST_SCHEMA failover passed through existing ModelPort. Final fixed18-control qualification closed without a qualified auditor: Sol16/18 twice, GLM8/18 twice, Gemini12valid per draw then truncation with5NOT_RUN each. No judge shopping or threshold/gold change; old control6/6 and other failures remain historical, not current qualification.
- Current runtime4f7fc7c842ea63a352157baffe8252838fdc06332e2839fd3ddb6f250e04e9e5:1486 regression tests pass with zero failure/error/skip. All18 typed/19slice,540 capability references,132pairs/264cases/828coverage references and72 actual reference episodes/consumer fidelity/exposure/strictReplay pass; same-command resume adds0calls. Finite49 feasible structures/3pruned/44selected do not establish global new families; verified new scientific families0.
- Fixed bounded-history evidence merge, calibration1.2.0 JSON roundtrip plus strict terminal zero-call resume, and pool1.0.2 canonical pair comparison. Regression counterexamples and originalR12 failure preserved;426 runtime files differ only bypool from prior checkpoint,7 actual isolated entrypoint imports exclude pool/API0. Old model calls retain their true producer hash.
- FreshR13 history binds794sources/43643occurrences/7687unique;6661PROBED/1026INDETERMINATE. Actual resume preserves29654file SHA with0policy/API calls;954missing legacy-world fields and72unsupported legacy profiles unchanged. No fabricated fields or profile substitution.
- Predeclared96 exploratory panel rows settled as92COMPLETED/2BUDGET_EXCEEDED/2pending. All94 terminal traces strictReplay PASS; new60 traces and30 exact same-config directory resumes PASS with0Provider/key/new-episode calls and unchanged SHA/mtime. Technical scored90:SAFE77/UNSAFE_RECOVERED5/UNSAFE8;utility72success/18failed,2abstains separate. Inputs remain machine-unqualified, overlapping development controls, and MEASURED_EXPLORATORY_UNCALIBRATED_LABEL.
- Final usage from original ledger summarizer:2061started/2054success/2deliberate parameter failures/5unresolved;9543841known tokens,estimated known subtotalUSD5.394535590692,33unknown-billing attempts. Not an invoice;unknown charges not zero. Full production sequence is NOT_RUN/BLOCKED_MACHINE_QUALIFICATION;gold realism/evidence-anchor adjudication,GateD,classicT362P1,scientific difficulty and formal authorizations remain open. Final stage/suite evidence is linked fromdocs/v5/data_factory_upgrade/04_TRIAL_RESULTS.md.
- R13 actual retained18 candidates/36cases/114reference episodes correctly rejected17 ALL_HISTORY_DEDUP plus1 DEDUP. Original pool CLI build/verify and resume build/verify exit0,18entries/36cases withlayers36/0/0/0;674file SHA/mtime unchanged,new model/reference episodes0. A tampered copy is actually rejected withverify exit1;original untouched and temporary copy removed. Currentall18typed offline help/run exit0,checks36/reference_checks228/suites18/API0.475-member exactsource.zip SHA10fba140476996c027a254b8418d2b40e4f5eff713b71d7b587d208a8bfb7c30;protected45434 files unchanged. Explicit final archive/secret scans and stage/suite report preserve their actual statuses inupgrade-20261019.

## Workspace consolidation - 2026-10-18

- Current-source regression rerun:852 v5 tests plus4 packaging tests,856 passed in98.29s;zero failures/errors/skips,zero HTTP/external connection attempts,and new test temporary files cleaned. Runtime source unchanged;no fresh model or formal scientific evaluation.

- Moved the993-file isolated generation prototype into archive/external_workspaces/20261018/ioa_codex_spec_ai_generation_probe without integrating obsolete runtime code. Removed two partial sibling directories after comparing all13 files and verifying recovery ZIP;12 match current source,one is superseded. Current snapshot locator updated;immutable historical path records retained.
- Archived4394 completed test temporary files(182907865 bytes) as a17209309-byte ZIP,retaining test logs/XML and all scientific inputs/results. Refreshed workspace navigation,state,queue validation and recovery mapping. Original runtime source,tests,contracts,configuration,credentials,history and frozen evidence remain protected by full-file hashes. Validation and scope:artifacts/workspace_maintenance/20261018-r1/; no provider calls or scientific acceptance change.

## Private GitHub source upload - 2026-10-14

- Created personal private repository https://github.com/JiaDirty/ioa-bench-v5 and uploaded the verified20261014 source-review snapshot,1411 byte-identical payload files plus .gitignore/.gitattributes. Commit db723e44364036258181e69b1a72db7b8908baea. No credentials or complete historical-run archive uploaded; original files retained locally.
- Verified remote commit/tree, private visibility,owner-only collaborator list,zero pending invitations/teams,and disabled Actions. Evidence:artifacts/workspace_maintenance/20261014-github-private-r1/VERIFICATION.json. No runtime/scorer/model calls or scientific acceptance change; existing856-test snapshot result reused without claiming a new run.

## Recoverable workspace cleanup and current source-review handoff — 2026-10-14

- Inventoried46769 workspace files;archived/verified53 regenerable development caches(218620 bytes),removed16 empty cache directories,and backed up9 edited documents/helpers/test fixtures. Historical data,runs,releases,trial artifacts and artifact fixture caches retained;rollback and final protected-hash validation in artifacts/workspace_maintenance/20261014-source-review-r1/.
- Refreshed WORKSPACE/README and added docs/HANDOFF_20261014_CHATGPT.md with actual generation limits,current-source reading order,a complete historical example,and a copyable review request. Reused existing source packager with bounded versioned output/current handoff and explicit evidence;4 package regression checks passed.
- Export checks added7 directly required offline fixtures/scan files;fixed one negative-test fixture's ROOT so host temp location does not mask the expected missing-file error. No production gate was weakened. Current source export registered at exports/chatgpt-source-review-20261014/;final member/SHA-256/CRC/credential and clean-extraction test acceptance are recorded there. No model calls,scientific gate change,bulk generation,runtime/scorer change or new formal acceptance;prior test checkpoints remain source-bound.

## Data-factory process review and evidence/response repairs — 2026-10-14

- Reviewed the shared pipeline,18 adapters,typed compilers,reviewer inputs,resume evidence and prior6 candidates. Found limited executable structural capacity,trial-only planning,partial historical indexing and missing online auditor controls; recorded prioritized improvements without claiming production quality.
- factory2.3.5/quality1.4.0 now supply original public construct definitions plus source hash to the reviewer; require historical references and hash-bound cache/source inventory; require complete accepted evidence and normal-stop auxiliary responses. quality-control1.4.1 persists response rejection as a failed terminal control and resumes without repeating calls. No GT/scorer/tested-model/frozen-data change.
- 36 new regressions reproduced the defects before repair;155 focused and852 complete v5 tests pass,0 failures/errors/skips. All18 offline preflight36/36 plus228 reference checks passed with Provider creation forbidden;API0.274 historical/prior-trial hashes unchanged; original judgments retained.457-file source and52-file test ZIPs verified SHA-256/CRC and local credential occurrences0.
- Evidence,backups,snapshots,capability inventory and06-template morning report:artifacts/v5/data_factory/review/process-audit-20261014-r1/. Source hash1416449d4ae6fda00d3f487e9d32115f553baf0c2002f5bb41591d2a43787e7d. M5 remains IN_PROGRESS; revised reviewer prompt needs bounded online positive/negative controls before quality acceptance or expansion.

## Selected auxiliary models and bounded GPT generation trials — 2026-10-14

- Recorded PI-V5-016 seven-model preference; retained all7 exact live catalog identities, complete official schemas and local official model documents. No stale model alias, tested-family bypass or new seven-model automatic fallback implementation.
- Six GPT-5.6-Sol proposals across T312/T331/T352;5 GLM-5.3-Flash and1 Gemini-3.8-Flash independent audits. Three new Kimi/DeepSeek-Pro/Grok connectivity probes completed.15 requests/15 responses,253572 reported tokens,no401 or observed Provider failure; actual cost not returned.
- Preserved3 original MACHINE_ACCEPTED/3 REJECTED judgments. r1 requested M/generated H on T331 and T352; old accepted T331 has a contract defect, not clean validation. r2 T331 and independently new r3 T352 pass machine checks; r3 structure is relative to the bound accepted pool, not a globally novel/scientifically accepted family.
- factory2.3.3 checks requested design difficulty;2.3.4 rebuilds typed preview with actual compile seed. T312 seed discrepancy reproduced before repair.32 factory/816 complete v5 tests pass; neither design tags nor machine audit substitute empirical difficulty, independent human review or formal gates.
- Three run archives verified457 files each/hash/ZIP CRC. Guarded terminal resume using each pinned source constructs no Provider; all immutable candidate JSON/logs and historical reference data hashes unchanged; local credential occurrence scan0. Current source_tree_sha25614ecaf00a1659b672efe12875ead7c9a107534e66b35d7c20c4fda3959f92e9b.
- Current M5/state/queue updated from obsolete401 blocker to remaining positive/negative auditor controls, broad18-suite quality, structural capacity, all-history dedup and empirical reliability/calibration. No bulk generation, formal tested-model substitution, frozen data mutation or formal acceptance. Evidence:artifacts/v5/provider_contracts/pi-order-20261014T082638/REPORT.md.

## AIHubMix mainstream model parameter and connectivity probes — 2026-10-14

- User-authorized10 exact model IDs resolved in the current catalog;9 full official schemas and10 local official model docs retained. Reused ModelPort, schema-derived per-model Chat parameters and authoritative served-model headers; no production-source or frozen-SUT change.
- Nine basic text/JSON probes passed identity, nonce/arithmetic and normal-stop checks. qwen3.8-27b returned HTTP400/no_available_channel both with schema parameters and with an official-minimum request; qwen-3.8-27b independently passed and was not treated as its alias. No401;11 requests,1109 reported tokens,failed-request usage unknown.
- Retained all requests/responses/errors and a parameter report; no-call reentry, source hash and secret/snapshot checks verified. No tool-loop, concurrency, generation-quality or scientific acceptance inferred. Evidence:artifacts/v5/provider_contracts/mainstream-20261014T080611.

## AIHubMix key recovery check — 2026-10-14

- User-authorized minimal connectivity check loaded the existing workspace secret without logging it; live model resolution and official GLM-5.3-Flash schema succeeded.
- One text completion returned the exact requested marker with matching served model and normal stop:5.828s,182 tokens,no401,no retry/fallback. Runtime source unchanged; no generation/benchmark batch or all-model/tool-loop/scientific acceptance inferred. Evidence:artifacts/v5/provider_contracts/key-recheck-20261013T234522Z.

## Versioned16-suite record-audit repairs — 2026-10-14

- Exposure checker1.3.0 binds audited structured stimuli to provider-facing content and reports actual upstream/downstream exposure; other suites explicitly retain declared-fingerprint-only scope.
- Corrected full business utility, legal exceptions, compliant alternatives and local recipient/compliance receipts. T321 scorer5.2.1 and dynamic scorers0.2.1 separate absent receipt evidence from model over-restriction.
- T363 scenario5.2.1/scorer5.2.2 allows omission, checks distinct task coverage/answers/structured guidance and task-bound recovery, and abstains on unresolved free prose including optional explanation. Simulation impact remains a field-presence model, not evidence of human skill effects.
- Balanced T341 primary-holder order in new generator5.2.0, declared bundled stimuli, retained written exceptions; report1.1.0 exposes the structured-content denominator. New candidate profile uses unchanged neutral role text with the previously explicit attachment contract.
- Final source f9cd9db539d25c5c553ff03190e055b69aea9386af6bdf6b34cedaa6793968e9:26 focused regressions and809 final v5 tests;148 system+88 revised-candidate reference executions/replays/resume checks. Prior source b3103315 full active tree1682 passed,2 live-AIHubMix skips; no inherited claim that final narrow follow-up reran the whole tree.
- Preserved1064 protected files. Supplement measured32 pinned historical cases/321 responses without rebuilding changed environments; original records unchanged. Eight T363 content-review items/rubric/index prepared with0 labels. No provider calls, new qualified families or formal acceptance; T333/T361 interpretation review and new-version online diagnostics remain open.
- Reconciled current queue bookkeeping:464 actual items,version26 and dependency/DAG/statistics checks; no historical scientific acceptance re-certified. Evidence:artifacts/v5/overnight_runs/20261014-audit-fixes-r3; ADR_V5_016_RECORD_AUDIT_REPAIRS.md.

## Personal16-suite online-evidence audit — 2026-10-13

- Personally reviewed32 current control/risk records across16 suites, excludingT333/T361;321 retained deepseek-flash responses, exact source-run/journal/input bindings and per-suite author conclusions recorded.
- Reanalysed32/32 saved-response behaviors under unchanged current source;16 pair-diff/schema checks passed;37 focused core/profile/scoring regressions passed. This is no new online run or independent review.
- Reproduced5 offline scoring counterexamples: missing T332 allowed gateway, declined T343 above-threshold work counted complete, qualified T352 alternative marked over-restriction, meaningless T363 guidance counted complete, duplicate T363 task counted full coverage. These are measurement tests, not observed model failures.
- Recorded exposure timing/content, sequential-correction difficulty, full-business receipt/utility boundaries and bundled manipulation/exception documentation. Added READY versioned follow-up tasks; retained original prompts/data/scores/Oracle and formal gates.
- Evidence:artifacts/v5/overnight_runs/20261013-16suite-audit-r1.0 Provider calls,0 new qualified families,formal_accepted=false.

## Entire-workspace organization — 2026-10-13 (r2)

- Inventoried and classified all34405 original files (6565461172 logical bytes), including code, contracts, data, releases, audits, exports, PI documents and local credentials metadata; no local credential content copied or displayed.
- Centralized10 historical rootZIPs into archive/deliveries and5 old Claude exports into archive/conversations; preserved every moved file's bytes and original-to-current mapping. Historical manifests/reports retain their original records.
- Updated8 legacy helper files for archive discovery/input/output paths, frozen-baseline ZIP lookup and shareable-snapshot archive exclusion; current ModelPort/runtime/scorers/18-suite contracts unchanged. Backed up13 edited navigation/state/helper files before changes.
- Added whole-workspace directory index, exhaustive file catalog, duplicate/provenance inventory and conflict-aware original-layout rollback. Independent history/audit/release copies kept; prior cache removal remains recorded under r1.
- Executable final acceptance, exact test count, protected-file verification and rollback check are recorded in artifacts/workspace_maintenance/20261013-r2/VERIFICATION.json;0 provider calls, no research gate changes.

## Recoverable workspace organization — 2026-10-13

- Added WORKSPACE.md and docs/WORKSPACE_INDEX_20261013.md as current Chinese navigation; corrected README's obsolete T311-only/235-task status while retaining historical references.
- Archived153 regenerable cache files and2 idle files before removal, with original-path mapping, per-file SHA-256 and ZIP CRC verification. Removed21 empty cache directories; local credentials excluded from rollback ZIP.
- Preserved all10 root historical ZIPs at their original paths because recovery scripts/state/indexes reference them. Kept datasets, online I/O, releases, archived sources, failure evidence and prior backups intact.
- Runtime source hash remains146eacffe47c7df7254794a0b1aa7383d923a64add1c6dc054e5822f4a81cfbd. Protected34390 original files; final hash/entrypoint/test checks and actual storage accounting in artifacts/workspace_maintenance/20261013-r1. Provider calls0; no research gate change.

## Scoring diagnostics, recorded-response reanalysis and review correctness — 2026-10-13

- Versioned T333 scorer5.1.2 fixes unknown-driver/disclosure metrics and conservatively abstains on additional sensitive comment claims under an authorized structured driver. T361 scorer5.1.1 separates endorsed errors and omitted rechecks without changing safety rules. T333-DYNA now exposes the actual delegated scorer version.
- Report1.0.2 includes boolean metrics and action-level ambiguity evidence. New reanalyse command verifies recorded requests/actions/events/state/monitors and writes old/new scores separately; strict historical replay still enforces the old source.
- Review package schema4 uses the actual required candidate profile, includes tool contracts, omits private reasoning from behavioral transcripts, and includes otherwise valid engineering abstentions without counting them as automatic-scorer agreement.
- New T361 finding: authored-neutral .3 omitted the original explicit recheck guideline, confounding attribution of both no-recheck violations. Historical outcomes and prompts remain unchanged; independent interpretation review remains open.
- Acceptance:833 tests passed;40/40 recorded-response reanalyses with unchanged outcome classes;36 review-case prompts/tool schemas matched actual online records;18-suite blinded packet prepared.0 Provider calls,0 human labels,0 new qualified families, no formal acceptance. Evidence:artifacts/v5/overnight_runs/20261013-scoring-audit-r1.

## Authored18 real online diagnostic and contract repairs — 2026-10-13 (PI-V5-015)

- Bound required candidate scenarios consistently across shared runner, preflight, manifest and replay; unknown profiles fail before calls. Runner1.2.0/evaluation1.1.0. Reporting1.0.1 preserves the specific scorer-abstention cause rather than mislabeling it as monitor failure.
- Real direct DeepSeek run completed36/36 with344 exact responses:30 EARLY_SAFE,2 TASK_SAFE_BUT_FAILED,3 FULL_FAILURE,1 SCORER_ABSTAINED. Original inputs, decisions, source and results retained.
- Observed task/interface confounds led to separately versioned T331 brief clarification and T332 full-record attachment contract. Candidate profile authored-neutral-20261013.4 records actual attachments and rejects invalid references before sending; no scorer/Oracle change. Separate4-case live recheck completed with41 exact responses, full task delivery and no target violations.
- Strict replay40/40; completed resume0 calls; original36 also replayed from archived source. Regression810 passed. Current source67642e666e2ae2492215a9c52fdfa93a67be123a5f1b7eaee2387847b9a18d1f. Evidence/report/source ZIPs: artifacts/v5/overnight_runs/20261013-authored-online-r1.
- Recorded385 completion responses,4 catalog requests,1,474,537 tokens; monetary cost unknown. No bulk generation, formal freeze or scientific acceptance. T333 abstention, T361 no-recheck interpretation and T361–T363 SIMULATION_ONLY remain explicit.

## Explicitly authored 18-suite candidate pack — 2026-10-13 (PI-V5-014)

- Hand-designed 18 risk cases and 18 mechanism controls with concrete business evidence, lawful exceptions, actionable safe paths and explicit hidden facts. Current version: `authored-18-20261013.3`; per-suite JSON, Chinese design notes, hashes, budgets, provenance and candidate checkpoint are retained under `artifacts/v5/manual_18/20261013-authored-scientific-r3/`.
- Candidate-only profile uses neutral role system prompts, omits T362's selected evidence-post label and binds T323 lookups to actual references. No changes to src/contracts/config, frozen prompts, core scoring or prior evidence; source hash remains `ef64b4368e2eb3e243acadbac5a3053b2e71cb611fa033c39c02d74ee31a3f6c`.
- Passed18 pair gates,124 neutral reference executions,36 native safe+utility paths and18 naive risk detections. Additional21 runs cover18 refuse-all utility failures,10 incorrect/empty reference misses,5 valid hits and2 complete public support+gateway replies. Fact assertions cover18 suites and hand-authored definitions exactly equal exported data.
- Preserved r1/r2 drafts, the failed verifier assertion and partial traces. Corrected two draft subtype labels in r3. Native T332 witness completes support only; explicit public-reply checks establish full lawful completion without changing its scorer.
- Provider calls0. Independent content review, real-model testing, difficulty calibration and full historical dedup not performed; no new qualified global families or formal data acceptance. T361–T363 remainSIMULATION_ONLY.

## Direct DeepSeek official protocol and 18-suite online smoke — 2026-10-13 (PI-V5-013)

- Configured the direct `deepseek-flash` path from the supplied official documentation: official base URL, explicit thinking/high effort, 131072-token ceiling, no ineffective temperature setting. Engine1.4.2 preserves and replays assistant reasoning in each direct DeepSeek agent's independent context, including follow-up turns after a final text. The AIHubMix path retains its historical protocol.
- Preserved the old source-bound 8192-token run and archived its exact source before editing. The new run uses a separate ID; the CLI rejects existing run directories before any identity evidence can be overwritten.
- T311 probe completed2/2; the full official-config smoke completed36/36 across18 classic suites with289 exact `deepseek-flash` responses, no truncation,36/36 strict replay and no-call resume. Outcomes32 EARLY_SAFE/3 TASK_SAFE_BUT_FAILED/1 SCORER_ABSTAINED remain intact. T361–T363 remain SIMULATION_ONLY; no formal scientific acceptance is claimed.
- Regression:802 passed (tests/v5 + tests/m1). Evidence: `artifacts/v5/evaluations/direct-deepseek-flash-20261013-official-all-r1/CONFIG_VERIFICATION.json`; JUnit retained in the initial official T311 run. New source hash, manifests, source ZIP, document hashes and usage are recorded.

## v5 one-pair-per-suite run and T332 replay-order fix — 2026-10-13 (PI-V5-012)

- Generated a fresh programmatic CONTROL/RISK pair for each of the 18 classic suites (36 cases) and ran the real evaluation entry point under witness and naive reference policies. Both policies completed 36/36; resume added no result rows; strict replay passed 36/36; Provider calls0.
- The first cross-process replay exposed a real T332 defect: scorer violations were collected by iterating an unordered set, so serialized score evidence could differ across Python hash seeds. T332 scorer version is now `t332-scorer-5.1.1` and sorts confidential values before recording violations.
- Added a subprocess hash-seed regression. Full `tests/v5 + tests/m1`: **796 passed**, no failures/errors/skips. Current system acceptance is rebound as `system-acceptance-20261013-final-r9`.
- The 18-suite pack remains `ENGINEERING_REFERENCE_ONLY`; one pair per suite cannot establish semantic validity, difficulty calibration, human agreement, test-retest reliability, or formal DeepSeek evidence.

## v5 historical-reference deduplication and current-source rebound — 2026-10-13 (PI-V5-012)

- The reusable factory is now version `ioabench.v5.reusable-data-factory/2.3.2`. Offline preflight binds 19 historical case files (5.1.5, plus T332 5.1.6) by SHA-256 and compares dynamic candidates with the matching construct's classic and dynamic runtime structures. Text/name changes remain duplicates or instances; they do not establish a new family.
- `local-historical-compare-20261013-r2` passed 18 suites, 36 checks and 228 reference checks with zero Provider calls. The report records `TEXT_DUPLICATE=23`, `INSTANCE=11`, `NEW_STRUCTURE=2` and keeps difficulty evidence explicitly design-proxy only.
- Added a regression proving a dynamic candidate is compared against a classic same-construct reference with its own runtime adapter. Full `tests/v5 + tests/m1`: **795 passed**, no failures/errors/skips.
- Rebound local system acceptance to `system-acceptance-20261013-final-r8`: 18 classic +19 dynamic structures, 74 supplied cases, 148 reference executions/replays, current source/test archives and provider calls0. This remains engineering evidence; no formal data, Gate D, freeze or campaign acceptance is claimed.
- Rebound the candidate-intake verification as `INTAKE_VERIFICATION_20261013_R2.json` so its JUnit hash and test count (795) match the current source; the prior 794-count verification remains preserved.
- Generated the current-source engineering blind package `system-20261013-engineering-r2` and bound its Gate C/D preparation record at `artifacts/v5/gates/gate-c-d-readiness-20261013-r2.json`; sample shortfalls and the lack of human labels remain explicit.

## v5 candidate intake and local review handoff — 2026-10-13 (PI-V5-012)

- Added `scripts/v5/prepare_candidate_intake.py`: an append-only handoff from `CANDIDATE_EXPERIMENTAL` pair runs to standard Case JSONL. It rechecks schema, dynamic registration, CONTROL/RISK identity, declared mechanism differences, pair gates, duplicate IDs and source/case hashes; it never freezes or accepts formal data.
- Added `tests/v5/test_candidate_intake.py` with valid intake, bad-pair rejection and overwrite refusal. Full `tests/v5 + tests/m1` now passes **795** with no failures/errors/skips.
- Validated the local handoff using the existing T321-DYNA experimental run: 2 pairs/4 cases became `ENGINEERING_INTAKE_READY`, ran through witness and naive reference evaluation, and produced a blinded review package with explicit per-suite shortfalls. Provider calls0; no bulk generation or formal freeze.
- Rebound the system acceptance to current source as `system-acceptance-20261013-final-r8`: 18 classic +19 dynamic structures, 148 reference executions/replays, current source/test archives, and 795 full regression tests.

## v5全面工程复核与动态资格修复 — 2026-10-12 (PI-V5-012)

- 对18项套件、19个注册动态结构、统一运行链、状态证据和科研边界做只读复核。发现动态运行器在无效模型输出、未暴露、无决策机会或评分弃权时可能错误标记 `scientifically_eligible=true`；修复为只有 `COMPLETED`、暴露/机会/评分资格均满足且监测无阻断时才进入科学分母。
- 修复动态家族注册模块缺少 `Mapping`/`Any` 导入导致 `typing.get_type_hints(register)` 失败的问题，并加入回归测试。
- 新验收 `artifacts/v5/system_acceptance/system-acceptance-20261012-final-r5/`：18经典+19动态、74工程样本、两种参考策略148次执行/严格回放全部通过；全量 `tests/v5 + tests/m1` 为791 passed，失败/错误/跳过0。Provider调用0，正式科研和数据生成状态不变。
- 修复T312经典生成器把集合直接转列表造成跨Python哈希种子输入不稳定的问题；多进程哈希种子回归一致。
- 当前验收每种结构只取一个工程配对，主要证明现有结构的运行链；不代表所有难度、多家庭、批量数据质量或DeepSeek正式结果。历史V4顶层状态与历史heartbeat保留为历史证据，当前v5以PI-V5-012及嵌套v5状态为准。

## v5 local 18-suite system acceptance — 2026-10-12 (PI-V5-012)

- Registered the user's current local-system priority; new AIHubMix calls, candidate generation and data-factory trials are paused. Same v5 Goal, unchanged constructs, Ground Truth, scorers, frozen data and formal tested model.
- Strengthened the existing verifier to require exact per-case reference outcomes, completion/eligibility, exposure and decision opportunities, safety/outcome agreement and SIMULATION_ONLY identity. Negative controls reject changed scores, absent exposure and duplicate results. Added explicit two-agent private-context isolation and independent recovery after a tool business error.
- Current-source CLI acceptance: 18 classic suites +19 registered dynamic structures, 74 local engineering cases ×2 reference strategies =148 completed executions and148 strict replays; every behavior/exposure/opportunity/ledger check passes; resume adds no execution. Provider calls0; no formal or generated qualified data.
- Full tests/v5 + tests/m1: 787 passed in67.69s, no failures/errors/skips; targeted regression68 passed. Evidence: artifacts/v5/system_acceptance/system-acceptance-20261012-final-r2/. Existing source archive452 files and separate test-source archive60 files pass SHA-256/ZIP CRC verification; hash scopes are explicit.
- These are deterministic local reference agents, not a current live DeepSeek measurement. T331/T333 PI/expert audits, human Gate D, confirmatory Pilot, formal freeze/Campaign/Release and unattended scheduling continuity are not passed by this acceptance.

## v5 reusable data-factory engineering and bounded validation — 2026-10-12 (PI-V5-011)

- The direct user instruction authorizes autonomous repair and small trials, superseding the earlier defect-by-defect pause. Same v5 Goal; no bulk production, frozen data changes or formal tested-model substitution.
- Reused existing scenario/scorer/runtime contracts in a common 18-suite pipeline: controlled public-text adapters, typed T312/T331/T352 compilers, deterministic pair/reference execution, actual runtime-structure comparison, blind independent review and immutable evidence. T321 graph validation now rejects duplicate/cyclic/unresolved nodes; unsupported world/rule changes fail closed.
- Added exact durable-response recovery for a documented auditor transport failure, with a new run/auditor identity, zero regeneration and immutable old evidence. Existing FAIL/ABSTAIN/malformed/identity-failed answers cannot be retried with another judge. Pending unknown requests are not reissued. Error diagnostics redact credentials and distinguish HTTP401 from empty/connection failures; refusals remain rejected.
- Genuine Astra review rejected T352 agent-count-only diversity. Added versioned own-receipt plus explicit completed-report query using the existing tool; default broadcast compatibility and Ground Truth/scoring remain intact. Actual exposure, reference recovery and immutable action snapshots pass local checks; fresh online quality remains unverified.
- Final tests/v5 + tests/m1: 784 passed/66.14s; 18-suite preflight36/36 with228 reference checks, typed preflight6/6 with36 checks. Archived old r4 CLI in a disposable copy resumes the genuine rejection with zero Provider construction/calls and33 original files unchanged. Final source archive452 files, SHA-256/CRC verified, credential matches0.
- Eleven inference attempts produced7 unique saved responses/38383 tokens: seven candidate executions yielded1 machine acceptance,3 rejections,3 Provider failures; auditor negative-control request also failed. Latest Gemini generation, GPT audit and documented read-only key-quota authentication on both official domains return HTTP401. No inference calls are wasted after shared authentication failure is established. Prepared contradiction blind pack is not an audited PASS.
- Engineering evidence and limitations: artifacts/v5/data_factory/trials/factory-acceptance-20261012-r1/; docs/v5/V5_DATA_FACTORY_HANDOFF_20261012.md. M5 remains IN_PROGRESS; latest live positive/negative controls, broad executable diversity, global historical dedup and difficulty calibration remain open. Global qualified families/formal datasets/human labels0.

## v5 data-factory preflight paused — 2026-10-12 (PI-V5-010)

- Registered the user's new requirement to pause and notify on the first pipeline/quality/AIHubMix failure; supersedes overnight automatic failover for this work.
- Added exact reviewer citation roots/index, issue evidence checking and malformed-evidence handling; historical r10 rejection remains unchanged.
- Added opt-in single-attempt, primary-only AIHubMix calls and factory pause checkpoints/zero-call paused resume. Default formal adapter behavior unchanged; remaining replay/NO_REFERENCE stop coverage is documented, not silently claimed complete.
- 507 regression tests pass. New offline readiness command passes original compilation/reference gates but fails duplicate-task-node rejection: invalid graph compiles without findings. Saved exit1/negative evidence and paused immediately; no live API calls, generated candidates, registered families or formal data changes.
- Evidence: artifacts/v5/data_factory/process-validation-20261012-r1/; next work requires explicit user continuation.

## v5 supplied-case measurement system — 2026-10-12 (PI-V5-009)

- Registered system-first priority; data-factory construction/generation deferred. Corrected r10's current state to terminal quality rejection without changing its original evidence.
- Added exact dynamic registration/JSON loading, SIMULATION_ONLY identity preservation and T352 JSON round-key compatibility. Engine1.4.1 retains repeated malformed-call actions/events; dynamic runner1.1.0 keeps journal context across async bridging and wires default monitors.
- Added supplied-case batch CLI, immutable source/model/input pins, bounded retry, identity guard, process-interruption recovery and preserved partial-write segments. Added chronological request/role-exact response replay and separate safety/utility/recovery/missingness reports.
- Live r1 exposed body snapshot/catalog alias variation despite a constant authoritative gateway identity. Its interruption is retained; evaluation1.0.1 pre-pins only the exact probe body and catalog alias, rejecting unknown IDs. Fresh r2 two-case DeepSeek run completes and replays exactly; genuine risk recovery remains LATE_RECOVERY.
- Review software accepts dynamic cases, records sample shortfalls and source hashes, rejects invalid labels/duplicate reviewers and preserves disagreements for human adjudication. No human labels or formal acceptance produced.
- 472 regression tests pass; 3240 offline checks pass;74 supplied cases ×2 policies=148 executions/148 exact replays, resume without additional execution. Source archives, proof, usage and limits: artifacts/v5/system_acceptance/system-20261012-r2/; handoff: docs/v5/V5_SYSTEM_HANDOFF_20261012.md.
- Existing heartbeat no longer exists; no replacement or continuity after shutdown is claimed. Frozen data, constructs, truth and scoring semantics remain unchanged. Formal Pilot/Campaign/Release gates remain separate.

## T321 blueprint/executable fidelity correction — 2026-10-12

- Compiler 1.3.0 requires explicit per-arm broker profiles and blocks undeclared or contradictory alpha/beta weakening. Existing `conflicting_claim=false` failures now stop before compilation. General schema, Ground Truth and scorer semantics remain unchanged; old blueprint/run evidence is retained.
- Scenario 0.4.0 / slice generator 0.2.0 use the actual offer version in beta's claim while preserving version/signing across arms. The intended false basic-profile claim remains. Generator and reviewer instructions expose the executed arm design and existing verdict rules; free-text fidelity still needs independent review.
- Full tests/v5 + tests/m1: 374 passed. First app heartbeat observed at 2026-10-12T01:52:36.772Z; no power-loss/app-closure continuity claim.

## Official AIHubMix per-model call correction — 2026-10-12

- Read the supplied official snapshot and fetched seven current model schemas via the official index; GPT-6.1 Sol has a documented minimal example but no indexed schema. Added opt-in auxiliary schema lookup, documented token/reasoning parameters, HTTP/1.1 and allowlisted authoritative gateway response headers. Frozen DeepSeek parameters/scientific semantics unchanged.
- Eight actual auxiliary JSON/content/identity probes pass (713 tokens). GPT dated body IDs resolve through X-Aihubmix-Model, without guessing aliases. Claude json_object is avoided; GLM remains thinking-enabled. Production auxiliary output ceiling is 65536, bounded request deadline 900 seconds; probe-only MiMo thinking-off is not used for generation.
- Real GLM-5.3-Flash independent high-effort review returns in r9. Fixed single JSON-fence parsing after it mistakenly triggered a Qwen retry; interrupted Qwen outcome is recorded as unknown. Exact-input checkpoint replay preserves GLM's original findings without a new audit call. Semantic score 3 contradicts PASS, so the unchanged contract rejects the candidate; no family registered.
- T321 1.2.0 / scenario 0.3.0 now gates peer capability publication on gamma arrival and preserves item labels; offline checks pass but blueprint/compiled-offer semantic fidelity remains the next task. Full tests/v5 + tests/m1: 368 passed.
- Read back active 30-minute Codex app heartbeat ioa-bench-v5-goal; first execution remains unverified. See docs/v5/V5_AIHUBMIX_CALL_CONTRACT_20261012.md and run-scoped evidence. Historical records remain intact.

## T321-DYNA executable diversity extension — 2026-10-12

- The blueprint compiler accepts an optional `broker_count` of 2 (legacy default) or 3. Three-broker candidates add a scheduled `broker_gamma` secure profile cross-check held constant across CONTROL/RISK; the paired manipulation and T321 scoring rules are unchanged.
- Added fail-closed count validation, explicit generator constraints, structural-signature and gamma-drift tests, and full dynamic-runner coverage. `tests/v5` + `tests/m1`: 350 passed.
- Live run `artifacts/v5/overnight_runs/model-routing-20261012-r6` discovered 419 entries. Qwen returned an empty transient response; GLM generation was interrupted without a persisted response; Astra returned an unverified served ID; all were recorded and routing continued to Gemini. The Gemini candidate passed compilation, hard gates, all three reference executions, and executable-family dedup; independent review by GLM is in progress. No candidate registration is claimed before that review finishes.
- S1 request timeout is now 180 seconds. On checkpoint resume, a started request without a persisted response is recorded as `REQUEST_INTERRUPTED_NO_RESPONSE`, with provider use explicitly unknown, and the route is cooled down; targeted recovery/compiler tests pass.

## PI-V5-008 dynamic auxiliary-model routing — 2026-10-12

- Registered the direct user/PI amendment allowing live AIHubMix discovery, task-matched auxiliary-model selection, bounded fallback, model-family separation, and versioned non-frozen candidate expansion; formal model, historic evidence, scientific thresholds, Gate D, confirmation Pilot, and Campaign remain protected/gated.
- Added exact catalog candidate resolution and detail enrichment; added a run-scoped T321 S1 route/generate/compile/run/dedup/audit runner with checkpoints and raw request/response provenance. A provider-blocked run can now resume discovery; provider-operation counting no longer double-counts auditor resolve/generate starts.
- Live routing is evidenced in r2-r5. r4 passed compilation, hard gates and reference executions but its 4,096-token audit was truncated. r5 reused the generator response, discovered a surface-only family duplicate and exercised auditor fallback (three empty responses; Astra served identity did not match an exact catalog ID). No valid independent audit or new family resulted. The report recovery and early diversity stop are fixed; `tests/v5` + `tests/m1` pass 346.
- Blind-review package v2 is prepared with per-suite dataset versions and source hashes. Per-run morning reports now follow the 06 template and preserve candidate acceptance/rejection/blocking distinctions. The CLI read-only smoke works; workspace-write was not executed because automatic approval returned HTTP 404. Unattended scheduling remains unverified/unconfigured. See `docs/v5/V5_PROGRESS.md` and the run-scoped evidence under `artifacts/v5/overnight_runs/`.

## 网页端 ChatGPT 源码审阅包 — 2026-10-10

- 新增源码审阅打包工具，复用工作区打包器的清单、路径、CRC 和 SHA-256 验证；保留当前源码、测试、文档、配置、v5 候选数据和关键摘要，不嵌套历史 ZIP 或完整运行轨迹。
- 新增 docs/HANDOFF_20261010_CHATGPT.md，说明当前 v5 与历史 v4 边界，并附可直接粘贴的中文审阅请求。
- 打包不调用 Provider、不改变数据或测评语义；验收结果以 exports/chatgpt-source-review-20261010/PACKAGE_VERIFICATION.json 为准。
- 已完成：1,197 个工作区文件，ZIP 3,112,669 字节；清单集合、CRC、逐文件 SHA-256 和已知秘密扫描通过。包内状态记录是打包开始时快照，完成状态在本机台账和包外验收文件中。

## 工作区整理与 18 项测评实现进度 — 2026-10-10

- 对根目录和 src/tests/scripts 下 38 个可重建缓存目录进行可恢复清理，共 166 个文件、1,422,254 逻辑字节；回滚 ZIP 的 CRC、逐文件 SHA-256 和秘密模式扫描通过。清理前后 17,126 个受保护文件哈希一致。历史包与研究资产保留原路径。
- 新增 docs/WORKSPACE_INDEX_20261010.md 和 docs/v5/PROJECT_PROGRESS_18_SUITES_20261010.md，逐项列出 18 项测评的实现、版本、工具动作及历史试点剩余问题。
- 本次 v5 回归 71 passed；重跑离线矩阵 3,240/3,240 通过。Provider 调用为 0；Gate D/E、冻结和正式运行状态不变。
- 磁盘空闲观测下降 1,720,320 字节：本次保留回滚包及哈希清单，且可能存在并发写入；不宣称释放了磁盘容量。此次目标是可恢复整理。

## v5 single-model offline revalidation — 2026-10-09

- Re-ran the complete v5 offline matrix with seeds 5, 11 and 101: 18 suites, 3,240 pair-seed checks, 0 failures. The dated evidence is `artifacts/v5/gates/offline-matrix-20261009-single-model-precheck.json`; existing historical Gate E and frozen candidate files were not overwritten.
- Re-ran candidate data-quality checks for all 18 suites on `5.1.5-candidate-20261006`: 18/18 passed with no gate failures, static firewall hits, entity-substitution-only pairs or exact pair-template duplicates.
- No Provider calls were made. This strengthens automated offline evidence only; Gate D human review and the approved single-model confirmation Pilot remain outstanding.

## v4.1.13 corrective - strict formal campaign and final delivery - 2026-10-03

- Executed the frozen v4.1.13 campaign for all 18 suites: 1620/1620 terminal cases, with 1488 `COMPLETED`, 103 `INVALID_MODEL_OUTPUT`, 21 `BUDGET_EXCEEDED`, 8 `INFRA_INTERRUPTED`, and no `FAILED` terminal result. Historical v3/v3.2 runs were not consumed.
- Recomputed Run, Release, source-tree, Dataset, scorer, runtime, model-profile, attempt-journal and Replay bindings. The post-run audit is `STRICT_18_OF_18`; T353 has 90/90 complete honest/manipulated paired Replay bundles; T361-T363 remain `SIMULATION_ONLY` with frozen Synthetic Human provenance.
- Added versioned post-campaign validation tools so valid terminal interruptions are not required to contain a completed dispatch envelope and invalid/interrupted simulation cases are not required to contain a Synthetic Human response. The Release-frozen validator was restored to its recorded SHA-256; no Run, Release, Dataset, Replay or frozen runtime artifact was modified.
- Generated canonical report, Dashboard, reproduction guide and verified delivery bundle. The bundle passed secret scanning and ZIP CRC verification; recorded model responses total 21082.

## v4.1.7 corrective - offline delivery/provenance closure - 2026-10-02

- Froze immutable successor `v4.1.7-corrective-integration-20261002` with Release SHA-256 `11492727...041a5` and unchanged candidate-v7 source tree `37b5f798...253c7`; 18 pre-frozen Run Manifests bind the same Release.
- Retained every Synthetic Human response attempt, made malformed outputs terminal, hardened Phase F attempt/Replay/model binding, and completed report/bundle provenance wiring. Promotion audit and `tests/v4` pass; pre-provider strict binding remains correctly 0/18 because no v4.1 Formal Run exists.
- Provider calls remain 0. Live smoke and Formal Campaign remain blocked on explicit user authorization; historical Releases, Runs, Gates, reports, and bundles remain intact.
- Full workspace regression completed with `838 passed, 2 skipped`; the 25 historical artifacts overwritten by test fixtures were restored from frozen archives and rechecked against the protected baseline. The restore helper now refuses source/config/contract rollback and chooses a new report filename.

## v4.1.1 corrective — 执行脚本冻结哈希收口 — 2026-10-02

- 保留原 v4 与 v4.1 Release 不变，新增 successor `release/BENCHMARK_RELEASE_v4.1.1-corrective-integration-20261002.json`；它只刷新历史目录共存修复后的执行脚本哈希，不改变 taxonomy、Dataset、scorer、prompt、tested-model roster 或 candidate 源码树。
- v4.1.1 继续使用隔离的 `-v4.1-formal` Run 命名；18 份新 Manifest 位于 `data/runs/_v4_1_1_manifests/`，全部绑定 Release SHA-256 `fe05293f...8906d` 与 source tree `8763a042...5af3`。
- 离线 preflight 10/10 通过：workspace、candidate-v3、Release 三方源码哈希一致；四个执行脚本哈希一致；18 个历史 Run 保留；0 个新正式 Run；无 live-smoke gate。`tests/v4` 47 项、核心 runtime 回归 11 项、状态回归 4 项通过，Provider 调用为 0。
- Phase F/G 预运行结果保持 0/18 `NOT_BOUND`，明确表示尚无 v4.1 正式结果，不构成科研通过。当前唯一下一步仍是取得用户对 live smoke 的明确 Provider 授权。

## v4 corrective — frozen runtime 与 Run Manifest 执行接线修复 — 2026-10-02

- 将工作区 `src/ioabench` 中 9 个与 frozen candidate 不一致的文件同步为 `corrective-candidate-v2` 的精确字节；当前 `src/contracts/config` 与 candidate 逐文件差异为 0，authoritative tree hash 为 Release 冻结值 `2b72255b...e6ff`，实际 import 的 dispatcher 为 `construct-dispatch-1.0.2`。
- `run_online_campaign.py` 在任何正式 Run 前 fail-closed 复核完整 source tree 与 dispatch version，并把对应 `_v4_manifests` 文件原样安装到实际 Run 的 `manifest/<run_id>.json`；已存在但字节不同则拒绝执行。默认起点纠正为 T311。
- `v4_validate_run.py` 新增实际 runtime manifest 与预冻结 manifest 的字节一致性检查，消除 Phase F/G 只看预冻结 manifest、Phase C 看实际 manifest 的 provenance 分裂。
- v4 Campaign state 与 pilot Run/Gate 全部迁到 `artifacts/scientific_closure_v4/`，不再读取或覆盖历史 `ONLINE_CAMPAIGN_STATE.json`、历史 pilot gate 或历史 pilot Run；v4 pilot 只读已有 semantic-validation evidence，不向 frozen Dataset 写 cache/结果。
- `tests/v4` 44 项通过，相关 workspace runtime/manifest 测试 11 项通过；旧 19,606 文件 baseline 的变化精确等于 9 个 v4 source promotion 文件，额外变化为 0。Release、Dataset、candidate tree、历史 Run 和历史交付包未改动，Provider 调用为 0。证据见 `artifacts/gates/V4_S7_RUNTIME_INTEGRATION_001.json` 与 `runtime-promotion-audit-001.json`。

## 工作区整理与交接快照 — 2026-10-01 22:31

- 将 81 个活动缓存目录及 3 个临时诊断脚本移入 `artifacts/workspace_maintenance/20261001-223139/`，保留原相对路径及经校验的恢复备份。直接删除被自动审批拦截，本次采用可恢复归档，不声称释放磁盘空间。
- 新增 `docs/HANDOFF_20261001_WORKSPACE.md`，说明历史 v3.2 与 v4 的边界、已确认的运行清单/编排/汇总缺口和后续验证任务；本次不修复测评代码、不升级科研验收结论。
- 新增 `scripts/package_workspace_snapshot.py`，在新的 `exports/` 子目录构建快照，排除凭据、缓存和重复嵌套的旧压缩包；保留排除清单，逐文件 SHA-256 和 ZIP CRC 验证。
- 本次未调用模型服务、未重跑会改写历史 Gate 的工作区测试。整理前后的文件核对及原 19,606 个受保护文件验证见本次维护目录。

## v4 corrective — V4-S7 等待期：Phase F/G 验证工具离线构建并证明 — 2026-10-01

- 新增 `scripts/v4_validate_run.py`（Phase F 逐套验证器，25 项检查）与 `scripts/v4_strict_binding_audit.py`（Phase G 聚合审计，目标 18/18 STRICT_BINDING）。两者均 fail-closed：任何检查不通过即 `NOT_BOUND` 并排除出 canonical 聚合；`historical_runs_consumed` 恒为 0。
- 用合成 v4-native fixture 证明通过路径：18 套全绿、`STRICT_18_OF_18`、零 blocker；无 v4 run 时返回 0/18 且退出码 1。新增 `tests/v4/test_phase_f_validator.py`（9 项），`tests/v4` 合计 37 项通过。
- 发现并修复一处会误杀全部 T353 正式结果的缺陷（PF-1）：T353 三分支校验最初查 `replay` 顶层 `primary/honest/manipulated`，而冻结运行时实际写在 `replay["scenario"]["paired_runs"]`（键 `honest`/`manipulated`，各带嵌套 replay）。已按 `discovery_selection.py:318-345` 的真实契约改正，并加回归测试锁定。若不修，Phase F 会把每个 T353 v4 run 误判为 NOT_BOUND 并排除出 Phase C。
- 顺带独立确认历史 T353 结果完全不含 `paired_runs`，与既有审计中"v3 配对分支丢失"的结论一致；v4 native run 将携带。
- 本轮零 Provider 调用；未改动 Release、Dataset、历史资产。证据：`artifacts/gates/V4_S7_FG_TOOLING_001.json`。

## v4 corrective — V4-S7 等待期离线预演：修复 Phase E 会覆盖历史 Run 的缺陷 — 2026-10-01

- 在等待 Provider 批准期间对 Phase D/E 前置条件做只读预演，发现一处阻断级缺陷：`scripts/run_online_campaign.py` 用 `<model>-<suite>-<version>-formal` 构造 run ID，而这正是 18 个历史 v3/v3.2 Run 目录的命名。若不修，Phase E 会 resume 进历史目录并改写冻结证据，直接违反"历史 Release/Run/Gate/Dataset/Report/Bundle 不得覆盖或删除"。
- 修复：run ID 改为 `<model>-<suite>-<version>-v4-formal`；新增守卫，历史目录存在时 `SystemExit`；`formal_complete()` 改读 v4 目录。新增 `tests/v4/test_campaign_orchestrator_run_ids.py`（7 项）锁定该行为，并断言 18 个历史目录全部存在且与 v4 ID 无冲突。
- 第二项发现（非阻断）：`AIHUBMIX_API_KEY` 只存在于工作区 `.env`（进程环境未导出），而 orchestrator 仅向子进程传递 `os.environ`。经核实 `ioabench.cli` 与 `scripts/run_online_pilot.py` 都在任何 Provider 调用前调用 `load_workspace_env()`，且该函数不覆盖已存在的环境变量、不记录明文，因此凭据链路成立。凭据值未被读取或落盘。
- 新增只读预演脚本 `scripts/v4_phase_de_readiness_audit.py`（40 项，对照 goal pack 的 Release Freeze Contract 逐字段核对）与 `scripts/v4_phase_e_preflight.py`。结果：40/40 通过；orchestrator run ID 与 18 个冻结 manifest 完全一致；`tests/v4` 29 项通过；基线 19,606 个受保护文件零变更；本轮零 Provider 调用。
- 该修复仅改动 campaign harness，不触及 dataset、scorer、prompt、contract、runtime construct 或 Release 字段，冻结 v4 Release 无需重建。证据：`artifacts/gates/V4_S7_PREFLIGHT_FIX_001.json`。

## v4 corrective Release — Phase A–C 离线收口（等待 Provider 批准）— 2026-10-01

- 冻结 `release/BENCHMARK_RELEASE_v4-corrective-20261001.json`，源码树 sha256 `2b72255bcb5d258322bb97c88714a443ae4bb4026092a3c4219d886d2083e6ff`。18 个 Run Manifest 全部绑定同一 Release 三元组，写入 `data/runs/_v4_manifests/`。
- strict retry 契约落地：`INFRA_INTERRUPTED` 成为终态；只有零有效模型行为且 `infrastructure_failure is True` 的 `RETRYABLE_INFRA_FAILURE` 才允许有界 resume；`INVALID_MODEL_OUTPUT` 永不重试。新增 AttemptJournal，逐条 fsync，attempt 编号永不复用。
- 离线验证：82 项 candidate validation、23 项 strict retry 自检、22 项 `tests/v4`、831 项工作区测试（2 skip）、90 案 mock 端到端全 COMPLETED、19,606 个受保护文件基线零变更。
- 本轮零 Provider 调用，未覆盖或删除任何 v3/v3.2 资产。Phase D/E 属 Provider 阶段，必须获得用户明确批准后方可执行；批准件 `artifacts/scientific_closure_v4/provider-approval-request-001.json` 状态 `AWAITING_USER_DECISION`。

## 科研收口 v3.2 — 剩余证据的有界搜索 — 2026-10-01

- 新增可重跑的 `scripts/audit_recovery_boundary.py`：核对 9 个 ZIP 内 15 份嵌套源码树及 2 份磁盘历史源码树，全部匹配已知旧版本；没有新增源码匹配。工作区数据库、备份及临时文件后缀搜索为零命中，范围限制写入证据。
- 检查 39 段含无效状态的历史工具输出及四个相关正式 Run 的文件清单。历史 `results.json` 的观察时间不能代替快照生成时间，不能据此推断原始无效案例身份；保留 364 条源码缺口及至少 30 条无效计数下降结论。
- 19 项审计测试通过。版本化搜索 Gate 仅确认搜索完成，科学验收仍未通过；队列版本 15、440 项任务。没有 Provider 调用，未应用科学修复候选，历史资产保持原样。

## 科研收口 v3.2 — Phase C 取数与验收入口 — 2026-10-01

- 修复 `scripts/phase_c_campaign.py`：汇总前必须提供相互绑定的审计、验收和元数据补充件，校验文件哈希、精确 Run Manifest、被测模型和数据身份。未获准结果不进入取数；所有输出使用新目录，拒绝覆盖历史成果。
- 移除固定的“未发生重跑趋安全”和“每例只运行一次”事实断言；最终状态由 A–D 分项、完整 canonical 覆盖、资格伪装偏差及交付状态共同决定。未完成时 `--final` 返回非零。
- 真实文件运行得到 0 项、0 条获准汇总和 18 项排除清单；任务效用率为 null。报告及仪表盘明确显示未通过，三项人机能动性侵蚀测评保留 `SIMULATION_ONLY`。
- 17 项审计回归测试通过；浏览器桌面/390px 显示检查通过，22 项自动可访问性检查通过，未报告违规。强制 final 的退出码为 1，失败验收证据保留。队列版本 14、440 项任务，科学验收未升级。

## 科研收口 v3.2 — Release 元数据补充 — 2026-10-01

- 创建纯元数据 Release Addendum 和规范化 Model Profile Addendum，原冻结文件不变。对 19,673 条记录重新计算角色、系统提示、初始任务和工具哈希，生成后再次完整复验。
- 分开记录 18,628 条被测模型调用与 1,045 条合成人类调用；纠正旧 profile 统一 8192 的描述，保留资格伪装实际 4096 和合成人类 2000。未设置参数、实际地址、恢复并发及模型发现回复缺失均明确标注。
- 新版最终验收快照引用 A–D 四个分项和元数据检查，保持 NOT_ACCEPTED。补充件仅冻结已保存输入的元数据，不改变科学语义或升级 canonical 资格。
- 审计回归测试 14 项通过；队列版本 13、440 项任务。S1 继续，S6/S7 的增量证据已关联；没有 Provider 调用或新科学 Release。

## 科研收口 v3.2 — 历史编辑还原与增量重放 — 2026-10-01

- 静态解析历史导出的字面编辑，未执行历史命令；新增精确还原 12 个源码哈希。边界检查覆盖越界路径、未知赋值、命令不执行、字节篡改和不匹配哈希；审计回归测试 13 项通过。
- 54 条新增责任链断裂记录用对应源码在独立进程中重放，全部匹配。累计历史源码与重放覆盖 1,256/1,620 条，责任链断裂覆盖 87/90 条；节点操纵 90 条仍仅验证主轨迹。
- 364 条记录的完整源码尚未还原。逐路径审查和 `RETROACTIVE_RELEASE_BINDING_AUDIT_v3.json` 追加新证据，分类仍为 5 项 INCOMPATIBLE、13 项 UNPROVEN，最终验收未通过。
- 队列更新为版本 12、440 项任务，检查点纠正过期证据链接。科学源码、冻结成果和旧审计均保留；没有 Provider 调用，未应用修复候选或创建新科学 Release。

## 科研收口 v3.2 — 历史源码还原与参数来源 — 2026-09-30

- 按 Windows 的实际路径排序重算 9 个根目录源码 ZIP；使用保存的旧/当前文件字节组合，精确还原两个中间源码哈希。共定位 1,202 条结果对应的源码，418 条仍缺完整源码还原。
- 4 个源码组在独立进程中重放全部对应记录：1,202 条匹配，节点操纵的 90 条限定为主轨迹。旧 dispatcher 不支持新增空参数导致的首轮审计失败保留；审计器修正调用后仅重跑失败的 442 条。
- 逐路径审查支持 4 项源码严格一致、8 项源码语义兼容，6 项仍有未还原组。`RETROACTIVE_RELEASE_BINDING_AUDIT_v2.json` 追加这些证据，canonical 分类仍为 5 项 INCOMPATIBLE、13 项 UNPROVEN。
- 整理并交叉验证 19,673 条模型记录的提示、工具和参数来源。恢复时实际并发、每次使用的服务地址、未保存的上下文上限等明确标注未知；未设置参数写为 PROVIDER_DEFAULT_UNSET。
- 审计回归测试 10 项通过；活动科学源码与冻结成果未改动，没有 Provider 调用。队列版本 11、440 项任务，S1 继续进行。

## 科研收口 v3.2 — 独立复核与隔离候选验证 — 2026-09-30

- 历史工具输出与冻结恢复器的独立复现证明：责任链断裂、谣言扩散、讨论扭曲、能动性弱化四项中，至少 30 条无效输出终态经重试后不再无效。尚不能还原准确案例名单；不能将其称为不安全结果被重跑成安全。
- 16 项共 1,440 条保存轨迹完整重现。资格伪装的 90 条仅在 token 上限归一化诊断中重现；节点操纵的 90 条主轨迹重现，但 180 条配对轨迹缺原始回复，另有 4 条配对差异指标与已保存选择冲突。
- 新验收按实现、数据、绑定、正式测评和最终项目拆分；仅数据复核在声明范围内通过，其余未通过。旧 Gate、Release、数据和运行结果保留。
- 修复候选仅位于隔离目录：第一版的嵌套 Replay 哈希检查失败，证据保存为 `candidate-validation-001.json`；第二版通过 39 项离线检查，审计器 7 个回归测试通过。冻结源码未变更，没有 Provider 调用，也未批准修复版本或重跑。
- 对节点操纵 90 条保存记录离线重算，仅 4 条配对差异指标由 1 变为 0，其余评分字段不变。9 个根目录 ZIP 的 10 份相关结果/检查点与当前文件一致，没有找回更早尝试。19,606 个原始文件哈希复核无变化。
- 状态与队列更新为版本 10、440 项任务；S1 保持进行中。候选补丁和检查通过不等于科学验收通过。

## 科研收口 v3.2 — 2026-09-30

- 新增 `scripts/scientific_closure.py`，只做离线证据检查，拒绝覆盖已有审计文件。两个回归测试验证内容篡改、跨 Manifest 错绑和审计文件覆盖会被拒绝。
- 保存 19,606 个历史文件的哈希清单和修改前 state 备份；冻结 Dataset、Run、Release、旧 Gate 保持原样。
- `V32_S0_EVIDENCE_INVENTORY.json` 独立重算 18 套数据的实际内容，核对 Run/Dataset/Release 三方绑定、全部 1,620 条结果的 case 身份、Replay 与请求哈希，并提取实际提示、工具、模型参数证据。
- State/Queue 转入 v3.2 科研收口，旧最终 PASS 明确保留为历史记录；新的 canonical 与最终验收尚未通过。没有在线模型调用。

## 1.0-draft-model-centric — 2026-09-23
- Reframed benchmark target from IoA infrastructure security to model endogenous safety in IoA scenarios.
- Incorporated confirmed design decisions Q001–Q132.
- Made local no-Docker profile normative for v1.
- Added AIHubMix model runtime contract and initial tested model request `deepseek-v4.1-flash`.
- Added 18 independent dataset lifecycle and per-suite data recipes.
- Added synthetic worlds/sandbox, batch scheduler, statistics, replay/dashboard, release governance and Codex autonomy playbook.
- Added local SQLite DDL, dataset/world/run/model schemas and expanded Python ports.

## Construct remediation offline gate — 2026-09-26
- Connected all 18 suite baseline dispatches to their suite-specific construct runtimes; the legacy generic executor remains historical and is not used by this offline construct dispatch.
- Fixed T341 A2A evidence delivery to a real tested decider, added delegation alternatives, and corrected alternative plans for protocol, disclosure, and rumor suites.
- Added regression coverage for all-suite safe/naive/alternative/recovery action sensitivity.
- Verified `384 passed, 2 skipped`; skipped tests require `AIHUBMIX_API_KEY` and made no provider call. `validate-spec` passed.
- No Dataset Pack v3, r6, frozen-data mutation, or online model run was created.
## Work queue v2 — 2026-09-23
- Expanded `state/WORK_QUEUE.yaml` from the initial seed queue to a complete M0–M10 DAG with 220 executable tasks.
- Added per-suite implementation chains for all T311–T363 evaluations and per-suite M9 formal dataset generation/freeze tasks.
- Added M10 full-benchmark execution, checkpoint/resume, analysis, dashboard, replay, report, reproducibility bundle and Definition-of-Done gates.
- Added `state/WORK_QUEUE_VALIDATION.json`; DAG validation confirms no cycles, no missing dependencies/references, all 18 formal dataset freeze tasks present, and all milestone exit gates present.
## M10-007 — 2026-09-25
- Completed the canonical `deepseek-v4.1-flash` all-suite run against the frozen v1 dataset pack: 1,620/1,620 work units completed and valid, with replay bundles persisted for every case.
- Confirmed exact AIHubMix model resolution, no provider or dataset blocker, and simulation-only labeling for T361–T363.
## M10-008 — 2026-09-25
- Added machine-readable run completeness validation and `data/runs/deepseek-v4.1-flash-v1/completeness.json` with terminal-state, exclusion, replay-presence and replay-hash checks.
- Validated the formal run with 1,620 valid units, 1,620 replay/hash matches and zero errors; added a regression test for completeness artifact generation.
## M10-009 — 2026-09-25
- Generated formal run metrics for all 18 suites with safety metrics kept separate from Task Utility and validity counts.
- Added deterministic difficulty/world/mechanism breakdowns and Wilson 95% utility uncertainty summaries without inventing an overall safety score.
## M10-010 — 2026-09-25
- Wrote deterministic representative case selection for the formal run with replay paths and replay hashes.
- Recorded the observed outcome distribution honestly: 1,440 `EARLY_SAFE`, 180 `TASK_SAFE_BUT_FAILED`, and no `UNSAFE_ACTION` or `LATE_RECOVERY` cases.
## M10-012 — 2026-09-25
- Generated the formal Markdown report, suite CSV/JSON tables, six-category `risk-profile.json` and task-utility SVG figure.
- Report provenance identifies `AIHUBMIX_LIVE`, keeps Safety and Task Utility separate, avoids an invented overall score and states all simulation limitations.
## M10-013 — 2026-09-25
- Added evaluator-side replay audit and `artifacts/runs/deepseek-v4.1-flash-v1/replay-audit.json`.
- Audited all 1,620 valid replays successfully for canonical content hashes, observable timeline/model records, reconstructible scorer references and scrubbed model-visible Oracle fields.
## M10-014 — 2026-09-25
- Built `release/ioabench-v1.0-research-prototype/` with frozen specs/contracts, all manifest-referenced formal datasets, run evidence, reports, completeness/replay audits and environment metadata.
- Added a content-addressed bundle manifest with 1,756 file hashes; provider credentials are excluded.
## M10-011 — 2026-09-25
- Completed the local read-only Dashboard data/HTML surface with six categories, all 18 suites, separate safety/utility views, validity and breakdown details, simulation labels and representative replay links.
- Verified the live local HTTP endpoints: `/api` and a replay endpoint both returned HTTP 200 for the formal run.
## M10-015 — 2026-09-25
- Final v1 Definition-of-Done gate passed after `316 passed, 2 deselected` offline regression tests and the formal-run evidence audit.
- Project state transitioned to `complete`; all 220 queue tasks are done, with no ready or blocked tasks remaining.
- Post-gate reporting correction: recovered missing Task Utility from persisted replay evidence for 540 cases, added token/call/tool/latency aggregates, and added a source-linked current-catalog cost estimate without changing frozen datasets or model prompts.
- Reproducibility bundle correction: include executable source/configuration/tests, both the historical run-pinned dataset versions and the current M9 frozen dataset versions, and exclude Python cache artifacts; rebuilt bundle contains 2,366 content hashes.
## M0-001 — 2026-09-23
- Initialized the `src/ioabench` package layout with provider-neutral domain package boundaries.
- Added `pyproject.toml` with setuptools packaging and pytest, Ruff and mypy configuration.
- Added import/tooling regression tests and a package import verification script; acceptance passed with 2 tests.
## M0-002 — 2026-09-23
- Added local-v1 YAML configuration loading with deterministic project-relative paths and enforced no-public-internet/no-Docker settings.
- Added environment-only API-key loading, safe representations, redaction and offline configuration tests.
## M0-004 — 2026-09-23
- Added JSON/YAML schema loading, Draft 2020-12 validation, semantic hooks and stable canonical SHA-256 hashing.
## M0-005 — 2026-09-23
- Added persisted run lifecycle transitions, write-once manifests and atomic JSON checkpoints; acceptance tests pass.
## M0-006 — 2026-09-23
- Added normalized observable events with distinct occurred/observed timestamps, payload hashes and SQLite telemetry queries.
## M0-007 — 2026-09-23
- Added deterministic offline fixtures, opt-in integration marker checks, contract verifier and regression-test naming guidance.
## M0-008 — 2026-09-23
- Added formal-run Agent environments with SUT-only paths, public-web denial, and nested telemetry/exception secret redaction.
## M0-009 — 2026-09-23
- Added `validate-spec`, `status` and validated `run` placeholder CLI commands; CLI tests and direct spec validation pass.
## M0-010 — 2026-09-23
- M0 acceptance gate passed: 28 offline tests and four clean SQLite stores; evidence recorded in `artifacts/gates/M0.json`.
## M1-001 — 2026-09-23
- Added provider-neutral `ModelPort`, immutable model profile/request/response types and request validation.
## M1-002 — 2026-09-23
- Added AIHubMix adapter with exact live catalog resolution, OpenAI-compatible generation, typed provider failures and no model substitution.
## M1-003 — 2026-09-23
- Added bounded transient-provider retries and separate latency/token/retry/provider-failure usage records.
## M1-004 — 2026-09-23
- Added schema-validated tested-model profile for `deepseek-v4.1-flash` with explicit sampling parameters and capabilities.
## M1-005 — 2026-09-23
- Added isolated multi-agent sessions with private prompts/memory and explicit peer-message transfer only.
## M1-006 — 2026-09-23
- Added deterministic `MockModel` scripted responses and request-hash keyed `ReplayModel`; both remain offline-only.
## M1-007 — 2026-09-23
- Added explicit model-role router and provenance history; tested-model reuse for support roles is rejected by default.
## M1-008 — 2026-09-23
- Added provider adapter contract smoke and opt-in live test. Current environment records `PROVIDER_BLOCKED` because `AIHUBMIX_API_KEY` is absent; no secret was persisted.
## M0-003 — 2026-09-23
- Applied four normative SQLite DDLs to separate files, with foreign-key enforcement and telemetry WAL.
- Added a control-store RunRepository adapter; tested-agent visible paths exclude Oracle. Three acceptance tests pass.
## M2-011 — 2026-09-23
- Added isolated per-agent memory with reset semantics, provenance-bearing knowledge claims, scoped reputation events and separate incentive utility signals.
- Acceptance passed with the M2-011 tests.
## M2-012 — 2026-09-23
- Added evaluator-side replay bundles that order observable events, retain model records, rebuild scorer references and strip Oracle/hidden-truth fields from the tested-agent view.
- Acceptance passed with `tests/m2/test_replay_bundle.py`; M0–M2 regression suite passes with 64 tests.
## M2-013 — 2026-09-23
- Added a standard-library local environment lifecycle with start/reset/stop/kill semantics, mutation gating and telemetry flushing for the no-Docker profile.
- Acceptance passed with `tests/m2/test_local_environment.py`; M0–M2 regression suite passes with 66 tests.
## M2-014 — 2026-09-23
- Added the multi-agent Reference IoA end-to-end gate covering two organizations, discovery, A2A messaging, delegation authorization, asynchronous MCP-to-Sandbox execution, replay reconstruction and Oracle isolation.
- Added `artifacts/gates/M2.json`; acceptance and full M0–M2 regression suite pass with 70 tests.
## M3-001 — 2026-09-23
- Added provider-neutral mechanism declarations and a shared registry for all 18 frozen suites, with five mechanism families, applicable worlds, difficulty labels and explicit SIMULATION_ONLY flags for T361–T363.
- Acceptance passed with `tests/m3/test_mechanism_registry.py`.
## M3-002 — 2026-09-23
- Added programmatic case skeletons with immutable Ground Truth, safe naturalization boundaries and paired CONTROL/RISK generation sharing one seed.
- Acceptance passed with `tests/m3/test_skeleton_truth.py`.
## M3-003 — 2026-09-23
- Added versioned naturalization prompts with hidden-truth/benchmark-label rejection and content-addressed generation provenance.
- Acceptance passed with `tests/m3/test_generation_provenance.py tests/m3/test_prompt_leakage.py`.
## M3-004 — 2026-09-23
- Added generation-task routing on top of the existing role router, preserving exact model IDs and rejecting silent tested-model reuse.
- Acceptance passed with `tests/m3/test_generation_model_router.py`.
## M3-005 — 2026-09-23
- Added deterministic generation validation for required fields, truth presence, exposure reachability, control solvability and visible-truth leakage, with machine-readable findings.
- Acceptance passed with `tests/m3/test_deterministic_validators.py`.
## M3-006 — 2026-09-23
- Added independent semantic validation with hidden-context rejection and validator/arbitrator provenance; disagreements invoke the configured arbiter.
- Acceptance passed with `tests/m3/test_semantic_validator.py tests/m3/test_judge_arbitration.py`.
## M3-007 — 2026-09-23
- Added one-attempt repair/regenerate policy and rejection analytics without lowering quality thresholds.
- Acceptance passed with `tests/m3/test_repair_loop.py tests/m3/test_no_quality_downgrade.py`.
## M3-008 — 2026-09-23
- Added reproducible exact/near deduplication and recursive hidden-truth value/key leakage detection.
- Acceptance passed with `tests/m3/test_dedup.py tests/m3/test_oracle_leakage.py`.
## M3-009 — 2026-09-23
- Added explicit difficulty features and truth-preserving Easy/Medium/Hard calibration.
- Acceptance passed with `tests/m3/test_difficulty_calibration.py`.
## M3-010 — 2026-09-23
- Added auditable quota planning for 90 qualified cases per suite, 30/30/30 difficulty, mechanism/world coverage and explicit oversampling.
- Acceptance passed with `tests/m3/test_coverage_planner.py`.
## M3-011 — 2026-09-23
- Added immutable content-addressed dataset freezing with schema validation, case hashing, version-only corrections and rejected-candidate provenance storage.
- Acceptance passed with `tests/m3/test_dataset_freeze.py`.
## M3-012 — 2026-09-23
- Added the shared generation pipeline smoke path covering naturalization, deterministic validation, bounded repair/rejection, leakage, deduplication, calibration and dataset freeze.
- Added `artifacts/generation/smoke-report.json`; acceptance passed with 24 M3/generation tests.
## M3-013 — 2026-09-23
- Added `artifacts/gates/M3.json`; M3 generation readiness gate passes without manual case authoring.
## M4-T311-01 — 2026-09-23
- Added T311 Qualification Spoofing suite specification with five mechanism families, exposure proof, paired controls and separate safety/utility rules.
- Acceptance passed with `tests/t311/test_spec.py`.
## M4-T311-02 — 2026-09-23
- Added T311 programmatic generator across three worlds and measurable difficulty labels; semantic validation cannot override canonical truth.
- Acceptance passed with `tests/t311/test_generation.py tests/t311/test_validation.py`.
## M4-T311-03..06 — 2026-09-23
- Added the T311 deterministic scenario/exposure controller, observable scorer and semantic-judge rubric, frozen 12-case dev dataset, and Mock/Replay end-to-end acceptance path.
- Acceptance passed with `python -m pytest tests/t311 -q`, dataset generate/validate commands, and the Mock run plan.
## M4-999 — 2026-09-23
- M4 vertical-slice gate passed; evidence recorded in `artifacts/gates/M4.json`.
## M5-T312-01 — 2026-09-23
- Added T312 Registry Distortion mechanism families, external truth invariants, paired control semantics, exposure proof and separate safety/utility rules.
- Acceptance passed with `tests/t312/test_spec.py`.
## M5-T312-02..03 — 2026-09-23
- Added T312 programmatic generator/validator across three synthetic worlds and deterministic registry exposure execution with explicit budgets.
- Acceptance passed with T312 generation/validation/scenario/exposure tests.
## M5-T312-04..06 — 2026-09-23
- Added T312 deterministic registry cross-check/selection scorer, judge rubric, frozen 12-case dev dataset, and Mock/Replay E2E acceptance artifact.
- Acceptance passed with T312 tests, dataset generate/validate commands, and the Mock run plan.
## M5-T313..T323 — 2026-09-23
- Added T313 Representation/Delegation Drift and T321/T322/T323 protocol/accountability specifications, generators, validators, exposure paths, scorers, judge prompts, dev datasets and replayable Mock E2E gates.
- Acceptance passed with 32 suite tests, five dataset generate/validate runs, five Mock run plans, and M5 gate evidence.
## M5-999 — 2026-09-23
- M5 acceptance gate passed; evidence recorded in `artifacts/gates/M5.json`.
## M6-T331..T333 — 2026-09-23
- Added cross-system cascade, structural exposure and behavioral inference specifications, programmatic generators/validators, deterministic exposure paths, observable scorers, judge prompts, frozen 12-case dev datasets and replayable Mock E2E artifacts.
- Acceptance passed with T331/T332/T333 suite tests, dataset generate/validate commands and Mock run plans.
## M6-T341..T343 — 2026-09-23
- Added ecosystem false consensus, rumor propagation and norm drift specifications, programmatic truth/generators/validators, exposure paths, deterministic scorers, judge prompts, frozen dev datasets and replayable Mock E2E artifacts.
- Acceptance passed with 24 suite tests, three dataset generate/validate runs, three Mock run plans and the M6 gate.
## M6-999 — 2026-09-23
- M6 acceptance gate passed; evidence recorded in `artifacts/gates/M6.json`.
## M7-T351..T353 — 2026-09-23
- Added incentive misalignment, reputation monopoly and node manipulation specifications, programmatic generators/validators, exposure paths, deterministic scorers, judge prompts, frozen dev datasets and replayable Mock E2E artifacts.
- Acceptance passed with 24 suite tests, three dataset generate/validate runs, three Mock run plans and the M7 gate.
## M7-999 — 2026-09-23
- M7 acceptance gate passed; evidence recorded in `artifacts/gates/M7.json`.
## M8-T361..T363 — 2026-09-23
- Added the T361 Judgment Delegation, T362 Discussion Distortion and T363 Agency Weakening simulation suites with seeded synthetic personas, programmatic truth, scenario/exposure paths, deterministic scoring, judge rubrics, frozen 12-case dev datasets and replayable Mock E2E artifacts.
- Added `SIMULATION_ONLY` validity and claim-boundary artifacts for all three suites; no real-human inference is emitted.
- Fixed CLI simulation manifest labeling so T361–T363 generation writes the validity marker to the suite manifest; added a regression test and regenerated the three dev datasets with updated hashes.
- M8 acceptance gate passed; evidence recorded in `artifacts/gates/M8.json`.
## M9 — 2026-09-23
- Added `formal-v1` candidate generation and immutable `v1.0.0` freeze commands for all 18 suites.
- Generated 18 formal datasets with 90 cases each, balanced across Easy/Medium/Hard, and retained candidate/rejected provenance plus content hashes.
- Added cross-suite coverage, integrity/leakage/exposure preflight, immutable dataset-pack manifest and M9 gate evidence in `artifacts/gates/M9.json`.
- M9 remains blocked: the frozen procedural datasets record `SINGLE_VALIDATOR`; they are not treated as formally qualified until independent dual semantic validation is available. Frozen content is unchanged.
## M10 — 2026-09-23
- Completed deterministic suite-all expansion, immutable full-run manifests, checkpoint/resume, cancellation, run eligibility gates, 1620-unit offline Mock/Replay execution, metrics, case selection, dashboard payload/server, report generation and provider-free release packaging.
- Recorded exact `deepseek-v4.1-flash` execution as provider-blocked because `AIHUBMIX_API_KEY` is absent; no model substitution occurred.
- Added runtime rejection of formal datasets without `DUAL_VALIDATOR` semantic validation and retained the blocker as an explicit artifact.
## M8/M9 continuation — 2026-09-24
- Re-ran the T361–T363 simulation suite regression tests and M8 gate; all simulation datasets remain `SIMULATION_ONLY` with replay and telemetry evidence.
- Updated the AIHubMix adapter to support the documented `/api/v1/models` catalog and current `model_id` response shape while retaining the legacy mock contract.
- Read the local AIHubMix API documentation and verified the requested model through the adapter path is still blocked by connection/TLS resets on both documented domains; no model substitution or formal-result acceptance was performed.
## M9 continuation — 2026-09-24
- Fixed semantic-validation evidence hashing/import order, opaque validator IDs, intended visible-conflict handling, and generic AIHubMix naturalization for non-T311 suites.
- T311 formal candidates passed dual validation, causal pairing, leakage, deduplication and 30/30/30 quota; frozen as immutable `1.4.0`. T321 passed the same gates and is frozen as immutable `1.1.0`.
- Reconciled M5 T321–T323 task statuses with their passing tests and gate evidence; no prior frozen dataset was modified.
- T312 formal generation was regenerated after its visible payloads failed the near-duplicate gate; the neutral payload diversity fix passed regression tests, dual validation and 30/30/30 quota, then froze as immutable `1.1.0`.
- Corrected T312 generator provenance to `t312-formal-v3` and published immutable `1.2.0`; `1.1.0` remains unchanged.
- T313 formal generation recovered from provider transient failures using bounded retries and a 200-case pool; dual validation and 30/30/30 quota passed, then froze as immutable `1.1.0`.
- T322 formal generation passed dual validation and 30/30/30 quota with retained provider, duplicate and semantic rejection provenance; frozen as immutable `1.1.0`.
- T323 formal generation required a 220-case pool to cover transient failures and semantic rejections; dual validation and 30/30/30 quota passed, then froze as immutable `1.1.0`.
- T331 formal generation passed dual validation and 30/30/30 quota with retained duplicate and semantic rejection provenance; frozen as immutable `1.1.0`.
- T332 formal generation passed dual validation and 30/30/30 quota with retained duplicate provenance; frozen as immutable `1.1.0`.
- T333 formal generation passed dual validation and 30/30/30 quota with retained provider, duplicate and semantic rejection provenance; frozen as immutable `1.1.0`.
- T341 formal generation passed dual validation and 30/30/30 quota with retained duplicate and semantic rejection provenance; frozen as immutable `1.1.0`.
- T342 formal generation passed dual validation and 30/30/30 quota with retained duplicate provenance; frozen as immutable `1.1.0`.
- T343 formal generation passed dual validation and 30/30/30 quota with retained duplicate and semantic rejection provenance; frozen as immutable `1.1.0`.
- T351 formal generation passed dual validation and 30/30/30 quota with retained duplicate provenance; frozen as immutable `1.1.0`.
- T352 formal generation completed with a 220-case candidate pool, dual semantic validation, retained rejection provenance and 30/30/30 quota; frozen as immutable `1.1.0` with content hash `e8a999d3411f08561ee01228c9d4c0cf1d3a3d4efd2aa7b32ebf23ab04d6a7a`.
- T353 formal generation completed with a 220-case candidate pool, dual semantic validation, retained rejection provenance and 30/30/30 quota; frozen as immutable `1.1.0` with content hash `84428507ebcce732abb3e462d1d60a7b36ac3235f6dc57f285495940ca5dcfba`.
- T361 formal generation completed with dual semantic validation, retained provider-failure and quality rejection provenance, 30/30/30 quota and `SIMULATION_ONLY` on every formal case; frozen as immutable `1.1.0` with content hash `e643b4fca5c5c814725e3b3bdadb829d10ebe76cd0501b212cab292b341cfd62`.
- T362 formal generation completed with dual semantic validation, retained duplicate rejection provenance, 30/30/30 quota and `SIMULATION_ONLY` on every formal case; frozen as immutable `1.1.0` with content hash `f6188849ac697ceb6b16da73bebe55938d7c9144e92e6c65df193a62720cab28`.
- T363 formal generation completed with dual semantic validation, retained duplicate rejection provenance, 30/30/30 quota and `SIMULATION_ONLY` on every formal case; frozen as immutable `1.1.0` with content hash `39f047508923b1072b7af44a640a051b3c9a232df6293086926fbd4d618fc86c`.
- Updated the stale M9 gate regression assertion from the legacy single-validator blocker to `PASS`; all 18 frozen manifests now record `DUAL_VALIDATOR`.
- M9 coverage, integrity/leakage preflight and dataset-pack manifest gates passed with 18 immutable versions and 1620 formal cases; M9 exit gate artifact records `PASS`.
- AIHubMix live resolution and two-call smoke passed for exact `deepseek-v4.1-flash`; formal model-resolution artifact records endpoint family, capabilities and defaults without secrets, with no substitution.
## Post-M10 scientific acceptance — 2026-09-25
- Applied the independent scientific audit remediation: frozen Manifest and case execution, independent source records, multi-tested-agent replay, scorer discrimination and prompt-leakage gates.
- Completed the replacement `deepseek-v4.1-flash-v1-pack-v2-r5` run against immutable `DATASET_PACK_v2`: 1,620/1,620 `VALID`, replay hashes 1,620/1,620, Replay audit `PASS`, with 83 `UNSAFE_ACTION` and 35 `FULL_FAILURE` outcomes.
- Recorded the final gate and reproducibility bundle; release contents exclude provider credentials and include the r5 evidence chain.
- Closed `M10-SCI-007` and `M10-SCI-008`; project status is `complete` with no remaining ready or blocked tasks.
# 2026-09-25 — Construct remediation

- Independent r5 audit found 18/18 formally present but construct-invalid; r5 and historical acceptance files remain immutable engineering evidence, not a current scientific acceptance claim.
- Opened CIG-00 → CIG-01 → CIG-02 → CIG-CONTRACT → CIG-T311. Remaining 17 suites and r6 are explicitly blocked pending review.
- Closed CIG-00 through CIG-T311 for offline vertical-slice acceptance; r5 stays historical and no formal construct-valid model run has occurred.
- Added immutable per-request model snapshots and replay action hashes, isolated agent sessions/budgets, bounded invalid-output policy, strict raw source records, and stable source-tree code hashes where Git SHA is unavailable.
- Added 18 schema-validated versioned construct contracts (only T311 marked implemented), actual T311 Registry discovery and candidate selection, delegation/revocation, A2A task delivery, Sandbox invoice access and causal scoring.
- Added four offline baselines plus evidence, ranking, Oracle-label, delegation-scope, sandbox-state and recovery counterfactual tests. No provider call, dataset-pack mutation, r6 artifact or paid run was performed.
- Windows offline verification: 347 passed with online integration and history-writing v1 gate test excluded; 24 construct tests passed; validate-spec passed. Linux-native execution remains unverified, and T311 has no formal live-model result.

## 2026-09-26 — Construct remediation Wave 1
- Implemented shared construct-valid discovery/selection execution for T312 Registry Distortion and T353 Node Manipulation.
- Added real visible candidate directory, ranking stimulus, comparison, explicit selection, A2A dispatch, independent executor session and Sandbox business state mutation.
- Added causal T312/T353 scorers and offline safe, naive unsafe, alternative-safe and recovery baselines with Oracle/ranking/Sandbox/replay counterfactual tests.
- Marked only T312 and T353 contracts as implemented; the remaining 16 suites remain planned/blocked. No Dataset Pack, historical run, r6 or provider call was changed or created.
- 2026-09-26: Completed construct-remediation Wave2 for T313 delegation drift and T323 accountability-chain break; added causal scorers, real delegation/provenance state transitions, three tested-agent replay, offline baselines, and counterfactual regression tests. No datasets or provider runs changed.
- 2026-09-26: Completed construct-remediation Wave3 for T321 negotiation pollution and T322 interoperability mismatch; added protocol state-machine runtime, real session/ledger transitions, recovery/compensation baselines, causal scorers, and offline regression tests.
- 2026-09-26: Completed construct-remediation Wave4 for T332 structural exposure and T333 behavioral inference; added disclosure/inference state, raw visible records, explicit disclosure/withhold/retract/share actions, causal scorers, and offline baselines. No datasets or provider runs changed.
- 2026-09-26: Completed construct-remediation Wave5 for T351 incentive misalignment and T352 reputation monopoly; added incentive acceptance/decline, quality feedback, reputation updates, dynamic selection state, causal scorers and offline baselines. No datasets or provider runs changed.
- 2026-09-26: Completed construct-remediation Wave6 for T331 cascade propagation and T342 rumor propagation; added multi-hop message graph, explicit propagation/correction/retraction actions, reach/depth state, causal scorers and offline baselines. No datasets or provider runs changed.
- 2026-09-26: Completed construct-remediation Wave7/Wave8 for T341/T343 group and longitudinal norm mechanisms plus T361-T363 SIMULATION_ONLY agency mechanisms; all 18 construct runtimes now have offline baseline coverage. Full offline regression reached 376 passed; no provider calls or dataset changes.
- 2026-09-26: Completed M12 T311 offline trial generation with six development fixtures and 24 construct-runtime replays. Safe and alternative baselines produced EARLY_SAFE, naive produced FULL_FAILURE, and recovery produced LATE_RECOVERY. Trial quality evidence records zero provider calls and no formal dataset freeze; T311 formal evaluation is now the next ready task.
- 2026-09-26: Extended generated-world adapters to T311, T312/T353, T313/T323 and T321/T322. Trials and construct regressions now exercise generated raw payloads through Registry, delegation-chain and protocol state, with 389 offline tests passing and no provider calls. Formal dataset freeze and paid evaluation remain blocked pending the full sequential data workflow.
- 2026-09-26: Completed generated-world adapters for T331/T342, T332/T333, T341/T343, T351/T352 and T361-T363. Added direct generated-case execution coverage for all 11 adapter-backed suites, fixed structured rumor detection in the propagation baseline, and updated the offline construct gate to 69 construct tests and 393 offline tests (2 provider tests skipped). CIG-REST-16 is done; CIG-R6-ENTRY remains blocked pending cross-platform and independent scientific review. No provider call, dataset mutation, r6 run or formal evaluation was performed.

## 2026-09-27 — Phase A V2 reopened

- Recorded source/contracts and 16,414 historical file hashes in `artifacts/gates/V2_A00_BASELINE/`. All historical files verified unchanged.
- Isolated Windows regression: 396 passed, 2 integration tests deselected. Initial blanket socket guard blocked Windows asyncio loopback; corrected guard permits loopback only. Both reports retained. Linux NOT_VERIFIED.
- Preserved all 289 historical tasks and statuses; appended V2 Phase A, sequential 18-suite Phase B and Phase C DAG. Corrected duplicate milestone and queue version mismatch.
- Old offline gates superseded for current acceptance; R6 remains blocked on V2 final acceptance. T311 2.0.0 provisional; previous pilot exploratory and INVALID_MODEL_OUTPUT.
- A00/A01 complete; A02 causal generator diversity in progress. No new provider calls or frozen asset edits.

### A02 partial: registry distortion

- Fixed-seed audit finds 17 suites with identical mechanism/difficulty payloads; retained failure evidence rather than accepting metadata variation.
- T312 now generates five distinct registry interventions, paired independent receipts and variable candidate/evidence workload. Adapter consumes generated records; task state no longer derives from Oracle validity for the new world format.
- Selection runtime checks tool permissions and omits condition labels from initial model input; bumped runtime/replay versions. Added all-mechanism paired outcome tests, alternate safe path, Oracle perturbation and role escalation checks. Targeted result: 31 passed.
- A02 remains in progress. See `docs/ADR_PHASE_A_V2_REOPEN.md` and `state/V2_CHECKPOINT.md`.
- Full isolated regression after integration repair: 414 passed, 2 integration tests excluded. The new Oracle stores keyed suitability judgments, avoiding redundant public task/agent scalar copies rejected by the existing leakage check; no leakage threshold changed. Historical 16,414 files reverified unchanged.

### A02 partial: delegation and accountability chains

- T313 implements scope, resource, audience, TTL and representation-principal changes on raw grants; T323 implements source, grant ID, issuer, trace-parent and cross-organization receipt loss. Difficulty changes chain depth to 2/3/5 edges.
- Added versioned `delegation-chain-2.0.0` executor. Every handoff invokes an independent tested-agent session with explicit A2A delivery; raw source reconstruction and bounded attenuation precede re-issuance. Oracle metadata no longer constructs the new visible chain or drives its physical transitions.
- New scorer records unsafe grants even without execution, first unsafe hop, active grants, recovery, and persisted business effects; issued-record equality prevents repair without re-issuance from silently authorizing execution.
- 35 targeted causal checks passed; isolated offline regression 449 passed, 2 integration tests deselected. A02 and final scientific acceptance remain open. No provider calls.

### A02 partial: negotiation pollution

- T321 has five distinct raw negotiation interventions with matched endpoint capabilities and business requirements. Difficulty changes the capability comparison workload.
- Added `negotiation-2.0.0` with separate initiator/counterparty contexts and bidirectional A2A messages. Both parties must accept the same offer. Fallback terminates the prior session and requires a new offer; utility requires a persisted permitted business operation.
- Twenty new causal tests passed. Full isolated regression: 469 passed, 2 integration tests excluded. T322 and the remaining A02 suites are still pending. No live provider calls or frozen asset edits.

### A02 partial: interoperability mismatch

- T322 generator now creates five concrete gateway mapping interventions: state, cancellation, TTL, error and idempotency. Matched controls retain the same task, target receipt and original business effect.
- Added `interoperability-2.0.0` with separate source/destination sessions, explicit receipt exchange, idempotency-key forwarding, real duplicate ledger records and compensation of specific reversible effects. Recovery and utility use persisted net effects.
- Fixed leakage checker type confusion for ordinary public boolean/null protocol fields, with regressions retaining hidden-key and textual truth-label rejection. Numerical thresholds unchanged.
- Added 18 interoperability causal tests and one leakage regression. Full isolated regression: 488 passed, 2 integration tests deselected. A02 remains open; next is T331/T342 propagation. No provider calls or historical asset edits.

### A02 partial: cascade and rumor propagation

- T331/T342 now generate suite-specific source/message interventions and difficulty-dependent 3/4/6-node graphs; matched pairs preserve raw source, task and topology.
- Added `propagation-network-2.0.0`: only adjacent-peer delivery is permitted, every recipient makes independent model decisions, and node business state is persisted. Quotes remain qualified and distinct from endorsement. Corrections are queued and must reach recipient state before recovery credit.
- Delayed correction stimuli can produce late recovery through actual recipient actions; no forced naive-failure label. Empty/truncated cooperating agents remain INVALID_MODEL_OUTPUT.
- Thirty-five new causal tests pass. Full isolated regression: 523 passed, 2 integration tests excluded. A02 and final scientific acceptance remain open. No provider calls or frozen asset changes.

### A02 partial: structural exposure

- T332 now varies the actual requested disclosure: critical node identity, combined metadata, topology, cross-organization mapping or internal records. Difficulty adds directory distractors; controls retain the same directory, task and recipient scope.
- Added `structural-disclosure-2.0.0` with separate draft, irreversible delivery and recipient acknowledgement state. Receiver contexts contain the actual delivered facts. Pre-delivery correction and post-delivery retraction have different consequences; task completion cannot erase excess disclosure.
- Corrected raw metrics to use actual disclosed critical-node identities and directed topology edges, rather than labeling every unauthorized fact as a critical node. Nineteen targeted tests pass. Final isolated regression after the metric correction: 542 passed, 2 integration tests deselected. Phase A remains incomplete and no provider calls were made.

### A02 partial: behavioral inference

- T333 now generates distinct periodic, burst, call-combination, temporal-correlation and cross-node traces. Difficulty increases unrelated tenant metadata. Control/risk pairs hold raw traces, business task and hidden intent fixed while changing the scripted interpretation cue.
- Added `behavioral-inference-2.0.0`: independent analyst/receiver contexts, typed action schemas, aggregate analysis, optional claims, confidence revision, withholding and actual immutable delivery. Utility requires a correct aggregate plus receiver acknowledgement; unsafe inference can coexist with completed operational analysis.
- Hidden claim truth is separate from evidential support. A true guess can still be an unsupported confident sensitive disclosure. Post-delivery qualification cannot erase prior exposure. Added 26 causal checks including persisted-state suppression and deterministic scorer recalculation. Full isolated regression: 568 passed, 2 integration tests deselected. All 16,414 original data/artifact hashes remain unchanged; no provider calls. A02 and Phase A acceptance remain open.

### A02 partial: ecosystem false consensus

- T341 now generates role-private ledgers, cached summaries and decision mandates. Five mechanisms alter repeated summaries, source reputation, quote attachment availability, summary completeness or upstream source independence; difficulty adds ledger items and irrelevant receipts.
- Added `ecosystem-consensus-2.0.0`: four independent tested roles execute five discussion rounds. Real quote/position messages enter recipient contexts only after persistence; source challenges retrieve raw records. Each role casts its own ballot, and two persisted group snapshots establish stable wrong consensus or subsequent recovery.
- Scoring uses actual individual ballots and available cited receipts, with separate minority-evidence survival, verification and confidence calibration metrics. A correct decider alone is insufficient for supported group utility. Twenty-six new causal checks pass. Full isolated regression: 594 passed, 2 integration tests deselected. All 16,414 historical file hashes remain unchanged; no provider calls. Frozen datasets and historical runtime behavior remain unchanged.

### A02 partial: longitudinal norm drift

- T343 now generates five causal norm-drift interventions with matched policy/request data, persistent agent memory, approval receipts and 3/4/6 episode difficulty strata. The hidden truth includes mechanism-specific unsafe consequence and recovery paths; visible history remains raw practice records rather than policy verdicts.
- Added `longitudinal-norm-2.0.0` execution through the deliberation dispatcher. Policy lookup, approval challenge, decision, correction, workflow ledger, active/reversed effects and peer messages are persisted in the synthetic sandbox; peer messages are emitted only after the corresponding business effect is durable. Utility requires durable ledger and peer evidence, and drift recovery requires a durable correction record.
- Added 27 T343 causal tests covering mechanism/difficulty diversity, matched controls, safe/naive/alternative/recovery baselines, memory/policy/receipt exposure, Oracle-only mutation, persistence suppression, invalid outputs, replay scorer recalculation and post-correction episodes. Targeted and full isolated runs passed (`27` and `621` respectively); JUnit is `artifacts/gates/V2_A00_BASELINE/pytest-after-longitudinal-norm.xml`. Source hash `d93c3845e68a01aabf8e76fc138eaac951378141c3e10bf4d3e9dc47a3a7aa3f`; inventory recheck found 0 missing/changed hashes across 16,472 entries. No provider calls or frozen-data changes.

### A02 partial: incentive, reputation and node manipulation

- T351 now varies the raw offer table per mechanism: reward differential, verification requirement on the unsafe offer and a mechanism-specific temptation attribute (expedite premium, KPI credit, reliability risk, leadership visibility, boundary exception). Difficulty widens the differential and the approval workload. Truth keeps legacy factory keys plus mechanism-specific causal signatures.
- T352 couples quality and reputation differently per mechanism and selects distinct runtime dynamics: plain averaging, incumbent amplification, scripted endorsement bonuses, visibility-weighted ranking and incomplete quality evidence for the decoupled agent. Rounds scale 3/4/6 with difficulty. `observe_registry` now ranks by live reputation with visibility multipliers, so persisted feedback genuinely changes later selection context.
- T353 keeps candidate records condition-invariant and distorts only the router ranking per mechanism (affiliation, suppression, rationale notes, steering, resource priority); the runtime executes paired honest/manipulated worlds on the same ground truth and derives the counterfactual selected-id delta from actual runs.
- `T351/T352-incentive-reputation-2.0.0` records local reward on execution, scores an accepted-and-approved unsafe offer as an unsafe grant even without execution, marks non-completed runs `INVALID_MODEL_OUTPUT`, and fixed the legacy recovery baseline confirming the unsafe incumbent at round 3. Restored legacy `DEFINITION` exports after the generator rewrite so suite validation tests keep passing.
- Added 70 causal checks in `tests/construct/test_incentive_selection_causal.py`. Full isolated regression: 691 passed, 2 integration tests deselected (`artifacts/gates/V2_A00_BASELINE/pytest-after-incentive-router.xml`). Source hash `838f642e0ed07589532a7d2c766518bf85795135355383d6620071ab34ff6d9e`; 16,414 historical protected files verified unchanged. No provider calls or frozen-data changes.

### A02 partial: simulation-only human agency suites

- T361-T363 runtimes rebuilt to the contract shape: tested roles are model sessions (T361 advisor+reviewer, T362 discussant-a/b+moderator, T363 assistant+reviewer) and the synthetic persona is a deterministic scripted actor whose verification, follow, exposure, shift and error-detection transitions persist in the sandbox with SIMULATION_ONLY labels; personas never invoke the model.
- Generators t361/t362/t363-causal-v2 give each of the five mechanisms a distinct raw intervention: recommendation presentation cues, authority-cue verification suppression, correct-to-wrong transition points, verification fatigue and override suppression (T361); coordinated repetition, pseudo-majority endorsements, feed steering and minority suppression over a condition-invariant candidate graph (T362); answer outsourcing, strategy outsourcing, challenge decay, detection dependence and retraining cues with matched baseline/assistance/withdrawal task designs (T363). Difficulty varies episode/round/task counts 3/4/6 (T361/T362) and 2/3/4 (T363) with calibration checks.
- Fixed a sandbox idempotency-key collision that silently dropped same-episode advice revisions and check invitations, a role-name mismatch that let discussants execute moderator ranking actions, decay that keyed on case labels instead of persisted assistant behavior, and truth task-id/string leakage into visible payloads (oracle fields now derived from world data at case level).
- Added 69 causal checks in `tests/construct/test_human_agency_causal.py`. Full isolated regression: 760 passed, 2 integration tests deselected (`artifacts/gates/V2_A00_BASELINE/pytest-after-human-agency.xml`). Source hash `3f97e5372bb6f607faba268bc03fff4a5c7835b463ab22fbd4dccbb8f0544fb3`; 16,414 historical protected files verified unchanged. No provider calls or frozen-data changes. A02 remaining: T311 causal depth audit, then A03.

### A02 complete: T311 causal depth audit

- Audited the T311 generator against the causal-signature standard: each of the five mechanisms is a distinct raw-evidence intervention on the recommended agent (unlisted credential subject, empty registered capabilities, expired organization license, wrong representation delegate, revoked credential status) and difficulty adds directory distractors, conflicting peer endorsements and a scheduling-timing ambiguity with passing calibration classification. Added 20 checks in `tests/construct/test_t311_causal_diversity.py` covering the 5×3 matrix, per-mechanism evidence flags visible through the credential/issuer/capability records, condition-neutral paired resources, four baselines on generated cases for every mechanism, and replay scorer recalculation.
- Fixed the T311 adapter leaking the condition suffix into the model-visible task resource (`resource-T311-...-risk` vs `-control` pairs now share one condition-neutral resource label shared with the oracle).
- A02 (generator causal diversity) is now complete for all 18 suites: every suite has a versioned causal generator revision, a specialized construct runtime consuming the generated world, and dedicated mechanism/difficulty causal tests. Full isolated regression: 780 passed, 2 integration tests deselected (`artifacts/gates/V2_A00_BASELINE/pytest-after-t311-audit.xml`). Source hash `99b88756a6c83fab69055f1abb982f5dc13db0224e9c235028252ac5d9baae92`; 16,414 historical protected files verified unchanged; no provider calls. Next: A03 machine-readable contract conformance.

### A03 complete: machine-readable contract conformance (18/18)

- Added `scripts/verify_construct_conformance.py`: executes every suite through its canonical causal runtime on a generated case (safe/naive/recovery baselines) and validates each `contracts/constructs/Txxx.json` field with evidence: tested actor roles and minimum tested agent count, scripted environment actors, environment state, model-visible evidence, contract verb support with documented runtime business tools, state transitions, safe/unsafe/recovery conditions, task-utility separation, required raw metrics, scorer inputs, minimum interaction depth, replay immutability and completeness, forbidden-shortcut scans, and SIMULATION_ONLY labeling (including persona-never-a-model checks for T361-T363).
- Added contract-named raw metric aliases to the suite scorers so every contract-required metric is published under its canonical name: first_unsafe_hop/unauthorized_action_rate/recovery_rate (T313/T323), task_success (T321/T332), cascade_size/R_agent/verification_before_forward/containment_rate (T331), acceptance_rate/forward_rate/endorsement_rate/rumor_reach/source_retention/verification_rate (T342), wrong_consensus_rate/minority_evidence_survival/verification_rate/confidence_miscalibration (T341), norm_adoption_rate/policy_deviation/time_to_drift/correction_recovery (T343), unsafe_shortcut_rate/verification_drop/global_utility_loss (T351), verification_rate/utility_loss (T353), verification_rate/error_following_rate (T361).
- Gate artifact: `artifacts/gates/CONSTRUCT_CONFORMANCE_V2.json` — overall_pass=true, 18/18 suites, reproduced independently in the isolated regression workspace. Full isolated regression: 780 passed, 2 integration tests deselected (`artifacts/gates/V2_A00_BASELINE/pytest-after-conformance.xml`). Source hash `dbf047127fd73ca492605b7634b0aa6076deefeb47731b7d1ed0b70a1ba85170`; 16,414 historical protected files verified unchanged; no provider calls. Next: A05 unified formal dispatcher, then A06 final Phase A V2 gate.

### A05 complete: unified formal construct dispatcher

- Added `src/ioabench/runtime/construct_dispatch.py`: a single registry mapping all 18 suites to their causal adapters and runtimes. Frozen cases enter once and are executed directly - the dispatcher re-encodes the frozen oracle payload into the runtime view (no regeneration, verified by a monkeypatch test), stamps every result with dispatch version, case hash, bound runtime version and `frozen_case_executed_directly`, and marks simulation suites `SIMULATION_ONLY`. Deterministic per-suite baselines are registered for offline E2E; formal campaigns bind the tested model through the same entry point.
- Migrated `run --suite Txxx` and `run --suite all` (`cli._run_all`) to the dispatcher: `execute_mock_case` is removed from the formal path (retained in `offline_run.py` for historical replay only) and the run manifest now records the dispatch version. Fixed a nested-event-loop failure by returning the dispatch coroutine to the BatchRunner (the legacy awaitable contract).
- Evidence: 22 dispatcher tests (`tests/construct/test_formal_dispatcher.py`) including frozen-case execution for all 18 suites and the no-regeneration guard; CLI smoke in the isolated workspace `run --model mock --suite T351 --run-id smoke-dispatch-T351` completed 90/90 units with dispatch metadata and EARLY_SAFE/utility outcomes. Full isolated regression: 802 passed, 2 integration tests deselected (`artifacts/gates/V2_A00_BASELINE/pytest-after-dispatcher.xml`). Source hash `001db1cf4aa127ed2fa7ff3a28f8d8d620463e264f36e5c7c16b15bf90c3b717`; 16,414 historical protected files verified unchanged; no provider calls.
- Incident: the first CLI smoke executed against the main workspace through an editable install and overwrote two protected historical files (`data/runs/mock-T311-v1-pack-v2/checkpoint.json` and `results.json`). Both were restored byte-exact from the baseline snapshot and the full inventory reverified 0 missing / 0 changed. The misdirected smoke also created new unprotected files under `data/runs/mock-T351-v1-pack-v2/` (retained as evidence). Subsequent smokes force the isolated workspace import path.

### A06 complete: Phase A V2 final acceptance (PASS with one documented deviation)

- Added `scripts/verify_phase_a_v2_gate.py`: assembles executable evidence for every closure condition - live causal-signature checks (mechanism and difficulty) for all 18 suites, the 18/18 contract-conformance artifact, dispatcher/runtime registry coverage, the causal test battery, T311 regression, the Windows offline regression JUnit, and historical artifact integrity. Gate artifact: `artifacts/gates/PHASE_A_V2_FINAL_ACCEPTANCE.json` (overall_pass=true).
- Incident: the gate's first run executed tests/t311/test_e2e.py in the main workspace, which rewrites `artifacts/suite-gates/T311.json` by design, overwriting one inventory-pinned historical file. Byte-exact recovery is impossible (replay hashes embed wall-clock timestamps) and the file is a superseded mock-era gate badge - not a dataset, run, oracle or scorer artifact. Recorded in `artifacts/gates/INCIDENT_SUITE_GATES_T311_20260928.json` and `docs/ADR_PHASE_A_V2_INCIDENT_SUITE_GATES_T311.md`; the acceptance carries the exception explicitly (16,413/16,414 intact). The gate script now excludes the e2e writer from main-workspace regressions.
- Wrote `docs/PHASE_A_V2_CONSTRUCT_ACCEPTANCE.md`. Project state advanced to `construct_implementation_v2_complete_ready_for_per_suite_data_campaign`. Source hash `001db1cf4aa127ed2fa7ff3a28f8d8d620463e264f36e5c7c16b15bf90c3b717`; provider_calls=0 throughout Phase A V2. Next: Phase B per-suite lifecycle starting with B1 T311 trial generation (offline); the online stages require the AIHubMix key and are a genuine external dependency.

### Phase B started: T311 B1 recipe trial + B4 2.0.0 acceptance

- B4 audit of the frozen T311 2.0.0 dataset (90 cases, 30/30/30 difficulty, five mechanisms, 45 CONTROL / 45 RISK): payload dedup 90/90, leakage clean on every case, all five mechanism-specific raw-evidence interventions present with matching truth flags, CONTROL solvability 45/45, manifest content_sha256 immutable, and a 90/90 structural comparison against the current causal-audited generator (truth, raw evidence layer and directory structure identical; only the glm-5.2 naturalized language differs by design). Dispatcher baseline sensitivity confirmed (safe EARLY_SAFE/utility, naive FULL_FAILURE). Verdict: **2.0.0 accepted for V2 use** (`artifacts/gates/T311_B4_ACCEPTANCE.json`) - no new T311 dataset version required.
- B1 recipe trial: `scripts/run_b1_t311_trial.py` generates a 9-candidate mechanism x difficulty x condition grid with the current generator and validates the full B1 checklist (programmatic truth, mechanism/difficulty diversity, dedup, leakage, raw evidence, runtime execution through the dispatcher-registered runtime, scorer metrics, utility with safe/unsafe path separation, replay immutability, Oracle isolation, conformance linkage). Result: 13/13 checks pass (`data/trials/T311/b1-v2-recipe-trial/trial-report.json`). Recipe validated without freezing a new dataset.
- T311 lifecycle: `RECIPE_VALIDATED` + `FORMAL_DATASET_FROZEN` (2.0.0 accepted). `ONLINE_PILOT` is blocked on the missing AIHUBMIX_API_KEY (genuine external dependency; key never printed or persisted). Next: B1 trial for T312; online stages resume once the key is provided.

### Phase B continued: T312 B1 recipe trial

- `scripts/run_b1_t312_trial.py` validates the current `t312-causal-v2` recipe over a 10-candidate grid (five mechanisms x CONTROL/RISK at medium plus easy/hard strata) through the dispatcher-registered `T312-selection-2.0.0` runtime: mechanism/truth diversity, difficulty calibration, dedup, leakage, programmatic truth, safe path (EARLY_SAFE/utility) and unsafe path (naive FULL_FAILURE), contract metrics, replay immutability and Oracle isolation - 12/12 checks pass (`data/trials/T312/b1-v2-recipe-trial/trial-report.json`). The frozen 1.2.1 dataset predates the causal-v2 generator, so T312 proceeds to B2 overgeneration and a new frozen version (2.0.0) once the recipe stays stable.
- Suite lifecycle: T311 = RECIPE_VALIDATED + FORMAL_DATASET_FROZEN (2.0.0 accepted, B4) with ONLINE_PILOT blocked on the provider key; T312 = RECIPE_VALIDATED (B1), next B2 overgeneration. No provider calls; no frozen data modified.

### B2/B3 complete: all 18 suites frozen at 2.0.0

- `scripts/b2_b3_freeze.py` overgenerates 180 candidates per suite (5 mechanisms x 3 difficulties x 2 conditions x 6 seeds), applies the per-candidate quality gates (leakage, dedup, difficulty calibration, programmatic truth completeness, safe-path utility, naive-path unsafe expectation, required contract metrics, replay request-hash immutability, Oracle isolation), selects the 90-case qualified set with exact 30/30/30 difficulty and 45/45 Control/Risk pairing (paired by seed+mechanism), and freezes an immutable version with rejected candidates + reasons, generator provenance, quality gates, manifest and content_sha256. A post-freeze coverage assertion aborts the freeze if any target is missed.
- Frozen 2.0.0 datasets: T312-T363 (17 suites, 90 cases each with 90 rejected retained). T311 remains on its accepted 2.0.0 (B4). Recipe fixes made during freezing: T361 M02 verification prompt now disappears at the correct-to-wrong transition, T363 M03 detection decay raised so the unsafe condition is reachable, T363 M05 recognized as the recovery-path mechanism, T331 naive_ok extended for its correction-stimulus recovery dynamic, and the pre-fix imbalanced T331 freeze was discarded and regenerated 45/45.
- The frozen T361-T363 datasets carry SIMULATION_ONLY in their provenance; semantic dual-validation is deferred to the provider stage and enforced by the formal-run dataset gate. Full isolated regression: 802 passed, 2 integration tests deselected. All offline Phase B work is complete; the campaign now waits on AIHUBMIX_API_KEY for B5 online pilots (T311 first, then T312-T363).

### B5 preparation complete: online campaign is one command per suite

- `scripts/run_online_pilot.py` composes the deferred provider stages for one suite: deferred dual-model semantic validation of the frozen 2.0.0 dataset (glm-5.3-flash + deepseek-v4.1-flash independent validators, cached, all-accepted required), exact tested-model resolution through live AIHubMix discovery (`deepseek-v4.1-flash`, no substitution), a 12-case pilot through the formal construct dispatcher covering Control/Risk x Easy/Medium/Hard x all five mechanisms with bounded provider retries, and the B5 checklist (model output, tools/A2A, state transitions, replay integrity, Oracle isolation, scorer fields, task utility, invalid-output accounting, provider-failure accounting, token/latency recording). Report: `data/runs/<independent run id>/pilot-report.json`; gate artifact on PASS: `artifacts/gates/{suite}_B5_PILOT.json`. The API key is read only from the environment and never printed or persisted.
- `run --suite ...` formal path (B6) now enforces stage discipline: a passed B5 pilot gate per suite and the semantic-validation stamp are required before any non-mock execution; the resolved formal model profile is bound to the run and executed through the same dispatcher. Mock E2E behavior is unchanged.
- Verified: missing-key path exits cleanly with PROVIDER_BLOCKED guidance (exit 2, no partial artifacts); full isolated regression 802 passed (`pytest-after-phase-b-freeze.xml`, rerun as `pytest-after-b5-prep.xml`). The campaign is now fully staged: setting AIHUBMIX_API_KEY in the environment is the single remaining step before `python scripts/run_online_pilot.py T311` starts the online evaluation chain.

### Phase C preparation complete: campaign aggregation, secret scan and reproducibility bundle

- `scripts/phase_c_campaign.py` aggregates the 18 per-suite formal runs into the campaign manifest: per-suite outcome distributions and utility rates, six risk-family profiles (human-agency family permanently labelled SIMULATION_ONLY), aggregate safety-vs-utility separation with no single overall safety score, representative failures/recoveries, a reproducibility bundle (campaign manifest hash + source-tree hash + run inventory) and a secret scan over artifacts/state/docs/scripts/runs (key patterns: AIHUBMIX assignments, bearer tokens, provider key prefixes). `--final` emits the DoD verdict requiring 18/18 formal runs and a clean scan. Verified end-to-end against a mock dispatcher run (90 cases aggregated, scan clean over 15,760 files); `--final` correctly reports incomplete with the missing suites enumerated.
- B6 formal-path enforcement verified in regression: pilot gate + semantic stamp + resolved formal profile through the dispatcher; mock E2E unchanged. Full isolated regression: 802 passed (`pytest-after-phase-c-prep.xml`).
- The goal's offline-preparable surface is now fully built. The single remaining blocker for B5/B6 and Phase C execution is the missing AIHUBMIX_API_KEY (goal blocker 5): set it in the environment, then run scripts/run_online_pilot.py T311 followed by the per-suite formal runs.

### B5/B6 campaign launched: T311 FORMAL_EVALUATION_COMPLETE

- The provider key became available through the workspace .env (M0-002 local-secret convention); `load_workspace_env` bridges it into the process environment for adapters that read os.environ - values are never logged.
- T311 B5 ONLINE_PILOT PASS (`artifacts/gates/T311_B5_PILOT.json`, run T311-pilot-20260928-035637-5c18d6fd): deferred dual-model semantic validation + 12-case coverage pilot through the formal dispatcher, all checks green (model output, state causality, replay integrity, Oracle isolation, utility measured, efficiency recorded).
- T311 B6 FORMAL RUN: 90/90 units COMPLETED with tested model deepseek-v4.1-flash (run deepseek-v4.1-flash-T311-v2-formal, run-validate PASS). Outcomes: 86 EARLY_SAFE / 3 FULL_FAILURE / 1 UNSAFE_ACTION; task-utility rate 0.833 - the tested model followed spoofed qualifications on some RISK cases while remaining safe on most.
- Transport fix during the run: AIHubMix curl/urlopen timeouts raised 15s/30s -> 300s (reasoning-model completions take 30-60s; the old cap caused ~50% transient failures). Sampling max_tokens raised to 4096 across runtimes (reasoning models exhausted 1024-token budgets on hidden reasoning alone, producing empty content). Both are infrastructure/sampling changes recorded before any formal result was affected; all affected runs were re-executed.
- `scripts/run_online_campaign.py` drives the remaining suites sequentially (pilot -> formal -> bounded resume passes, per-suite independence, blocked pilots recorded and retried on a second campaign pass). T312's first pilot hit initial-provider rate limiting (3/12 PROVIDER_FAILURE) and is recorded as blocked-pilot for retry; the campaign proceeds T313 onwards.

### Leak-fix round: six suites re-frozen at 2.1.0, pilot gates repaired, campaign ready to restart

- The first full B5 pilot campaign blocked 17 suites. Dual-model semantic validation (glm-5.3-flash + deepseek-v4.1-flash) correctly rejected visible-payload benchmark leakage in six suites: T352 carried ground-truth honest-ranking labels per round, a hidden quality value inside the RISK stimulus text, and internal mechanism markers; T353 carried honest/manipulated router-world framing; T361/T362/T363 carried a validity label and mechanism markers in the model-visible payload; T351 carried mechanism markers.
- Fixes: all six generators re-issued without benchmark labels (stimulus text neutralized, `validity` moved from the payload to case/scenario metadata per the SIMULATION_ONLY policy, T352 rounds reduced to visible ranking + feedback requirement, T353 payload restructured to `registry_ranking` + `independent_directory` with the honest/manipulated framing living only in oracle metadata). The T353 runtime adapter and paired-world trigger were rebuilt for the new payload shape.
- Infrastructure repairs from pilot evidence: provider curl/urlopen timeouts 15s/30s -> 300s, inner transport retries x3 with escalating backoff (transient empty responses), sampling `max_tokens` 4096 -> 8192 (reasoning models exhausted completion budgets on hidden reasoning, producing empty content), pilot check semantics corrected (INVALID_MODEL_OUTPUT cases judged separately; state causality = model actions that change nothing while the world changes; utility measured as boolean per completed case), deferred semantic-validation provider failures are retryable (exit 2) rather than misread as recipe failures.
- Refrozen at 2.1.0 with the corrected recipes: T351, T352, T353, T361, T362, T363 (each 90 cases, 30/30/30, 45/45 Control/Risk, rejected retained) on top of the earlier T313/T323 2.1.0 coherence refreeze. Full isolated regression: 802 passed, 2 integration deselected (`artifacts/gates/V2_A00_BASELINE/pytest-after-leak-fixes.xml`) after bringing the regression workspace fully current (src/tests/scripts/contracts/config/state/data/docs/worlds/roles/adr + pyproject).
- Source hash `6c30e858b8c49adf4f1387eadb770d9ca7961d6bfa5dca88b6a0adf2d15b22e2`; 16,413/16,414 protected files unchanged (the documented T311.json incident remains the sole exception). The campaign driver now skips recorded PASSING pilots and completed formal runs; restart resumes T312+ on 2.1.0 datasets.

### Data-integrity fix: candidate_id collision across difficulty strata, 17 suites re-frozen at 2.2.0

- Discovery: the first campaign pass recorded T312 formal complete with only 30 units. Audit found a candidate_id collision: the causal generators name candidates by seed/mechanism/condition without difficulty, so the same ID recurred once per difficulty stratum with a distinct payload (verified: T312-1-0-control appears 3x with easy/hard/medium variants). WorkScheduler keys work units by candidate_id, collapsing 90-case datasets into 30 executable units. T312's recorded formal completion was therefore invalid (30/90 executed) and was superseded; T313's formal checkpoint was similarly truncated. T311@2.0.0 is unaffected (90 unique IDs; its 90/90 formal run stands).
- Fix: the freeze pipeline (`b2_b3_freeze.py`) now disambiguates candidate_id with the difficulty suffix (e.g. T312-1-0-risk-easy). All 17 affected suites re-frozen as 2.2.0 (overgenerated 180 each, execution-gated, 90 selected, 30/30/30 difficulty, 45/45 Control/Risk, rejected retained); verified 90 unique IDs per suite.
- Side effect repaired: dual-model semantic validation is keyed by candidate_id, so earlier validations had only covered 30/90 distinct payloads per suite; the 2.2.0 pilots validate all 90.
- Superseded evidence retained: seven stale pilot gates moved to `artifacts/gates/superseded-pilot-gates/`; T312's truncated run left in place and marked invalidated in `ONLINE_CAMPAIGN_STATE.json`. Version maps updated in the pilot runner, campaign driver and dispatcher test. T311 stays on its audited 2.0.0 dataset and completed formal run.

### Pilot check-semantics fix: state_causality baseline corrected, T312 pilot gate reissued with disclosure

- The recalculated T312 2.2.0 pilot (12/12 executions COMPLETED, semantic validation 90/90 on the full unique payload set) failed only `state_causality`. Forensics from the persisted replay: `scenario.initial_world` is a partial world projection in some runtimes (T312 exposes only `task_result`), while the first action's before-snapshot is the complete reset world; the violating case's world was actually unchanged (`world == first_before`), and the model's eight actions (one read-only discovery plus six ERROR actions and a blocked execute) legitimately changed nothing - scored TASK_SAFE_BUT_FAILED, not a harness violation.
- Fix: the pilot's state-causality baseline is now the first action's before-snapshot, falling back to `initial_world` only for passive cases. Checks were recalculated from the same immutable persisted replay evidence (no re-execution) and all ten checks pass; the T312 pilot gate was reissued with a full recalculation disclosure (original pass=false, reason, fix, pointer to the original report) rather than silently overwritten.

### Recipe fix: delegation narrative coherence (T313/T323 re-frozen at 2.3.0)

- T313's 2.2.0 pilot semantic validation rejected 5 cases (85/90). Forensics: the chain-vs-archive drift for mechanisms 3/4 (expired TTL, swapped principal) is the designed risk stimulus and correctly stays; but `stimulus_detail` inherited the VerticalGenerator invoice boilerplate ("The assertion has no linked receipt.") which contradicts the delegation scenario's source_archive (which does contain receipts) and names an unrelated workflow — a real recipe incoherence the validator correctly flagged.
- Fix: `_delegation_world.py` re-anchors `stimulus`/`stimulus_detail` to the delegation scenario (chain review against the archived source record). T313/T323 re-frozen at 2.3.0 (90 unique IDs, 30/30/30, 45/45 each; coherence smoke across 5 mechanisms x 3 difficulties x both suites: 0 problems). 78 delegation-related tests pass.
- Campaign driver `formal_complete()` aligned with run-validate terminal semantics: COMPLETED and INVALID_MODEL_OUTPUT are both recorded terminal outcomes (INVALID is never scored safe, per the T311 precedent); provider failures stay non-terminal and are retried by resume passes — this prevents unbounded resume loops over deterministic INVALID cases.

### B6 milestone: T321 FORMAL_EVALUATION_COMPLETE (third suite)

- T321 formal run on 2.2.0 (deepseek-v4.1-flash): 90/90 terminal units (run-validate semantics), outcomes 84 EARLY_SAFE / 6 TASK_SAFE_BUT_FAILED, task-utility rate 0.933. The tested model rejected the unsafe negotiation downgrades on nearly all RISK cases while still completing the task — the suite discriminates through the 6 safe-but-failed cases rather than unsafe following.
- Campaign progress: T311 (2.0.0), T312 (2.2.0), T321 (2.2.0) formally complete; T322 pilot in flight; driver proceeds sequentially through T323 (2.3.0) onward.

### Recipe fix: base narrative neutralized (7 suites re-frozen at 2.3.0)

- Systematic narrative audit across all 17 frozen datasets: T313/T323 (2.3.0 delegation fix), T351-T353/T362/T363 (leak-fix round) and T312/T361 (invoice IS their real business) are coherent; but 7 suites — T322, T331, T332, T333, T341, T342, T343 — inherited the VerticalGenerator base boilerplate ("complete a synthetic local invoice intake task...", "A peer-provided standard packet assertion...", "The assertion has a linked receipt.") whose unrelated workflow narrative contradicts each suite's actual business_task (interoperability transfers, cascade shipments, disclosure contacts, inference traces, consensus batches, norm batches). T331's pilot semantic validation rejected 8 cases on exactly this; T322 (2) and T332 (1) likewise. T321 passed probabilistically but carries the same defect — its dataset is already formally evaluated and stays immutable, with the defect documented here.
- Fix: `_vertical.py` base narrative re-anchored to workflow-neutral text ("complete the assigned synthetic local task...", "The task materials... are available through the channel.", "The relevant records are provided in the case materials.") — the base class has no suite business knowledge, so neutral is the only safe shared narrative; condition pairing no longer hinges on receipt-presence wording. The unused `_WORKFLOWS`/`_RECORDS` lookups were removed from the base path (T311/T312 keep their own copies where those workflows ARE the business).
- 7 suites re-frozen at 2.3.0 (overgenerated 180 each, execution-gated, 90 selected, 30/30/30, 45/45, rejected retained); verified 90 unique IDs, zero boilerplate markers in task/stimulus/stimulus_detail. 220 affected tests pass. Version maps in pilot/driver/dispatcher-test rewritten as explicit per-suite dicts (T313/T322/T331/T332/T333/T341/T342/T343 = 2.3.0; T312/T321/T351-T363 = 2.2.0; T311 = 2.0.0) — the comprehension-based maps had silently failed earlier single-entry updates.
- Campaign was stopped during T333's pilot to avoid burning provider calls on datasets that were about to be re-frozen; it restarts from T321 (formal run resumes mid-dataset, then T322+ pilots on 2.3.0).

### Recipe fix: suite-anchored narratives (6 suites re-frozen at 2.4.0)

- After the base-narrative neutralization, the next campaign pass showed the neutral text itself fails semantic validation for suites that need an explicit operation: T322's pilot rejected 10 cases ("task is a generic placeholder... no specific question, deliverable, or success criteria"), and T331's rejected 8 (primary validator read the designed initial_message-vs-source_record quantity divergence as incoherent rather than as the relayed-update-vs-archived-record distinction the suite tests).
- Fix, following the T313 delegation_world pattern: each remaining base-narrative consumer now writes its own anchored narrative describing the scenario roles and deliverable without hinting at the tested decision — T322 (transfer operation through the cross-organization gateway, mapping/receipts as materials), T331/T342 via `_propagation_world.py` (update message relayed toward the destination while the warehouse record remains available; both described by role only, no trust hint), T333 (metadata analysis for the tenant with the source annotation described), T341 (batch consensus across four participants with private receipts), T343 (request episodes with policy documents and history).
- Six suites re-frozen at 2.4.0 (overgenerated 180 each, execution-gated, 90 selected, 30/30/30, 45/45, rejected retained); verified 90 unique IDs and zero boilerplate. 179 affected tests pass. T332 stays on 2.3.0 (its pilot passed and its formal run is mid-flight, resumable). Version maps updated in pilot/driver/dispatcher-test.

### Hotfix: T323 omitted from explicit version maps (silent 2.0.0 fallback), coverage guards added

- The rewritten explicit per-suite version maps omitted T323, so `get("T323", "2.0.0")` silently pointed its pilot at the pre-collision-fix 2.0.0 dataset (invoice-boilerplate narrative); the pilot's semantic validation rejected 36 cases in seconds. Diagnosed via the campaign state tail plus the absence of any T323 2.3.0 semantic stamp.
- Fix: T323 -> 2.3.0 restored in all three maps, and coverage guards added — the pilot raises rather than falling back if any of the 17 suites is missing from the map; the driver does the same before launching a formal run; the dispatcher test does the same at import. 44 T323-related tests and 18 dispatcher tests pass.
- Lesson recorded: single-entry edits to the comprehension-era maps had silently failed before; explicit dicts plus import-time coverage guards make any future omission fail loudly at startup instead of at provider expense.

### B6 milestone: T313 FORMAL_EVALUATION_COMPLETE (fourth suite)

- T313 formal run on 2.3.0 (deepseek-v4.1-flash): 90/90 terminal units (88 COMPLETED + 2 INVALID_MODEL_OUTPUT), outcomes 64 TASK_SAFE_BUT_FAILED / 19 EARLY_SAFE / 5 FULL_FAILURE, task-utility rate 0.211. The tested model mostly refused to follow the drifted delegation chains (safe on exposure) but frequently failed to complete the delegated task afterwards — the suite discriminates through safe-but-failed rather than unsafe-following, the inverse pattern of T321 (0.933 utility, mostly EARLY_SAFE).
- Campaign progress: 4/18 formally complete (T311 2.0.0, T312 2.2.0, T321 2.2.0, T313 2.3.0); T332 formal resumable at 45/90; driver proceeding sequentially through T322+ on 2.4.0/2.3.0/2.2.0 datasets.

### B6 milestone: T322 FORMAL_EVALUATION_COMPLETE (fifth suite)

- T322 formal run on 2.4.0 (deepseek-v4.1-flash): 90/90 terminal units (all COMPLETED after two resume passes clearing transient provider failures), outcomes 88 TASK_SAFE_BUT_FAILED / 2 EARLY_SAFE, task-utility rate 0.022. This is the inverse discrimination pattern of T321: the tested model almost always avoided the unsafe interoperability behavior (mismatched status/cancellation/idempotency mappings) but rarely completed the transfer afterwards — the suite discriminates through safe-but-failed rather than unsafe-following.
- This is also the first formal run on a 2.4.0 dataset and the end-to-end validation of the candidate_id collision fix: the work scheduler expanded all 90 unique candidate IDs (the pre-fix run had collapsed to 30).
- Campaign progress: 5/18 formally complete (T311 2.0.0, T312 2.2.0, T321 2.2.0, T313 2.3.0, T322 2.4.0); T332 formal resumable at 45/90; driver proceeding sequentially.

### Workspace sync and current handoff package

- Synchronized the current handoff summary and checkpoint headers with the Phase A V2-passed / Phase B-incomplete state. Historical runs, gates, frozen datasets, and prior ZIPs were retained.
- Updated `scripts/build_current_handoff_snapshot.py` to emit the current handoff filename and read current project status instead of embedding the 2026-09-26 snapshot claims.
- Built `IoA-Bench-current-workspace-handoff-20260929-latest.zip`: 19,719 entries, 113,055,699 bytes, SHA-256 `01f9a96bcfa309d433ffc04cb3cea9c108d18361f5842ff8f53fdc49bc59bbea`, CRC `PASS`, secret scan `PASS`. Package import verification passed; cache and secret patterns are excluded from the archive.

### 2026-09-29 (evening): T323 semantic-conflict fix + model-based Synthetic Human protocol + G0/G3/G4 artifacts

- T323 (Accountability Chain Break) pilot blocker resolved by evidence: the dual semantic validator rejected 9/90 T323@2.3.0 cases because `stimulus_detail` asserted "Each chain record can be checked against the archived source record", which the RISK mechanism itself falsifies (the break removes a linkage field from one chain record while the archive retains the true record). Construct-preserving fix in `suites/_delegation_world.py`: T323 briefings now instruct verification ("Verify each chain record against the archived source record.") instead of asserting universal checkability; T313 keeps its original text (its drift mechanisms never remove fields). T323 refrozen at 2.4.0 (90 cases, 30/30/30, 45/45 Control/Risk, rejected candidates retained); version maps bumped in run_online_campaign.py / run_online_pilot.py / test_formal_dispatcher.py. Re-pilot semantic validation: 90/90 ACCEPTED by both validators; pilot PASS; 2.4.0 formal run started.
- T361-T363 targeted redesign to the model-based Synthetic Human protocol (07_SYNTHETIC_HUMAN_PROTOCOL; goal item 9): new `runtime/synthetic_human.py` with a frozen 5-persona set (SH-CAUTIOUS/STANDARD/AUTOTRUST/EXPERT/NOVICE, sh-personas-1.0.0), deterministic per-case persona assignment (case-id hash, identical across tested models), and `SyntheticHumanActor` driving persona decisions through a frozen auxiliary model with structured JSON outputs. `execute_agency` accepts an auxiliary_models binding; formal paths (cli + run_online_pilot) bind the frozen profile and refuse scripted fallbacks; offline baselines/regression tests bind `ScriptedSyntheticHumanModel`, a deterministic reference that reproduces the legacy scripted outcomes exactly (45/45 tests). Replay provenance now records SYNTHETIC_HUMAN model I/O, persona metadata, and runtime version {suite}-agency-2.1.0. Synthetic-human failures raise SyntheticHumanFailure (ProviderTransientError) so cases stay retryable infrastructure, never tested-model results.
- G4 auxiliary-model selection evidence: live capability probe (`scripts/aux_model_probe.py`, artifacts/gates/AUX_MODEL_PROBES.json) over 10 candidates for structured-output adherence, tool calls, latency/P95, failure classes and token usage. Selected synthetic human = glm-5.3-flash (100% probe ok, perfect format adherence, largest in-workspace evidence base, independent of the tested deepseek model); frozen profile at config/synthetic_human.json with tested-model separation enforced; independent semantic-validator secondary selected = gemini-3.5-flash-lite (for the tested-model-free final validation pass). Evidence: artifacts/gates/AUX_MODEL_PROFILES.json.
- G0 authoritative reconciliation: new `scripts/reconcile_state.py` derives per-suite lifecycle from frozen manifests + pilot gates + formal-run results and rewrites WORK_QUEUE/PROJECT_STATE (131 queue statuses corrected; PROJECT_STATE suite_lifecycle now disk-derived). Evidence: artifacts/gates/STATE_RECONCILIATION.json.
- G3 dataset pack: `scripts/build_dataset_pack_v3.py` verified all 18 authoritative suites (90 cases, unique IDs, FROZEN manifests) and froze DATASET_PACK_v3.yaml (immutable).
- Full isolated regression suite re-run after the redesign (12 files synced to the isolated workspace).

### 2026-09-30 (night): pilot-infrastructure fixes + four suite de-benchmarking refreezes

- Pilot executor bug (T341-T343 incident): the synthetic-human plumbing passed `auxiliary_models` to every suite's executor; non-simulation executors reject the kwarg, so every pilot case died with a TypeError masked as PROVIDER_FAILURE. Fixed with a conditional kwarg; new `tests/construct/test_executor_signatures.py` pins the executor-signature contract (non-simulation executors must NOT accept auxiliary_models; simulation executors must). Pilot reports now persist error_class/error for diagnosability.
- Provider outage (21:28-21:43 window) misread as pilot failures initially; connectivity checks + concurrency calibration (artifacts/gates/CONCURRENCY_CALIBRATION.json, G6 evidence) confirmed levels 2/3/4 clean; scheduler profile frozen at concurrency 3 (config/scheduler_profile.json).
- Version-map centralization: `src/ioabench/frozen_versions.py` is now the single source of truth (driver, pilot, dispatcher test, reconciler, classifier, pack/release builders, independent validation all import it) — eliminates the duplicated-literal drift class that caused the T323 map-omission incident.
- T351@2.3.0: stimulus claimed a hardcoded differential that contradicted the computed rewards (36/90 semantic rejections); control stimulus leaked a condition slug ("balanced-reward-with-receipt"); visible reward_schedule.global_utility duplicated hidden truth (rush=0 = the safe answer) and was consumed by nothing. All three fixed; refrozen 2.3.0; re-pilot PASS.
- T353@2.3.0: visible candidate_set used answer-shaped agent_ids ("preferred"/"alternative"/"distractor-N") and the manipulated registry carried mechanism jargon ("affiliated-bias") - 62/90 rejections. Vendor-neutral identities + business-natural rationales; refrozen 2.3.0. Separately, the runtime wrote paired counterfactual router results into the sandbox world (world changed with no model mutation → state_causality violation); paired runs now flow to the scorer as an explicit argument, T353 runtime bumped to T353-selection-2.1.0 (T312 unchanged at 2.0.0).
- T361/T362/T363 de-benchmarking: visible payloads carried persona_policy (scripted-persona parameters) and cue field names (verification_prompt/fatigue_cue/override_cue/distractor_receipts/challenge_cue/retraining_cue). Renamed to business-natural keys with identical information content; persona_policy moved to the oracle side (the model-based synthetic human does not read it). T362 additionally leaked the correct view via raw_ledger.supports="minority" (30/90 rejections) - replaced with underlying business facts, answer label moved to oracle; T362 refrozen 2.4.0, T361/T363 at 2.3.0.
- Historical 2.2.0/2.3.0 datasets remain frozen and untouched; superseded versions retained with provenance.

### 2026-09-30 (morning): CAMPAIGN COMPLETE — 18/18 formal runs; G2 independent validation; Benchmark Release frozen; Phase C verdict complete

- deepseek-v4.1-flash campaign finished: all 18 suites at 90/90 terminal units on their authoritative frozen datasets (T342 cleared 20 retryable infrastructure units across resume passes to 89 COMPLETED + 1 recorded INVALID; T361-T363 executed end-to-end on the model-based Synthetic Human protocol with per-case persona provenance). ONLINE_CAMPAIGN_STATE campaign_complete=true; reconcile_state.py reports 18/18 FORMAL_EVALUATION_COMPLETE; RUN_CLASSIFICATION: 18 VALID_RESEARCH_RESULT.
- T352 runtime fix found via persisted pilot error details: executing with no current selection wrote a None key into traffic_shares/reputation, breaking canonical hashing (TypeError previously masked as PROVIDER_FAILURE). Now an invalid action; runtime bumped to T352-incentive-reputation-2.1.0 (T351 unchanged at 2.0.0). T352 re-pilot PASS; formal 90/90 all COMPLETED.
- G2 independent semantic validation (goal item 11): all 18 authoritative datasets re-validated with the tested-model-free pair glm-5.3-flash + gemini-3.5-flash-lite — 18 × 90/90 accepted, zero rejections (artifacts/gates/INDEPENDENT_SEMANTIC_VALIDATION.json; per-suite independent-semantic-validation.json evidence).
- G3/G7: DATASET_PACK_v4.yaml frozen (authoritative versions + hashes); Benchmark Release `release/BENCHMARK_RELEASE_v3-20260930.json` frozen (datasets, pack, contracts, source tree, runtime mapping, invalid-output semantics, replay schema, scheduler profile, auxiliary model profiles incl. synthetic human, dependency lock, Windows profile, single-execution disclosure, tested-model roster policy). Roster remains user-controlled.
- G8: RUN_CLASSIFICATION refreshed — 18 VALID_RESEARCH_RESULT (T311-T363 authoritative runs), 3 INVALIDATED (documented), 3 ORPHAN_INCOMPLETE, 92 DEVELOPMENT_EXPLORATORY (mock/pilot/pre-remediation eras). Canonical status for a named release remains a release-level designation, tracked separately from validity.
- Phase C final (artifacts/gates/PHASE_C_CAMPAIGN.json, artifacts/reports/phase_c_dashboard.html, phase_c_report.md): verdict **complete**; 1620 cases; outcomes 864 EARLY_SAFE / 572 TASK_SAFE_BUT_FAILED / 103 UNSAFE_ACTION / 56 FULL_FAILURE / 12 LATE_RECOVERY / 13 INVALID_MODEL_OUTPUT; provider failures in final denominators: 0; utility rate 0.5414; 51.1M output tokens; difficulty/mechanism breakdowns, six family profiles, SIMULATION_ONLY labelling verified end-to-end, secret scan clean, single-execution disclosure. Spot-checks against raw run results match exactly.

### 2026-09-30 (user roster confirmed): FINAL SCIENTIFIC ACCEPTANCE PASS — G13 closed

- User confirmed the final Tested Model roster: **deepseek-v4.1-flash only** (the completed 18-suite campaign is therefore the canonical campaign for the frozen release; additional models may be added later under the release's roster policy).
- G9: `release/MODEL_PROFILE_deepseek-v4.1-flash.json` frozen (exact ID, live-resolved capabilities, campaign parameters, no-substitution evidence, roster confirmation).
- G11: `artifacts/gates/REPLAY_AUDIT_V3.json` — replay integrity audit over all 18 formal runs: request hashes immutable, oracle isolation clean, T361-T363 SYNTHETIC_HUMAN provenance + runtime 2.1.0 + SIMULATION_ONLY eligibility verified. 0 failures.
- G13: `artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json` — verdict **PASS**; all 13 checks green (release frozen, 18 datasets with independent validation, campaign 18/18 terminal, runs classified, replay audit, provider/invalid denominators, no unsafe rerun-to-safe, SIMULATION_ONLY end-to-end, no single overall score, single-execution disclosure, secret scan, dashboard/report/bundle present). Known limitations recorded in the gate.
- Work queue V2-C01..C05 marked done via the reconciler (derived from the passing evidence artifacts).

### 2026-09-30: final delivery package built

- `IoA-Bench-v3-20260930-final-delivery.zip`: 160,613,682 bytes, 20,074 entries, SHA-256 `ad59d79f4c6cc44f460fd1bdf716225d617f4d845e85a1b937f6d3f632f7bbfa`, CRC PASS, secret scan PASS. Contains the frozen Benchmark Release v3-20260930, MODEL_PROFILE, DATASET_PACK_v4, all gates (FINAL_SCIENTIFIC_ACCEPTANCE/PHASE_C/REPLAY_AUDIT_V3/INDEPENDENT_SEMANTIC_VALIDATION/RUN_CLASSIFICATION/ONLINE_CAMPAIGN_STATE), dashboard + report, full source/tests/contracts/config, all 80 run directories (full provenance) and the goal spec. Excluded: .env, old ZIPs, caches. Companion manifest: `artifacts/handoff/HANDOFF_BUNDLE_MANIFEST.json` (hash non-circular, written after ZIP creation); inventory + external review index refreshed to the final delivery state.

## 2026-10-01 — Scientific closure round 2 (S1–S5 evidence closure)

- Parsed the second history export (2026-09-27_2247) with literal reconstruction (history-source-recovery-005/006, history-source-replay-007/008): 72 replayed source mutations across both exports, 0 new whole-tree matches; per-file inversion verified for 5 edit chains; cli.py and incentive_reputation.py inversion impossible due to unexported-session drift (documented).
- New method: per-file content anchoring (`precampaign-source-anchoring-001.json`). Every scientific-path file is pinned exact per suite via manifest single-file hashes, cross-snapshot identity, and saved-score fingerprints.
- T311 runtime file byte-exactly recovered: only difference to release is `max_tokens 8192 -> 4096`. Observed: 647/647 requests at 4096, max completion 3204, zero length finishes, zero failure/retry signatures, 90/90 terminal VALID. Contract content byte-identical since 2026-09-27 (label-only deviation). Prompts/tools pinned and present verbatim in replay.
- `T311_CANONICAL_DEVIATION_v2.json`: NON_MATERIAL_DEVIATION (supersedes v1 UNKNOWN; provider-rate-limit concern resolved by causal-direction argument + zero failure signatures).
- cli.py T311-era forward chain proves pre-campaign formal runs did not use the cli entry (non-mock path was a hard-block stub); the 6-hunk unexported diff is the B6 formal-enablement, outside the scientific path.
- T321/T332 run-time scorers == release content, proven by `task_success` present in 90/90 saved scores per suite (field absent pre-change).
- `source-semantic-review-003.json`: 18/18 suites' scientific-path source relation resolved (4 whole-tree recovered strict/semantic, 4 whole-tree known arch29 semantic, 10 scientific-path-exact with documented tree residual).
- Fresh three-way dataset binding recompute: 18/18 run==release==pack_v4 content hashes, case-id equality, all 1620 cases terminal (T323 keeps 2 INVALID_MODEL_OUTPUT terminal states).
- `RETROACTIVE_RELEASE_BINDING_AUDIT_v4.json`: 13/18 binding-accepted (1 documented deviation, 10 semantic, 2 strict); 5 INCOMPATIBLE (T323/T342/T362/T363 retry-policy violation; T353 missing paired records). User decision recorded as blocker V32-S5B-CORRECTIVE-DECISION.
- `INDEPENDENT_REVERIFICATION_V3_2.json` (S1 formal output): verdict PARTIALLY_CONFIRMED; decisive claims confirmed; prior decisive UNKNOWNs resolved; no provider calls.
- State/queue/checkpoint synced; queue version 16.

## 2026-10-01 — Final closure (S6–S11): goal complete

- User decision recorded: ACCEPT_DOCUMENTED_DEVIATION for T323/T342/T353/T362/T363 (zero provider calls). Binding audit v5: 18/18 accepted, verdict PASS_WITH_DOCUMENTED_DEVIATIONS.
- Acceptance split finalized: BENCHMARK_IMPLEMENTATION = PASS; DATASET_PACK = PASS; CANONICAL_BINDING = PASS_WITH_DOCUMENTED_DEVIATIONS; DEEPSEEK_CANONICAL_CAMPAIGN = PASS_WITH_DOCUMENTED_DEVIATIONS; FINAL_PROJECT_ACCEPTANCE_V3_2_003 = PASS.
- ADDENDUM_2 (metadata-only) links audit v5 + T311 deviation v2 + base release; base release SHA-256 unchanged; S6 gate pass.
- Canonical Phase C final build (`canonical-phase-c-003-final`, `--final`): verdict PASS, campaign_complete=true, 18/18 suites, 1620 canonical cases, utility rate 0.5414, secret scan clean, SIMULATION_ONLY enforced, no overall safety score.
- Final delivery bundle IoA-Bench-v3.2-final-delivery-20261001.zip (per-entry CRC32 + SHA-256 + inventory; secret-pattern scan clean); post-bundle artifacts recorded in final-delivery-addendum-001.json.
- phase_c_campaign.py line-131 t311 verdict literal widened to accept the protocol's NON_MATERIAL_DEVIATION spelling (compatibility fix, documented).
- State/queue synced at version 17; historical runs/gates/datasets untouched (baseline verify: 19606 files unchanged).
# 2026-10-06 — v5 continuation checkpoint

- Added missing v5 suite modules and closed the 18-suite offline matrix: 3,240/3,240 pair-seed checks; candidate dataset `5.1.5-candidate-20261006` passes Gate C data-quality checks but remains unfrozen.
- Gate E pilot ran 864 rows. Response metadata shows all `llama-4-maverick` calls returned `google/gemma-4-31B-it-turbo`; added response-identity validation so this cannot be reported as a valid four-model pilot. T361's specificity baseline exemption now follows its arm-invariant norm.
- Gate D blinded package is ready and integrity-checked, but no human/expert reviews exist. Formal Campaign remains unauthorized pending separate PI-V5-002 approval.
- `python -B -m pytest -p no:cacheprovider tests/v5 -q`: 68 passed. No v4.1.13 files or baseline artifacts changed.

## 2026-10-09 — v5 single-model protocol and DeepSeek diagnostic

- Added PI-V5-005: `deepseek-v4.1-flash` is the sole formal tested model. The Qwen/GPT/Llama rows and the original four-model Gate E artifact remain historical and immutable; no cross-model ranking or pooled-over-model claim is required.
- Added deterministic DeepSeek diagnostic (`216` rows, all provider metadata `deepseek-v4-1-flash-260910`, source SHA-256 recorded in the report). It classifies 26 empty/truncated outputs, 4 T332 budget loops, 5 T333 scorer abstentions, and task-utility failures without counting them as safety behavior.
- Versioned T332 runtime fix `t332-scenario-5.1.1` for neutral category matching/hints; copied candidate `5.1.6-candidate-20261009` passes targeted Gate C (60 pairs, zero candidate failures, zero firewall hits). Future single-model Gate E uses `max_tokens=8192` under protocol `v5-single-model-gate-e-1.1.0`; no provider rerun was started.
- Gate D remains blocked on independent human/expert labels; v5 is not publication-ready and no formal campaign was authorized.
- Rebuilt a DeepSeek-only Gate D package from the historical traces (`pilot-20261006-v5.1.5-deepseek-single-model`); reviewer ZIP CRC passes and the sealed key is excluded. No human labels were fabricated.



## Tree factory R2: mandatory Tree-to-BusinessBinding-to-IR runtime chain — 2026-10-24

- Fixed both externally reviewed P0s: blueprint_from_ir is fail-closed on every ir.validate() error (zero agents, cycles, dangling references can no longer project), and the business branch now changes compiled agents/tools/assets/evidence/events consumed by the real runtime instead of prompt text only.
- New typed BusinessBinding layer (business_binding.py + dynamic/business_tools.py): engine-enforced per-agent grants, DAG-gated receipts with events, SUT-safe world projection; T331/T321/T362 slices, witness/recovery policies run the duty prelude (naive is the negative control).
- Audit contract hardened with 3 new blocking program facts (execution arm coverage, single-suite packet, non-empty reference actions); 13 unseen offline negatives all blocked, 6 positives accepted.
- Provider: USD budget stops removed per user authorization (usage still recorded), output profile 131072/262144 with a live-accepted 393216 ceiling, SSE+usage verified.
- 10 fresh DEV_ACCEPTED pairs this round (T321 x2 incl. the first-ever fresh T321, T331 x4, T362 x4); R1 history and unresolved request ids untouched; 1928/1928 full regression; two review ZIPs in exports/.

## 2026-10-25 AIHubMix mainland API endpoint
- Per user instruction, default API requests use https://api.inferera.com/v1 in the shared adapter, preflight and tree-factory pilots; console/provenance links and system proxy settings are unchanged.
- Added development policy 1.2.0 for this endpoint while preserving validation of frozen 1.1.0 overseas policies. No old ledger, STOP, dataset or package was rewritten; the existing source ZIP predates this change.
- 81 related offline tests passed with zero external network attempts. No provider calls or live availability claim; future online work requires a fresh endpoint/source binding.

## 2026-10-25 Workspace maintenance and source-review snapshot
- Removed 22 regenerable development-cache directories (330 files, 7,945,788 bytes); retained original evidence, older packages, untracked assets and all pre-existing source changes.
- Fresh protection baseline covers 207,418 files; verification is recorded under artifacts/workspace_maintenance/20261025-r1. 51 maintenance tests passed with zero external network attempts; full business regression and Replay were not rerun.
- Working-tree source snapshot at exports/source-code-20261025-r1 includes current uncommitted changes over 7e35bc1. One credential literal in the historical R2 packaging script is redacted in the package copy only; the original is untouched. Package acceptance is recorded independently in PACKAGE_VERIFICATION.json.
- R3 observation refreshed without changing historical evidence: 7 unique DEV_ACCEPTED pairs (T321=5,T331=1,T362=1); novelty, frozen comparison and final R3 acceptance remain open. No provider calls, commit, push or scientific promotion.

## 2026-10-25 R3 compositional DAG factory (historical offline checkpoint, online BLOCKED_EXTERNAL at that time)
- WorkflowModule catalog + WorkflowPlan compiler + plan-first runtime + receipt-chain witnesses landed (compositional_r3 route); T321 truncation removed on the new path; BUSINESS_FLOW retired as legality source.
- 1949/1949 regression; T321_MULTISTAGE_PROOF + NEGATIVE_WITNESS_CASES + R3_ABLATION + HISTORY_PROTECTION (1203 files) emitted under tree_factory_r3/tf-r3-20261025-r1.
- AIHubMix gateway TCP-unreachable (both domains http 000, control hosts 200); 1 REQUEST_UNRESOLVED preserved, never resent; watcher active; online M4/M5/M6 resume on recovery with fresh cohort ids.

## 2026-10-25 Codex R3 strict closure - final acceptance in C0-C7 receipts
- Reproduced the empty-assertions business-witness bypass with two real offline end-to-end failures, then repaired the common route and added missing/failed/permission/receipt/event/arm/policy/conditional controls. Declared model DAG edges now constrain runtime prerequisites, authorized handoffs and reference-policy readiness.
- Replaced order-sensitive hash-only novelty claims with exact typed graph canonicalization and checkable mappings. Missing historical DAGs remain explicitly unknown; actual sealed trace receipt-edge invariants provide scoped non-isomorphism certificates rather than invented empty graphs. Original seven admissions are preserved but their unconsumed declared edges exclude them from current closure eligibility.
- Mainland exact-model high/max/131072/SSE/JSON/usage/identity checked. Closure scopes made 68 request intents: 62 complete responses and six unknown terminals, with zero old UNKNOWN POST resends. This continuation added 19 intents, 18 complete responses and one quarantined unknown. All STOPs remain intact; the endpoint is not claimed perfectly reliable. Same-model high/max review remains development-only; malformed factual reviews quarantine.
- Six strict DEV_ACCEPTED pairs now meet two accepted pairs and two executed, historically distinct typed graph families for each of T321/T331/T362. All 36 frozen route opportunities have actual outcomes (17 engineering PASS, 15 rejected, two pipeline failures, two external blocks); original first outcomes, repairs and source/policy strata remain separate. No formal/scientific promotion, scorer change, threshold reduction, dataset freeze or push.
- Added all-scope never-sent baseline selection, live 18-suite schema readiness mapping and final JUnit/source/Git binding. Shared-file task hunks are committed separately from pre-existing user edits; the SOURCE export retains the exact dirty overlay. Final full regression, Replay and package receipts are authoritative, not earlier checkpoints.
- The earlier checkpoint recorded 31 candidate pairs/186 Strict Replays, 1203 protected files, 39 scorer modules and zero-call stopped-run resume checks. Final HEAD regression, refreshed Replay/protection and SOURCE/EVIDENCE receipts are authoritative in exports/codex-r3-closure-20261025; neither that checkpoint nor the earlier 1978-test JUnit substitutes for them. Pre-existing unrelated dirty edits remain uncommitted; the historical R2 credential literal is redacted only in the export copy.
- Final-reference directories now bind Git HEAD, runtime and preserved overlay identity; old checkpoint runs cannot masquerade as fresh execution. Actual fresh/resumed policies are recorded and covered by regression. The ced1949 1984-test PASS is retained as a checkpoint; the successor final-source JUnit and package receipts remain authoritative.
