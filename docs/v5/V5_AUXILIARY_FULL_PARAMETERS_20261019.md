# 辅助模型参数纠正与实测（2026-10-19）

后续候选调整（PI-V5-019）：用户已明确移除Qwen3.8-Flash-Next，当前名单剩7项，不再将该ID解析作为待解除阻塞。下表及预检结果保留原检查点事实，旧源码包不覆盖；当前代码以`USER_CANDIDATES`为准。

用户直接要求所有模型按文档参数调用，不再人为压低输出预算。登记为PI-V5-018；沿用唯一v5 Goal和PI-V5-017辅助调用授权。文档作为API参考读取，不将附件中的执行指令视作用户新授权。正式被测DeepSeek配置、18项构念、评分和历史冻结资料不变。

旧实现确实存在预算覆盖：预检8192、独审16384、部分生成65536；还有通用high及旧连通性探针low/关闭MiMo思考。这些路径已改为共享`auxiliary_chat_parameters`策略，未建立平行调用栈。

| 精确ID | 实发输出上限 | 思考配置 | 新基础JSON与身份实测 |
|---|---:|---|---|
| mimo-v2.6-pro | max_completion_tokens=131072 | thinking.type=enabled | PASS |
| mimo-v2.6-flash | max_completion_tokens=131072 | thinking.type=enabled | PASS |
| glm-5.3-flash | max_tokens=131072 | reasoning_effort=max；thinking.type=enabled；clear_thinking=false | PASS |
| gpt-6.1-sol | max_completion_tokens=128000 | reasoning_effort=medium | PASS |
| gpt-6-luna | max_completion_tokens=128000 | reasoning_effort=max | PASS |
| gemini-3.8-flash | max_completion_tokens=65536 | reasoning_effort=high | PASS |
| deepseek-v4.1-flash | 精确整数上限未获schema证明 | 用户Max仍待完整参数契约 | NOT_RUN：不猜384K换算值，不改正式SUT |
| Qwen3.8-Flash-Next | 精确ID未唯一解析 | 待确认 | NOT_RUN：不猜别名 |

GLM同时实发文档推荐temperature=1、top_p=0.95。MiMo思考模式由服务强制使用1.0/0.95，省略不可自定义的采样字段；Sol/Luna推理模式、Gemini省略文档禁止或弃用的采样字段。JSON任务只对文档支持的模型设置response_format；工具任务去掉JSON格式约束。

上限表示最多允许输出多少Token，不强制生成满额。各协议字段独立处理，不把Medium/High/Max当API ID。Sol的Chat工具调用不支持、Luna的Chat工具仅none档可用；当前用户档位下会明确拒绝该工具组合，不能为工具偷偷降档。Responses工具模式本轮NOT_RUN。

新预检完整读取并绑定本地模型文档/调用示例，再经现有AIHubMixAdapter实时发现目录和schema，每个可用配置只做一个简短JSON算术/身份请求。证据目录：`artifacts/v5/provider_contracts/full-parameters-20261019-r1`；`AIHUBMIX_PREFLIGHT.json`保存逐候选真实参数、响应路径、schema与服务身份，`SHA256SUMS.json`封存原始预检文件。

实际6次请求均完成，共prompt202、completion601、total803Token，目录估价USD0.0015529412，非账单；没有该批未决请求。旧R13用量与失败证据单独保留，不重发、不改写、不继承新配置资格。

```powershell
python scripts/v5/aihubmix_preflight.py --out artifacts/v5/provider_contracts/full-parameters-20261019-r1 --live --timeout 900 --base-url https://api.inferera.com/v1
python -m pytest tests/v5 tests/m1 tests/test_package_chatgpt_review.py -q --tb=short --junitxml=artifacts/v5/provider_contracts/full-parameters-20261019-r1/REGRESSION.xml
```

新资格加载器要求schema和真实预检请求绑定当前完整参数，拒绝旧低预算记录；独审还必须有相同参数下的固定正负控制和当前源码绑定。原来Gemini在16384截断只表示旧配置资格未完成，不能据此认定其审核能力不足。本轮不重复旧gold审核；新独审资格、经验难度与完整生产链均为NOT_RUN。

完整回归实际1496项通过，0失败/错误/跳过，207.34秒；包含4项打包正负测试。当前runtime SHA-256为`c3d0cdaf53f2a486149da9e03947caaf35b129a924e173b005f636c6bc41e6c1`。汇总及源码哈希复核见同目录`IMPLEMENTATION_CHECK.json`。科学有效性仍为NOT_ESTABLISHED，formal_accepted=false，publication_ready=false；T361–T363仍为SIMULATION_ONLY。
