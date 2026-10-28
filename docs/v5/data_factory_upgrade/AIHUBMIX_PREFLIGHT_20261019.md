# AIHubMix 八候选预检与角色证据：2026-10-19

八个偏好候选中，七个精确 ID 已通过真实 Chat JSON 与服务身份探针，Qwen 候选未得到唯一 ID。MiMo Pro、Gemini、GLM 已完成真实工具往返；两次故意发送错误参数均触发 HTTP 400 分类，随后由已验证备用模型成功响应。基础连通、工具协议、生成质量、独立审核资格、开发难度测量是不同门槛。

当前runtime为 `4f7fc7c842ea63a352157baffe8252838fdc06332e2839fd3ddb6f250e04e9e5`。[最终真实ID/参数/角色矩阵](../../../artifacts/v5/data_factory/upgrade-20261019/PROVIDER_ROLE_MATRIX_R13.md)、面板与用量均绑定R13终态报告；旧 `PROVIDER_ROLE_MATRIX_R11.json` 保留原快照，不覆盖。基础探针、工具循环和固定独审各自保留真实producer SHA，pool依赖桥接不会重标旧调用或授予当前source机器资格。

## 精确 ID、参数与身份

全部成功基础探针使用 `https://api.inferera.com/v1/chat/completions`，协议为 OpenAI 兼容 Chat Completions。JSON 表示 `response_format={"type":"json_object"}`，思考表示 `thinking={"type":"enabled"}`。

| 用户候选 | 精确请求 ID | 基础探针实发参数 | 基础 JSON / 身份 |
|---|---|---|---|
| MiMo-V2.6-Pro | `mimo-v2.6-pro` | `max_completion_tokens=8192`，思考，JSON | PASS |
| GPT-6.1 Sol (Medium) | `gpt-6.1-sol` | `max_completion_tokens=8192`，`reasoning_effort=medium`，JSON | PASS |
| GLM-5.3-Flash | `glm-5.3-flash` | `max_tokens=8192`，思考，`reasoning_effort=high` | PASS |
| MiMo-V2.6-Flash | `mimo-v2.6-flash` | `max_completion_tokens=8192`，思考，JSON | PASS |
| GPT-6 Luna (Max) | `gpt-6-luna` | `max_completion_tokens=8192`，`reasoning_effort=max`，JSON | PASS |
| DeepSeek V4.1 Flash (Max) | `deepseek-v4.1-flash` | `max_tokens=8192`，`reasoning_effort=max`，JSON | PASS |
| Qwen3.8-Flash-Next | 未解析 | NOT_RUN | `UNRESOLVED_MODEL_ID` |
| Gemini 3.8 Flash (High) | `gemini-3.8-flash` | `max_completion_tokens=8192`，`reasoning_effort=high`，JSON | PASS |

括号中的 Medium/High/Max 只有在该精确模型的 schema 枚举支持时才转换为参数。`model_routing.py` 负责解析，未将展示名直接用作 API ID；Qwen 没有用近似型号代替。

身份检查优先将响应头 `x-aihubmix-model` 与实时目录精确匹配。Sol 正文版本为 `gpt-6.1-sol-2026-09-29`，DeepSeek 为 `deepseek-v4-1-flash-260910`；其余五个成功模型正文与请求 ID 一致。原始响应、头部、请求参数、账本均保留。目录中的 `active` 仅描述该次查询，不保证以后一直有渠道。

`factory-20261019-r2/LOCAL_DOC_SOURCES.json` 绑定 `D:\Project\Playground\scrape\aihubmix` 中 1510 个 UTF-8 文档和示例的字节、时间与 SHA-256；`MODEL_CATALOG.json` 和七份 `schemas/` 保存实时依据。本地 Luna 模型页声明仅 `/v1/systemone`，精确参数 schema 声明 Chat 支持；实际 Chat + max + JSON 成功，文档冲突保留。原生 Responses、Anthropic Messages、SystemOne 调用均为 **NOT_RUN**。

## 实际角色矩阵

