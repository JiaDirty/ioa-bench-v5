# AIHubMix 辅助模型调用校核 — 2026-10-12

本次按用户提供的 `D:/Project/Playground/scrape/aihubmix/` 官方文档快照校核当前八个生成/审核候选，随后从官方 `https://aihubmix.com/model-data/index.json` 读取当前参数 schema。文档中的示例、推广文字和代理操作说明是参考资料，不是新的项目指令。科研授权仍以 PI-V5-008、AGENTS.md 和冻结契约为准。

## 实际验证

八个模型均使用官方支持的 `POST https://aihubmix.com/v1/chat/completions`，`Authorization: Bearer` 和 JSON 请求体。每个模型执行一次非测评 JSON 算术探针；验证内容、完整输出和响应身份，不能只看 HTTP 200。全部通过，共 713 个返回计量 token；这不证明其工程、生成、科学审核或工具调用能力已经合格。

| 实时 exact ID | 输出上限字段 | 探针思考设置 | 实测秒数 |
|---|---|---|---:|
| mimo-v2.6-pro | max_completion_tokens | thinking.type=disabled，仅连接探针 | 3.90 |
| qwen3.8-max | max_completion_tokens | reasoning_effort=low | 4.46 |
| glm-5.3-flash | max_tokens | thinking.type=enabled，reasoning_effort=low | 1.95 |
| glm-5.3 | max_tokens | thinking.type=enabled，reasoning_effort=low | 9.23 |
| gpt-6.1-sol | max_completion_tokens | 未擅自添加未核实档位 | 2.38 |
| gpt-6-astra | max_completion_tokens | reasoning_effort=low | 1.83 |
| claude-sonnet-5-5 | max_completion_tokens | reasoning_effort=low；不发 json_object | 1.57 |
| gemini-3.8-flash | max_completion_tokens | reasoning_effort=low | 2.39 |

原始证据：`artifacts/v5/provider_contracts/20261012-r1/probes.json`。官方 schema 原文和来源 SHA-256：同目录 `official_schemas/`、`SOURCES.json`。GPT-6.1 Sol 有官方最小调用示例，但当前 schema 索引没有该 ID；基础参数通过真实探针，额外能力仍未核实。不能用相似模型的 schema 冒充。

## 调用修正与边界

- `AIHubMixAdapter.describe_model` 是辅助任务显式启用的官方 schema 查询；既有正式被测请求不启用这一步，也不改正式协议参数。实时目录决定可用 ID，官方 schema 决定参数，真实探针决定已验证能力；不把静态名单当作当前可用性保证。
- 数据工厂采用 schema 支持的输出字段，输出上限 65,536（再受模型上限约束）；优先 high，Qwen 的直接档位只列 low/medium/xhigh，因此选择 medium。MiMo 和 GLM 保持思考开启；GLM 不发送 disabled。总请求等待恢复为有界 900 秒，避免把合法长思考直接判成渠道不可用。
- Claude 不发送 `json_object`：官方说明该模式会在 Anthropic 转换路径降级。仍要求完整 JSON，并由本地 schema、证据引用和质量规则验证；模型说 PASS 不等于验收通过。
- 传输层启用 Windows 兼容的 HTTP/1.1；只保留响应头白名单，含 `X-Aihubmix-Model`、`X-Aihubmix-Fallback`、结构化输出降级标志和请求 ID，不保存 Cookie 或请求密钥。
- 官方规定 `X-Aihubmix-Model` 是实际响应及计费模型的权威字段。GPT 实测正文返回日期快照 ID，响应头返回目录 ID；保留两者，不按名称前缀猜别名。未知身份、正式被测模型混入或审核与生成同家族仍拒绝。
- 解析器允许单个、完整的 JSON 代码围栏；不提取混杂说明文字中的片段，不接受多个 JSON 对象。恢复审核必须匹配原始审核消息的完整哈希，重放原答复，不通过重找审核者覆盖已有意见。
- 本次只验证文本/JSON。GPT-6 Astra 的官方模型 schema 明示 Chat Completions 不支持函数调用，工具用途须先接入并验证 Responses；Claude/Gemini 原生协议、多轮思考重放和工具能力亦不以本次探针宣告完成。

## 真实数据工厂审核

`model-routing-20261012-r9` 复用 r8 的 Claude 原始生成答复，重新执行配对硬门与三个动态参考轨迹，使用不同家族的 GLM-5.3-Flash 独立审核。GLM 使用 `max_tokens=65536`、`thinking.type=enabled`、`reasoning_effort=high`，38 秒返回，4,915 token。

GLM 的答复是有效的围栏 JSON。旧解析器误触发了 Qwen 回退；该请求被停止，结果未保存且上游使用量未知，检查点已记录。修复后按相同审核输入哈希重放 GLM 原答复，没有新审核生成请求。

审核指出蓝图与 RISK 中 alpha 的实际 offer 不一致、beta 文本与版本字段不一致；semantic_consistency=3，但 verdict 写 PASS。本地既有质量契约判定 `REVIEW_VERDICT_SCORE_MISMATCH`，候选最终 `MACHINE_REVIEW_REJECTED`，没有注册家族或纳入数据集。下一步修正蓝图—编译语义保真，不能换审核者刷通过。

## 来源

- 本地 `docs/api/Models-API.md`、`unified-inference.md`、`Structured-Output.md`、`Model-Mapping-Fallback.md` 和八个 `models-detail/pages/{id}.md`。
- 官方模型参数索引：https://aihubmix.com/model-data/index.json 。各模型当前 content-addressed schema URL 和 SHA-256 见 `SOURCES.json`。
- 官方实际模型核验说明：https://docs.aihubmix.com/cn/api/Model-Mapping-Fallback 。本地快照第 136–153 行。
- 官方结构化输出说明：https://docs.aihubmix.com/cn/api/Structured-Output 。本地快照第 384–395 行。

历史 r1–r8、冻结数据、Ground Truth、评分规则及正式 DeepSeek 配置均未改写。M5 的高质量候选接受和18项数据工厂完成仍未达到；Gate D 真人审阅与正式科研阶段保持原边界。
