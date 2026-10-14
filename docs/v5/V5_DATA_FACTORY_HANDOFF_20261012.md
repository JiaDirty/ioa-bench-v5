# ADR-V5-002 — 可复用数据生成产线

日期：2026-10-12。授权：PI-V5-011，继续唯一 v5 长期任务。

## 流程与已有代码

统一入口 `scripts/v5/data_factory.py` 复用已完成的动态测评系统。每个候选依次经过：

1. 固定程序事实、机制、工具与生成契约。
2. 生成模型提交封闭格式的提案。
3. 校验、编译成 CONTROL/RISK 配对，检查机制外差异、泄漏和参考策略。
4. 用原运行器执行完整参考策略矩阵，保存动作、事件、判分和监测证据。
5. 对固定参考池做精确、文本和实际执行结构比较；重复候选在独审调用前拒收。
6. 另一模型家族审核最终可执行案例，引用必须能定位到真实字段。五项分数仍须全部至少4且无问题才能机器接受。
7. 保存原答复、拒收原因、输入/源版本/证据哈希、检查点和晨报。机器接受不等于冻结或科研接受。

共用代码在 `src/ioabench/v5/ai_generation/{pipeline,factory,quality}.py`。模型调用经过 ModelPort；每次新试跑先保存实时目录和精确模型官方参数。API 密钥仅从环境或本地秘密文件读取，证据中不保存密钥。

## 实际支持范围

`runtime_adapter.py` 覆盖18项、19个已注册动态结构的受控文本补充，原内容保留，新增内容实际进入代理输入。它保留程序事实、Oracle、评分、机制与原难度。文本变化不计新结构。

另有三项封闭结构参数编译器：

| 测评 | 实际支持的变量 |
|---|---|
| 注册失真 T312 | 操作、初始/修订区域、数据格式、组织；程序重建能力证据与修订后适配事实 |
| 跨系统级联扩散 T331 | 2或3个下游节点、受控字段、组织；实际改变扇出网络 |
| 声誉垄断 T352 | 2或3个分配代理、声誉数值、3条实际送达的报告说明、组织；广播报告或本地回执＋显式历史查询 |

旧 T321 蓝图入口保留并升版到1.4.0，拒绝重复/循环/未解析节点和证据，保留业务目标；其 task_graph 只是能力路径说明，不会强制代理走指定路径。新共用入口不把这份旧蓝图格式当作18项的上限。

新工具、任意拓扑和新的执行规则须新增适配与验证，不能塞进说明文字后宣称已运行。三项模拟人类结构当前程序模板只有 E 标签；没有擅自改标为 M/H。难度校准和全面历史家族比较尚未完成。模板文本适配不证明18项具有足量、高度多样的科研数据。

T352 的 `local_receipt_query` 让每个代理收到自己选择的服务商回执，其他服务商的已完成轮次报告通过现有 `read_history` 明确查询。查询未来轮次或未知服务商被拒绝；当前轮次仍可直接采样，代理保留选择权。四轮结果、声誉公告、标准答案、评分规则及效用阈值保持不变。默认广播模式兼容旧案例。真实审核曾因仅增加代理人数而给结构多样性3分并拒收，原结果 `factory-live-20261012-r4` 保留，新模式必须重新验证。

## 使用与恢复

离线预检：

```powershell
python -B scripts/v5/data_factory.py --run-id <新的运行名> --suite all --mode offline
python -B scripts/v5/data_factory.py --run-id <另一运行名> --suite T312 T331 T352 --typed --mode offline
```

小批真实试跑（每次1–6个候选，本阶段不批量生产）：

```powershell
python -B scripts/v5/data_factory.py --run-id <新的运行名> --suite T331 T352 --typed --mode live --trials 2
```

同参数、同版本、同运行名重跑即恢复。保存了响应就原样重放；已完成候选复核证据哈希后不再调用模型。若请求已经发出但没有可确认的落盘响应，会明确记录 REQUEST_UNRESOLVED，避免重复付费或覆盖意见。源代码、参数、模型或输入改变须新建版本化运行，不能把旧答复嫁接到新输入。

审核渠道明确报错且没有任何落盘审核答复时，先核对本地官方模型文档，再用新的运行编号和实时目录中另一合格审核模型恢复。`--recover-generation-from <旧运行名>/candidate-01` 只允许单个候选：旧结果必须是审核阶段的 Provider 故障，原始生成请求的模型、参数和完整输入哈希必须一致。旧证据只读复制，重新编译、重跑全部硬门和参考执行，新审核身份单独登记；不重复生成收费。已有 FAIL、ABSTAIN、无效格式、截断或身份错误答复均不能借此换审核者刷通过。未知中断且没有故障记录也不能自动重发。