| 精确模型 | 真实工具往返 | 生成角色 | 独立审核角色 | 开发难度测量 |
|---|---|---|---|---|
| `mimo-v2.6-pro` | PASS，r1/r2 各 1 次工具调用 | 当前NOT_RUN；旧源码 staged G2 的4次调用后被全历史去重拒收 | NOT_RUN | 原R3加R13共47个COMPLETED/1中断；标签UNCALIBRATED |
| `gpt-6.1-sol` | NOT_RUN | NOT_RUN | r15/r16各16/18，不合格 | NOT_RUN |
| `glm-5.3-flash` | PASS，r2 1 次工具调用 | NOT_RUN | r19/r20各8/18、不合格，各误接纳4负控 | 原R3加R13共45个COMPLETED/2个BUDGET_EXCEEDED/1中断；标签UNCALIBRATED |
| `mimo-v2.6-flash` | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| `gpt-6-luna` | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| `deepseek-v4.1-flash` | NOT_RUN | 排除正式被测家族 | 排除正式被测家族 | 排除正式被测家族 |
| 未解析 Qwen 候选 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| `gemini-3.8-flash` | PASS，r1 1 次工具调用 | NOT_RUN | r17/r18各12有效判断，第13截断，余各5控NOT_RUN；不合格 | 当前NOT_RUN；旧面板网络失败已停止 |

工具探针实际经过“模型请求工具 → 本地工具返回 42 → 模型接收结果并返回 JSON”。MiMo 的历史 `reasoning_content`、Gemini 思考签名字段由现有适配器回带。工具请求移除了基础探针的 `response_format`；MiMo 使用 8192 + 思考，Gemini 使用 8192 + high，GLM 使用 `max_tokens=8192` + 思考 + high。证据是 `tool-loop-20261019-r1/TOOL_PREFLIGHT.json` 与 r2 同名文件、各 `tool-start` / `tool-finish` 请求响应。两份报告的当时源码 hash 为 `4b0db08c73bf1abca9d71f2941e4013e44263f48984c3a1e3c73352cbe9d01a7`，没有改写成 R11 hash。

Sol金标准实发 `max_completion_tokens=16384`、`reasoning_effort=medium`、JSON，角色 `INDEPENDENT_AUDITOR`。控制1.5.1有18个固定输入，两次分别全部通过才合格。两draw均16/18；verdict一致17/18、κ0.8889。Sol三处有效事实引用/理由不合窄预声明锚点，另有r16“声誉垄断”正例真实 `ABSTAIN`（realism3/5）；这些不属于Provider故障，也不能一律称为捏造引用。旧r13的14/18合同正确、18/18 verdict正确保留旧失败，没有重判升级。

Gemini/GLM有限双draw比较已结束，原预声明见 `AUDITOR_QUALIFICATION_COMPARISON_R17_PLAN.md`。GLM两次各8/18，各误接纳4负控，重复一致14/18、κ0.6522；Gemini两次各12个有效判断，第13响应 `finish_reason=length`，余各5控 `NOT_RUN`。六draw共98响应、96有效判断、2截断、10个control draw未执行；没有合格审核者。全部结果见 `FINAL_AUDITOR_QUALIFICATION_R12.json/.md`，不继续轮换刷PASS，也未给生产拒收候选换裁判。gold真实性/锚点依据若需改变，须先独立科学裁决。

MiMo/GLM开发面板使用 `CALIBRATOR` 角色和8192工具配置，保留Safety与Utility、核验、预算、弃权及真实恢复结果。旧R3为32个COMPLETED、2个BUDGET_EXCEEDED、2中断，34条终态严格Replay通过；中断请求未重发。R13其余15项M按原计划完成30组/60回合，60严格Replay与30同参零调用恢复均PASS，原SHA/mtime未变，见 `REMAINING_PANEL_REPLAY_RESUME_R13.json`。合计92个COMPLETED、2个BUDGET_EXCEEDED、2中断，分源保留。完整Safety/Utility/核验/弃权/预算分母见 `FIXED_PANEL_BEHAVIOR_SUMMARY_R13.json/.md`。输入尚未机器合格且与开发/控制来源重叠，标签保持 `MEASURED_EXPLORATORY_UNCALIBRATED_LABEL`，不能证明隐藏泛化或科学E/M/H。

## 分类、有限恢复与故障切换证据

当前 `AuxiliaryRouter` 1.1.0 复用 `ModelPort → AIHubMixAdapter`，参数仍来自 `model_routing.py`。真实请求 ID、参数、服务身份、响应、费用估计和哈希链落盘，相同终态输入可零调用恢复。正式 SUT 不能进入此路由；独审 developer 必须与全部生成者不同，并重新核验当前源码、控制输入及结果字节。

