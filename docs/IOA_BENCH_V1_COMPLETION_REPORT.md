# IoA-Bench v1 完成与最终科研验收说明

> 文档版本：`v1.1-scientific-acceptance`
>
> 验收日期：2026-09-25
>
> 最终 Run ID：`deepseek-v4.1-flash-v1-pack-v2-r5`

## 1. 最终结论

IoA-Bench v1 已完成最终科研验收。最终运行使用 AIHubMix 的精确模型
`deepseek-v4.1-flash`，固定 `DATASET_PACK_v2`，18 个 suite 各 90 个正式
case，共 1620 个 case。全部 work unit 为 `VALID`，每个 case 都有完整
Replay，Replay hash 和冻结 case 审计全部通过。

这次验收实际检查了 Manifest、Frozen Case 执行、模型可见数据、两个
tested-model Agent、scripted peer、独立 source record、naive baseline、
Replay、评分、报告和发布包，而不是只检查文件是否存在。

最终机器可读 gate：`artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json`。

## 2. 审计修复历史

外部 Final Scientific Acceptance Audit 发现了旧正式运行的四个 P0 问题：

1. Formal Manifest 与调度时读取的 Dataset Pack 不一致。
2. Runtime 没有直接执行完整 Frozen Case。
3. 多数 formal case 没有真正形成多 tested-agent IoA 执行链。
4. Scorer 与 Runtime 没有闭环，unsafe baseline 不能稳定触发危险结果。

这些问题已修复并通过回归测试。历史结果不被覆盖：

| Run | 处理 | 原因 |
|---|---|---|
| `deepseek-v4.1-flash-v1` | `INVALID_FOR_SCIENTIFIC_BENCHMARK` | 旧数据版本和 generic skeleton 执行链 |
| `deepseek-v4.1-flash-v1-pack-v2` | `INVALID_FOR_SCIENTIFIC_BENCHMARK` | 独立证据缺陷确认后中断 |
| `deepseek-v4.1-flash-v1-pack-v2-r2` | `INVALID_FOR_SCIENTIFIC_BENCHMARK` | scorer 修复后不能混合旧运行 |
| `deepseek-v4.1-flash-v1-pack-v2-r3` | `INVALID_FOR_SCIENTIFIC_BENCHMARK` | provider 阻塞 I/O 修复后不能混合旧运行 |
| `deepseek-v4.1-flash-v1-pack-v2-r4` | `INVALID_FOR_SCIENTIFIC_BENCHMARK` | T312 Replay scenario 缺少 `sut_payload` 和 hash |
| `deepseek-v4.1-flash-v1-pack-v2-r5` | `PASS` | 最终科研验收运行 |

所有历史数据集和历史 Replay 均保留，不进行原地修复。

## 3. Reference IoA 交付范围

v1 是 Windows 兼容的本地 Python profile，不依赖 Docker、Kubernetes、
PostgreSQL 或 ClickHouse。四个本地数据面保持分离：

| 数据面 | 内容 | 测试 Agent 是否可直接访问 |
|---|---|---|
| Control | lifecycle、Manifest、checkpoint、scheduler | 否 |
| Oracle | Ground Truth、隐藏标签、评分真值 | 否，evaluator-only |
| SUT | Agent 可见业务状态和 Sandbox 状态 | 只能通过授权工具 |
| Telemetry | 规范化事件、模型 I/O、工具调用、Replay | 否，评估器读取 |

Reference IoA 组件包括 Organization、Registry/Discovery、Identity、
Authorization、Delegation、Router、A2A、MCP、Sandbox、Knowledge、
Reputation、Incentive、Memory、Telemetry、Replay 和 Dashboard。

每个 formal replay 至少保留两个独立 `TESTED` Agent 和一个可重放的
`SCRIPTED` peer，并保存 Registry、Identity、Delegation、Authorization、
Router、Reputation、Knowledge、Incentive、A2A、MCP、Sandbox 状态，以及
`Exposure -> Recognition -> Verification -> Decision -> Action -> Recovery`
六阶段事件链。

## 4. ModelPort 与 AIHubMix

所有 Agent 模型调用均经统一 `ModelPort`、`ModelRequest`、`ModelResponse`
和 `ModelProfile`。AIHubMix HTTP/OpenAI-compatible 细节只位于
`AIHubMixAdapter`。

最终 Manifest 记录：

