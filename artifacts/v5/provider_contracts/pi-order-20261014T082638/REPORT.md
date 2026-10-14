# 七模型选型与 GPT 首选小批生成试验 — 2026-10-14

本轮按用户指定顺序核对模型并首先试用 GPT-5.6 Sol。连接与完整生成链均已跑通，但六个候选的结果说明：不能宣布18项批量产线的质量与长期稳定性已达标。修复后的跨系统级联扩散和声誉垄断各有一个机器合格候选；注册失真因独审认为结构不足而拒收。所有结果为实验候选，不是正式科研数据。

## 选型与官方调用

| 优先级 | 精确 AIHubMix ID | 官方参数/本地官网说明 | 本次成功调用证据 | 生成角色范围 |
|---|---|---|---|---|
| 1 | gpt-5.6-sol | 完整schema及说明 | r1/r2/r3共6次生成 | 本轮首选 |
| 2 | deepseek-v4.1-flash | 完整schema及说明 | 当天 mainstream-20261014T080611 探针 | 仅列探索候选，未生成 |
| 3 | kimi-k3 | 完整schema及说明 | connection_results/kimi-k3.json，5.593秒 | 未实际比较生成质量 |
| 4 | deepseek-v4-pro | 完整schema及说明 | connection_results/deepseek-v4-pro.json，3.375秒 | 仅列探索候选，未生成 |
| 5 | glm-5.3-flash | 完整schema及说明 | r1/r2共5次独审 | 本轮独审 |
| 6 | gemini-3.8-flash | 完整schema及说明 | r3独审；当天基础探针 | 本轮新候选独审 |
| 7 | grok-4.6 | 完整schema及说明 | connection_results/grok-4.6.json，4.531秒 | 未实际比较生成质量 |

完整实时目录、官方URL、原始schema、参数、文档SHA-256见 SELECTED_MODELS.json、official_schemas/、local_docs/。GPT/Kimi/Gemini/Grok生成参数使用官方 max_completion_tokens；DeepSeek/GLM使用 max_tokens。上限65536及high思考档位由现有helper依据各自schema生成。GLM schema不支持JSON模式，本轮没有发送response_format，而是依提示及严格解析验证输出。请求使用现有ModelPort/AIHubMixAdapter，独审timeout有界900秒。deepseek-v4-pro与官方提到的新0813条目未混作同一型号，未自动替换精确ID。

独立API上下文不共享聊天记忆，但同模型/同家族生成可能引入题目分布偏向；用户对此的疑问未登记为解除正式科研隔离的批准。现有factory继续禁止被测DeepSeek家族充当正式生成/审核。GPT首选可用，因此没有为了轮遍名单切换生成模型。这里只登记优先顺序，没有新增七模型自动回退程序；原有故障政策与角色合格校验继续适用。

## 六个原始候选

| 运行/版本 | 测评 | 生成/独审 | 原始结果 | 实际解释 |
|---|---|---|---|---|
| r1 / 2.3.2 | 注册失真 | GPT / GLM | REJECTED | 审核ABSTAIN，结构新颖性3分；沿用已有结构 |
| r1 / 2.3.2 | 跨系统级联扩散 | GPT / GLM | MACHINE_ACCEPTED | 请求M但生成H，旧版未拦截；保留原结果，不能作为无缺陷产线接受证据；非新结构 |
| r1 / 2.3.2 | 声誉垄断 | GPT / GLM | REJECTED | 审核有不存在的引用，结构维度缺编译world引用；另有M→H标签漂移 |
| r2 / 2.3.3 | 跨系统级联扩散 | GPT / GLM | MACHINE_ACCEPTED | M标签正确；仍是已有结构的实例 |
| r2 / 2.3.3 | 声誉垄断 | GPT / GLM | REJECTED | M正确；审核结构维度仅引用metadata/runtime_context，严格验证拒收 |
| r3 / 2.3.4 | 声誉垄断 | GPT / Gemini | MACHINE_ACCEPTED | M正确、程序编译/保真/硬门/参考执行通过，审核各维度5分，编译world引用有效 |