| 情形 | 当前处理 | 已有执行证据 |
|---|---|---|
| `no_available_channel` / 无渠道 | 立即熔断，下一已预检且角色合格候选 | 受控假 Provider 正负回归 PASS；本次八候选未声明真实发生此事故 |
| 明确 429 / 5xx | 运行合同最多 2 次；短 `Retry-After` 等待，超过 60 秒转备用 | 离线回归 PASS；真实 429/5xx 切换 NOT_RUN |
| 参数错误 | `REQUEST_SCHEMA` 分类，保留并转备用 | 真实故意 HTTP 400 → Gemini 成功（r1）；HTTP 400 → GLM 成功（r2） |
| 已发送但无响应的超时/断连 | `REQUEST_UNRESOLVED`；同任务不重发、不换模型续发；新独立任务可用健康备用 | 旧 Gemini 两个 episode 各 curl 28、HTTP 000、180 秒超时，固定面板停止 |
| 401 / 403 或缺凭据 | 停止本运行凭据，不循环候选 | 离线负例 PASS；本次真实认证错误 NOT_RUN |
| 空响应、结构/身份异常 | 分类保留，有限熔断切换 | 离线正负回归 PASS；真实身份异常切换 NOT_RUN |
| 质量、独审 FAIL/ABSTAIN、科学 Gate 拒收 | 保留拒收，不换审核者刷 PASS | 当前控制与旧 staged G2 去重拒收保留 |

两次真实切换均刻意向 `mimo-v2.6-pro` 发送 `max_completion_tokens="deliberately-invalid-negative-control"`；收到 HTTP 400 后只切一次，Gemini high / GLM high 备用请求成功。它不是 MiMo 自然宕机，也不是生成或语义审核质量验证。精确字段、原因、attempt SHA-256 见矩阵 `failure_evidence`。

旧 Gemini 面板的网络失败保存在 `PANEL_FAILURE_DIAGNOSIS.json`，原 episode 和账本保留，没有重复未知请求。之后另建 R3 固定面板使用已验证健康的 MiMo/GLM，未在冻结面板静默替换。未知响应的 Token、服务身份和费用均为 **UNKNOWN**。最初主域名目录 GET 也发生 curl 28 / HTTP 000；r2 用本地文档列出的等价备用域名成功。该 GET 原异常只在命令轨迹，没有补造 r1 失败 JSON；未修改系统代理。

## 执行与计量

```powershell
python -B scripts/v5/aihubmix_preflight.py --out artifacts/v5/provider_contracts/factory-20261019-r2 --live --timeout 180 --base-url https://api.inferera.com/v1
python -B -m pytest tests/v5/test_auxiliary_runtime.py tests/v5/test_ai_generation_model_routing.py -q --junitxml=artifacts/v5/provider_contracts/factory-20261019-r3/OFFLINE_TESTS.xml
```

首条实际退出0，七次基础completion全通过。r2离线42项、r3补入口负例后45项通过，含有限重试、熔断切换、空响应、身份异常、未知请求防重发、认证停止、角色隔离、拒收不重试、重放和篡改检查。当前完整1486项回归见 `upgrade-20261019/INTEGRATED_REGRESSION_R13.xml`；旧45项不替代当前完整验收。

基础预检恢复使用必报错 Provider 构造哨兵，实际构造 0、调用 0，56 个既有文件 hash 未变；`VERIFICATION_ADDENDUM.json` 与 `SHA256SUMS.json` 保留结果。本页/矩阵整理新增 Provider 调用 0。

七次基础请求报告790 Token，目录估价USD0.00136754312；加两份工具/切换探针共19次、17成功、2个故意参数失败，2756已知Token，估USD0.00334858988。上述仅协议小计。全部付费结束后实际原脚本总账为[完整TOTAL_USAGE_R13](../../../artifacts/v5/data_factory/upgrade-20261019/TOTAL_USAGE_R13.json)：2061 started、2058 finished、2054成功、2失败、5未决；已知9,543,841 Token，7次缺usage、7次服务身份未知，目录估USD已知小计5.394535590692、33次计费未知。角色/模型加和均已独立核对。估价不是账单，未知不计零；旧R4不是最终总账。

当前未获得最终独审资格，R13完整生产接受链与机器合格池受该门槛阻断，均未获正资格。确认性Pilot、正式Campaign、正式冻结、真人实验均 `NOT_RUN`；正式DeepSeek配置未替换，T361–T363保持 `SIMULATION_ONLY`。