```powershell
python -B scripts/v5/data_factory.py --run-id <新的恢复名> --suite T352 --typed --mode live --trials 1 --auditor glm-5.3 --recover-generation-from <旧运行名>/candidate-01
```

辅助渠道故障诊断保留 curl 退出码、HTTP 状态和允许的请求ID/模型/重试头，不打印密钥、完整命令、响应正文或 stderr。渠道选取仍须核验当时实时目录与精确官方 schema；这不是永久固定的备用模型名单。

当前便捷默认是 Claude Sonnet 5.5 生成、GPT-6 Astra 独审，仍每轮实时核验模型ID、厂商和官方参数。GLM Flash/GLM 的原故障分别保存在 r2/r3；r3 证据为 curl56、HTTP000、空响应，说明调用链连接中断，不能据此断言服务端HTTP错误或参数错误。Astra 已返回有效审核意见，拒收意见没有被改写为通过。

独立审核负控制（一个额外付费审核请求，不生成正式数据）：

```powershell
python -B scripts/v5/verify_data_factory_quality.py --run-id <新的对照名> --candidate <已机器接受的T331或T352候选目录> --auditor gpt-6-astra
```

对照只修改公开审核副本：T331 写入与节点表矛盾的数量，T352 写入与交付状态矛盾的成功说明。审核必须给有效 FAIL、语义分不高于2，并准确引用和解释植入矛盾，才能通过对照；原案例、Oracle、评分器和全部历史证据保持原字节。通过一个对照不证明全部语义错误都能检测。

各 run 保存固定参考池；后续其他 run 的变化不会修改该池。新结构计数只相对于绑定的动态参考，不冒充全项目历史比较完成。现有 OS 写入锁防止第二产线同时写入；子任务只编辑明确分配的文件。

## 科学接受边界

本产线没有修改18项构念、被测 DeepSeek、Ground Truth 或评分门槛，没有覆盖历史失败/拒收，也没有自动冻结数据、运行确认 Pilot/Campaign 或替代真人审阅。T361–T363 保持 SIMULATION_ONLY。

正式生产前仍需覆盖更广的可执行结构、补齐难度与实质多样性证据、比较完整历史基线。真人环节沿用已有盲审工具；不要求真人替我们修程序或准备样本。

当前执行是有界命令与文件检查点；未验证应用关闭或断电后的调度，不能据此声称无人值守持续运行。

## 当前验收与下一次试跑

最终共用产线2.3.1，`tests/v5 + tests/m1` **784 passed /66.14s**。当前源码18项预检36/36、228次参考检查；三项结构编译预检6/6、36次参考检查，包括两种T352报告方式。归档旧r4源码隔离重跑真实CLI，原拒收结论保留、零Provider构造/调用、历史33文件字节不变。最终源码哈希`8dbff6f4081d0c6e9cc62cb0f8a3a05d932b5c65465bba498bc04f89ab51ca8a`；452文件源码ZIP逐文件SHA-256与CRC通过，实际本地密钥匹配0。汇总证据：`artifacts/v5/data_factory/trials/factory-acceptance-20261012-r1/STATUS.json`，同目录有`TRIAL_ACCOUNTING.json`和06模板`MORNING_REPORT.md`。

六次小试和一次负控共11次新推理请求、7份唯一响应、38383 tokens；恢复复制的生成响应不重复计费统计，未返回请求的实际用量/费用未知。7个候选执行为1机器接受、3拒收、3Provider失败；不是7个独立生成提案。旧T331贯通机器接受闭环；真实Astra拒绝T352数量变化的结构多样性。新报告查询模式本地验证通过，但新在线正例和审核负控均未完成。**这是受支持范围的工程验收，尚非生产质量验收。**

最新Claude新提案返回`refusal`，留存拒绝而非伪造JSON。Gemini新生成和GPT负控请求均HTTP401；按本地官方Bearer示例核验读取凭据后，两个官方域名的只读`/dashboard/billing/remain`也都401。证据`artifacts/v5/provider_contracts/20261012-auth-r1/AUTH_DIAGNOSIS.json`。当前配置的凭据被拒绝，不能据此断言余额不足或一定过期；没有另一已配置凭据可自主切换。恢复本地环境/秘密配置中的有效鉴权后再继续，不要把密钥写进报告或聊天。

负控可先离线准备（已完成的r2不再重复准备），再以同运行名、同源码审核原包：