r3是新种子、新提案、新run，不是把旧被拒样本换审核者重打分。没有改写审核原答复或降低阈值。它相对本轮固定参考池有结构差异（3个分配Agent及本地回执查询）；同类参数已在先前被拒候选中尝试，因此不宣称全球首次结构，也不计全历史科研合格新家族。全局新合格家族仍0，formal_accepted=false。

## 流程修复与验证

factory 2.3.3把请求的设计难度绑定到提示schema，并在生成后拒绝标签漂移；没有重标旧数据。2.3.4以本次种子重新构造typed示例预览；T312原先seed=0预览的listings/receipts/manifests与实际种子不同，T331/T352在本次M难度下没有该差异。新增回归先复现缺陷，再验证修复；未改变编译语义、GT、评分、正式模型参数或冻结数据。难度标签依然只是设计标签，不能代替模型表现的实测校准。

- 当前32项factory测试、完整816项v5测试通过；XML为 PYTEST_FINAL_FOCUSED.xml、PYTEST_FINAL_V5.xml。
- 各run预检均通过：r1六项/36参考检查，r2四项/24参考检查，r3两项/12参考检查。实际候选各自保留参考执行轨迹。
- 原始源码树：r1 f9cd9db539d25c5c553ff03190e055b69aea9386af6bdf6b34cedaa6793968e9；r2 68600fc5004cca60ccb439adbd1bd3c82ac731280c99b2f97dd392e6df863a2b；当前r3 14ecaf00a1659b672efe12875ead7c9a107534e66b35d7c20c4fda3959f92e9b。
- 每个run保留457文件源码ZIP及逐文件hash/CRC。RUN_CONTRACT中的source_sha256为源码树与CLI命令源码的组合hash，与上述源码树hash不是同一字段。
- verify_trials.py使用每个run归档的匹配源码，禁止构造Provider后执行terminal resume：三次均成功，没有新API请求，所有候选JSON/日志hash未变，历史参考数据hash匹配。
- 七份官方schema及本地说明匹配；实际响应身份由X-Aihubmix-Model核对，请求/响应hash绑定。原始body的供应商版本型号另行保留，未覆盖。
- 本轮6生成+6独审+3新增连接探针=15次完成请求，全部正常stop，没有401或观察到的渠道错误。231008 prompt +22460 completion =253572 reported tokens；目录/schema查询另存，实际金额未由API返回。
- 证据与源码的本机凭据字符串出现次数0；凭据来自既有本机环境，未写入报告或源码归档。写入时使用现有OS lock；ZCode写入进程未观察到。

## 后续接受边界

GPT现已证明能按受控契约生成可执行候选，可继续作首选；Gemini独审本轮一例遵守证据契约，GLM有两例引用失败，不能据此推成长期模型质量排名。API可用不等于生成/审核合格。

下一优先工作是有界验证独审的正负控制、扩展真实任务/证据/交互结构，再逐项验证18套件；随后做全量历史去重、重复可靠性与实测难度校准。未开始批量生产、正式DeepSeek测评、确认Pilot、Campaign或freeze；人工Gate D仍仅是正式接受的最后外部环节。本轮报告和每个run的06模板晨报保留这些边界，不声称完美或长期无故障。

## 重现命令

```powershell
python -B -m pytest tests/v5/test_reusable_data_factory.py -q -p no:cacheprovider
python -B -m pytest tests/v5 -q -p no:cacheprovider
python -B artifacts/v5/provider_contracts/pi-order-20261014T082638/verify_trials.py
```

verify_trials.py是离线证据检查，不再发模型请求；仅在确认现有writer lock没有其他项目写入者时运行。原run的实时命令、参数和版本由各RUN_CONTRACT/REQUEST保存；改源码后需新run，不能直接复用原live运行合同。
