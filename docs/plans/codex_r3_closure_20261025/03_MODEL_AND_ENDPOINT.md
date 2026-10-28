# 03｜AIHubMix / DeepSeek 调用方案：国内可达、质量优先、不省输出

## 已确认的信息

- 模型：**`deepseek-v4.1-flash-1017`**；不要自作主张替换成旧模型 `deepseek-flash` 或不同部署，除非用户明确变更。
- AIHubMix 模型网页公开的上下文：**约1,000,000 tokens**；最大输出：**约393,216 tokens**（393K，常被近似写为384K）。这是供应商页面能力，不保证任何一次调用能填满。
- **备用域名由AIHubMix官方披露**：主域名不可用时 `https://api.inferera.com` 代替 `https://aihubmix.com`，path、key、model、body不改。对于当前项目使用的 OpenAI Chat Completions 协议，**Base URL = `https://api.inferera.com/v1`**，完整路径是 `/v1/chat/completions`。用户已经在本机改过，优先保留最新改动。
- 用户说明大陆网络访问主域名有地域可达性问题；不要为了跑接口绕去操作系统级代理/VPN。只使用既有普通HTTPS连接和所配置的备用接口。
- R2实证：`max_tokens=393216` 曾被网关接受，但这**不是**实际384K正文输出的实测；旧R3报告仍存在请求终态未决。不能忽略完整SSE终态。

## 代码改动落点：端点一致，不另造SDK

先审实际本机版本中的：

`src/ioabench/v5/ai_generation/aihubmix_study.py` (`BASE_URL`)；
`src/ioabench/models/aihubmix.py` (`AIHubMixAdapter`默认 base_url)；
`scripts/v5/tf_r3_pilot.py` (`POLICY["base_url"]`、`study_for()`适配器)；
`scripts/v5/aihubmix_preflight.py`；
`src/ioabench/v5/ai_generation/auxiliary_runtime.py`（已有双域名认可）；
`config/v5/`下provider路由配置（若有）。

如果目前已全部指向 `api.inferera.com/v1`，只需小检查，不继续改。若只改了某一层导致 `AihubmixStudy` 检测 `port.base_url != BASE_URL`，**统一现存配置**，优先添加/复用一个明确的环境配置入口，避免同一URL在五份来源互相冲突。不因为 endpoint 变化而改业务或评分逻辑；与已冻结旧run保持分离。

## 具体模型参数（给 Codex 的默认策略）

- 生成工作流结构：`thinking.enabled`，`reasoning_effort=high`，`max_tokens=131072` 起；困难结构/连贯长任务用 `max`、`max_tokens=262144`。
- 很复杂的机制构造、反复证据链审核或确认遇到**完整收流的 length 截断**：可用 `max_tokens=393216`，前提是接口确实接受，且上下文+输出组合满足真实约束。
- 研发审核：不再把复杂 case 默认锁在 `16384`。按该请求自身实际内容及已有实测选择 `131072` 或 `262144`；需要时393216。不因省钱提前停止。
- 输入上下文：不设置 `120K` 等人为软阈值；仍只提交当前任务确实相关的上下文，以避免语义噪声；不要为装满1M而填无关材料。必要时按平台输入+输出总窗约束进行检查。
- `temperature`：不擅自混入未确认组合。先继承现有R2/R3已验证的参数契约，分不同活动明确冻结。输出 `response_format={"type":"json_object"}` 当网关支持，始终做 JSON schema/引用检查；不靠语言指令代替校验。
- `stream=true` / SSE 是默认传输方式；持续读取分块至完整finish + usage，严禁把连接中断的半份 JSON 算成功。对 JSON 对象正文极长的任务，先识别 `finish_reason=length`/空正文/推理正文分配不够、TCP中断/HTTP错误等不同原因。
- `reasoning_effort` 是否支持 `max`、`thinking` 同时传参、可用最大 `max_tokens`，以现有 `PROVIDER_CONTRACT` 和当前 API 探针为准；**只有出现字段不支持的明确HTTP证据，才对该字段做最小回退**。不要预设兼容性错误而统一降级。

参考请求体（不是要求独立写新HTTP客户端；通过现有Port发送）：

```json
{
  "model": "deepseek-v4.1-flash-1017",
  "messages": [
    {"role": "system", "content": "Return a complete JSON object matching the supplied schema."},
    {"role": "user", "content": "<workflow design task and constraints>"}
  ],
  "thinking": {"type": "enabled"},
  "reasoning_effort": "high",
  "max_tokens": 262144,
  "stream": true,
  "response_format": {"type": "json_object"}
}
```

**注**：请求体是现有项目R3接口约定的示意，并非已在 `api.inferera.com/v1` 当天重新实测成功；Codex在调用前读其本机已保存的实际模型合同，若 `reasoning_effort`、`response_format`、`stream` 组合不兼容，记录HTTP状态与明确错误，再精简唯一不兼容字段。用户不在乎费用，所以不应降到16K以省钱。

## 请求状态管理（只留下真必要约束）

- `SUCCESS`：身份符合、SSE有完整终态、JSON符合schema、usage/日志完整，才可用于入池。
- `MODEL_LENGTH`：完整终态但length截断；可新候选ID增加输出长度或合理拆分阶段，原始结果保留，不称网络故障。
- `TRANSPORT_INTERRUPTED`：断流且无可确认终态；保持 `UNKNOWN`，不可重新发相同POST；必要时在业务允许时用新任务/ID发新尝试并单独记录，不把它算恢复成功。
- `AUTH_ERROR` / `MODEL_UNAVAILABLE`：明确401/403等，停止对同问题的盲目批量重试，定位账户/端点/模型是否匹配；不能借此降质量门或伪造response。
- 费用：**不设置USD hard stop/soft stop**；usage仅作运行观察与实验效率指标。全记录失败分母、延迟和发送/完成Token，以帮助提高成功率，不是限制消费。

## 密钥使用

密钥已由用户在本机提供。Codex 直接调用现有 `load_workspace_env()` 或进程环境变量 `AIHUBMIX_API_KEY`；不用用户再复制粘贴。任何工作流文档、源码patch和外发审查包不需要密钥字面值。此项不是成本或权限障碍，不应因过度包装凭据而停滞工作。

## 首轮验证的最小必要动作

1. 查看本机 Base URL 统一性，已有验证结果可复用。
2. 若需实测，做**一次小的、结构化真实请求**证实模型+域名+thinking+SSE+JSON可用；验 `served_model/headers` 与 `finish_reason`。不做无意义的“试着输出384K”烧时实验。
3. 后续正式生成沿用同一冻结参数 profile，在执行数据里记录参数、成功/失败和源码hash。