- Provider：`aihubmix`
- Exact model ID：`deepseek-v4.1-flash`
- Runtime：`scientific-runtime-4`
- Execution concurrency：`16`
- Action budget：4 rounds、4 model calls、4 tool calls
- Source tool：`query_source_record`
- Python：`3.12.10`
- Dependency lock SHA-256：`a7d63cae1c517aafcd2a8f0d92b0203faf70c14cbd551809bac6dc1a3ed49fa9`

API key 只通过当前进程的 `AIHUBMIX_API_KEY` 使用，没有写入代码、文档、
Manifest、Replay 或 release bundle。Provider adapter 使用线程化 I/O，
避免同步 HTTP 调用阻塞异步 checkpoint scheduler。

## 5. Dataset Pack v2

`data/datasets/DATASET_PACK_v2.yaml` 固定 18 套新版本数据。每套 90 个
case，Easy/Medium/Hard 各 30 个，总计 1620 个。所有 suite 通过 schema、
Ground Truth、exposure、deduplication、prompt leakage、双 validator 和
内容 hash 检查。T361–T363 明确标记为 `SIMULATION_ONLY`。

| Suite | 中文名称 | Cases | Valid | Task Utility | Outcome 分布 | 状态 |
|---|---|---:|---:|---:|---|---|
| T311 | 资格伪装 | 90 | 90 | 88.89% | 55 EARLY_SAFE / 35 FULL_FAILURE | VALID |
| T312 | 注册失真 | 90 | 90 | 48.89% | 90 EARLY_SAFE | VALID |
| T313 | 代表资格漂移 | 90 | 90 | 50.00% | 90 EARLY_SAFE | VALID |
| T321 | 协商污染 | 90 | 90 | 52.22% | 89 EARLY_SAFE / 1 UNSAFE_ACTION | VALID |
| T322 | 互操作失配 | 90 | 90 | 50.00% | 90 EARLY_SAFE | VALID |
| T323 | 责任链断裂 | 90 | 90 | 60.00% | 82 EARLY_SAFE / 8 UNSAFE_ACTION | VALID |
| T331 | 跨系统级联扩散 | 90 | 90 | 50.00% | 90 EARLY_SAFE | VALID |
| T332 | 结构暴露 | 90 | 90 | 65.56% | 75 EARLY_SAFE / 15 UNSAFE_ACTION | VALID |
| T333 | 行为推断 | 90 | 90 | 53.33% | 87 EARLY_SAFE / 3 UNSAFE_ACTION | VALID |
| T341 | 生态错误共识 | 90 | 90 | 65.56% | 76 EARLY_SAFE / 14 UNSAFE_ACTION | VALID |
| T342 | 谣言扩散 | 90 | 90 | 0.00% | 90 EARLY_SAFE | VALID |
| T343 | 规范漂移 | 90 | 90 | 52.22% | 89 EARLY_SAFE / 1 UNSAFE_ACTION | VALID |
| T351 | 激励错配 | 90 | 90 | 50.00% | 90 EARLY_SAFE | VALID |
| T352 | 声誉垄断 | 90 | 90 | 54.44% | 90 EARLY_SAFE | VALID |
| T353 | 节点操纵 | 90 | 90 | 72.22% | 70 EARLY_SAFE / 20 UNSAFE_ACTION | VALID |
| T361 | 判断让渡 | 90 | 90 | 51.11% | 88 EARLY_SAFE / 2 UNSAFE_ACTION | SIMULATION_ONLY |
| T362 | 讨论扭曲 | 90 | 90 | 48.89% | 71 EARLY_SAFE / 19 UNSAFE_ACTION | SIMULATION_ONLY |
| T363 | 能动性弱化 | 90 | 90 | 47.78% | 90 EARLY_SAFE | SIMULATION_ONLY |

Frozen dataset 不允许原地修改。v2 修复了 v1 的数据质量/提示泄漏治理
问题，所有新版本均保留 provenance、validator 输入 hash 和 rejected
candidate 记录。

## 6. 正式运行结果

### 6.1 完整性

| 指标 | 结果 |
|---|---:|
| Work units | 1620 |
| `VALID` | 1620 |
| `INVALID` / `UNSUPPORTED` / retryable terminal | 0 |
| Replay files | 1620 |
| Replay hash matches | 1620 |
| Replay audit failures | 0 |
| Manifest dataset pack | `DATASET_PACK_V2` |

### 6.2 Outcome 分布

| Outcome | 数量 |
|---|---:|
| `EARLY_SAFE` | 1502 |
| `LATE_RECOVERY` | 0 |
| `UNSAFE_ACTION` | 83 |
| `FULL_FAILURE` | 35 |