```powershell
python -B scripts/v5/verify_data_factory_quality.py --run-id factory-quality-control-20261012-r2 --candidate artifacts/v5/data_factory/trials/factory-live-20261012-r1/candidate-01 --auditor gpt-6-astra --prepare-only
# 鉴权恢复后，去掉 --prepare-only；只发一次独审，不重新生成原案例。
python -B scripts/v5/verify_data_factory_quality.py --run-id factory-quality-control-20261012-r2 --candidate artifacts/v5/data_factory/trials/factory-live-20261012-r1/candidate-01 --auditor gpt-6-astra
python -B scripts/v5/data_factory.py --run-id factory-live-20261012-r7 --suite T352 --typed --mode live --trials 1 --seed 61017 --generator claude-sonnet-5-5 --auditor gpt-6-astra
```

准备完成只是`PREPARED_NOT_AUDITED`、passed=false、API0。实际审核必须通过既有矛盾检测要求；若失败则保留判定，修订流程后用新的版本化试验，不重审同一候选刷通过。以上模型仍以启动时实时目录/官方schema为准，不能自动改掉已绑定包的审核身份。源码变化需重新准备新run。所有正式模型、GT、评分及历史冻结数据继续受保护。

## 本地候选接入复核（2026-10-13，PI-V5-012）

新增 `scripts/v5/prepare_candidate_intake.py`，把已有 `CANDIDATE_EXPERIMENTAL` 运行目录重新检查后转换为统一 Case JSONL。它会拒绝错误的 CONTROL/RISK 配对、未声明差异、重复身份、未知动态结构和失败的动态配对 Gate，并保存源运行文件哈希、案例哈希、难度/子类型统计和重验结果。

本地复核使用旧 T321-DYNA 实验运行 `m8-fill-20261011-t321-v2`：2 对、4 条案例成功进入 `ENGINEERING_INTAKE_READY`，随后通过统一 `evaluate.py` 的 witness/naive 参考测评和 Gate D 盲审包生成。证据目录：

- `artifacts/v5/data_factory/intake/20261013-t321-v2/`
- `artifacts/v5/evaluations/intake-20261013-t321-v2-witness/`
- `artifacts/v5/evaluations/intake-20261013-t321-v2-naive/`
- `artifacts/v5/data_factory/review/20261013-t321-v2/`

当前源码回归绑定在 `artifacts/v5/data_factory/intake/20261013-t321-v2/INTAKE_VERIFICATION_20261013_R2.json`；旧的 794 测试验证文件保留为历史证据，不再作为当前状态引用。

这一步完成了“候选文件进入测评系统并准备盲审”的本地工程接线；它没有把候选变成正式数据，也没有改变历史数据。接入后的完整 `tests/v5 + tests/m1` 回归为 **796 passed / 0 failures / 0 errors / 0 skipped**。当前仍缺真实生成/独审在线质量、全量结构与难度扩展、Gate C/D、冻结和正式测评。

## 历史基线去重预检（2026-10-13）

产线版本升为 `ioabench.v5.reusable-data-factory/2.3.2`。离线预检现在会把每个构念的动态候选与对应经典 5.1.5（T332 同时保留 5.1.6）运行时放进同一参考池，逐文件记录 19 个 `cases.jsonl` 的 SHA-256，并在比较时使用各自真实 scenario 的 agent/tool/state 结构；因此换名或只改文字不会被报告成新结构。

当前源码绑定的 `artifacts/v5/data_factory/trials/local-historical-compare-20261013-r3/PREFLIGHT.json` 通过 18 Suite、36 个编译检查和 228 个参考检查，Provider 调用 0。质量状态为 `TEXT_DUPLICATE=23`、`INSTANCE=11`、`NEW_STRUCTURE=2`。这只是历史接线与去重工程证据，难度仍是 `DESIGN_PROXY_ONLY_NOT_EMPIRICALLY_CALIBRATED`，不替代在线独立审核、批量合格数据、Gate D 或正式冻结。

当前 r9 工程样本的 Gate C/D 准备清单为 `artifacts/v5/gates/gate-c-d-readiness-20261013-r3.json`，盲审包为 `artifacts/v5/review_package/system-20261013-engineering-r3/`。它只确认材料、哈希、CRC、样本缺口和裁决工具可用；真实专家标签和 Gate D 判断仍未发生。

另有 `artifacts/v5/manual_18/20261013-one-pair-per-suite-r3/MANUAL_18_VERIFICATION.json`：18 个经典套件各一对 CONTROL/RISK，共 36 条；witness/naive 两种参考策略均完成 36/36，恢复不重执行，回放 36/36。T332 评分器的跨进程证据顺序问题已修复并有 hash-seed 回归测试；该包仍属于工程参考验证，不是正式科研数据。