这组结果没有被解释为“模型绝对安全”。出现的 `UNSAFE_ACTION` 和
`FULL_FAILURE` 说明 Runtime、scorer 和 baseline 已经能够观察到危险动作；
Safety 与 Task Utility 仍然分别报告。

### 6.3 资源与效率

| 指标 | 结果 |
|---|---:|
| 加权 Task Utility | 53.40% |
| Model calls | 4885 |
| Tool calls | 4105 |
| Prompt tokens | 6,346,615 |
| Completion tokens | 1,844,608 |
| Total tokens | 8,191,223 |
| 总模型延迟 | 6,628,283.25 ms |
| 估算成本 | `$1.112106609152` |

成本使用 2026-09-25 的 AIHubMix catalog 快照估算，不等同于账单。快照
来源记录在 `metrics/summary.json`，并区分 input、output、cache-read 单价。

## 7. 科学有效性和限制

- Ground Truth 由程序化 Oracle 先生成；模型不可读取 Oracle path、隐藏标签或 scorer 规则。
- 正式 Agent scaffold 使用中性 system prompt，不要求模型暴露私有 chain-of-thought。
- `query_source_record` 返回独立 source record；它不是完整 `case_payload` 的别名。
- naive baseline 在 18/18 suite 触发 `UNSAFE_ACTION` 或 `FULL_FAILURE`；safe mock baseline 不被判为危险。
- T361–T363 是固定 synthetic personas 的 `SIMULATION_ONLY` 结果，不能表述为真实人类实验。
- 每个 case v1 默认只运行一次，不能估计模型随机方差；论文或横向比较应增加 repetition。
- Safety raw metrics 不强行合成为单一 18-suite 总安全分。
- 正式运行期间不允许公共 Internet 工具；业务资源是本地 synthetic Sandbox。

## 8. 验收与复现命令

在当前进程设置 AIHubMix key 后执行：

```powershell
$env:AIHUBMIX_API_KEY = "<process-only secret>"
python -m ioabench.cli validate-spec
python -m ioabench.cli run-validate --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m ioabench.cli replay-audit --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m ioabench.cli analyze --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m ioabench.cli report --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m pytest -q
```

一键重新执行全部 suite 的命令为：

```powershell
$env:AIHUBMIX_API_KEY = "<process-only secret>"
$env:IOABENCH_CONCURRENCY = "16"
python -m ioabench.cli run --model deepseek-v4.1-flash --suite all --dataset-pack v2 --run-id <new-run-id> --resume
```

正式 Run 的关键证据：

- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/manifest/`
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/completeness.json`
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/results.json`
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/replay/`
- `artifacts/runs/deepseek-v4.1-flash-v1-pack-v2-r5/replay-audit.json`
- `data/reports/deepseek-v4.1-flash-v1-pack-v2-r5/`
- `artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json`

## 9. Dashboard 与发布包

Dashboard 启动：

```powershell
python -m ioabench.cli dashboard --run deepseek-v4.1-flash-v1-pack-v2-r5 --port 8765
```

提供页面、JSON API、18 套结果、六类风险画像、代表性 Replay 和
`SIMULATION_ONLY` 标记。

最终发布目录：`release/ioabench-v1.0-research-prototype/`。发布包包含
规范、contracts、源代码、测试、DATASET_PACK_v2、Run Manifest、checkpoint、
results、Replay、metrics、report、Dashboard artifacts、最终 gate 和
文件级 SHA-256 清单；不包含 `.env` 或 provider credentials。

## 10. Definition of Done 对照

| DoD 项目 | 状态 |
|---|---|
| 本地 Reference IoA 无 Docker 启动 | PASS |
| ModelPort + AIHubMix exact model validation | PASS |
| 18 个 T311–T363 suite | PASS |
| 18 x 90 Frozen Dataset v2 | PASS |
| Frozen Manifest、case execution、Replay audit | PASS |
| Safety / Utility / efficiency / cost 分离 | PASS |
| checkpoint/resume | PASS |
| 一键 `suite all` | PASS |
| Dashboard、Replay、report、risk profile | PASS |
| `deepseek-v4.1-flash` 全量正式运行 | PASS |
| T361–T363 `SIMULATION_ONLY` | PASS |
| v1 reproducibility bundle | PASS |

项目状态、Work Queue、CHANGELOG 和最终 gate 均以 r5 证据为准；旧的
工程集成运行不会覆盖最终科研运行。
