# IoA-Bench v5：R13 后续实施与真实验收

本轮结论为 **PARTIAL / BLOCKED_MACHINE_QUALIFICATION_AND_PROVIDER_AUTH**。八候选均已真实调用；开发生成、固定修复、结构执行、经典 T362 修复及历史重探已落地。当前合格独审者、机器合格样本、经全历史验证的新科学家族均为 **0**。唯一 v5 Goal、18项构念、原 Gold、评分与正式 SUT 不变。

当前 runtime SHA-256：`0a4b9c9551ad93b01c54e679b7229c5f08af3cceeeb6d2af760e87594590fb26`。起始 Git HEAD：`034c867e69d474bb13c9e18862a5a12ba4be2c50`。本地提交与新版包的实际校验见 [交付记录](../state/SOURCE_DELIVERY_20261019_R3.yaml)；原 r1/r2 包保留，不 push。

实际实施提交为`da4ba4e59cf67b8874ce9f8f42e098a83b490ded`；[新版源码证据包](../exports/source-code-20261019-r3/IoA-Bench-source-code-20261019-r3.zip)含7779文件，60,905,018字节，SHA-256为`6d6b885dbef123d64601d53966fc9c24506dac7bfccc640396206c41c5da5814`。成员、CRC、逐文件SHA、密钥扫描和7779文件独立解压核验均PASS，解压runtime与当前一致。包内SOURCE_MANIFEST及状态属于该实施提交的快照；打包后仅追加本段、交付收据与队列完成状态，差异由DELIVERY_METADATA_SHA256.json单独绑定，不回写包或科研证据。

| 验收项 | 结论 | 实际证据和限制 |
|---|---|---|
| 工程回归 | PASS | R3完整回归1562项，0失败/错误/跳过，进程退出0，运行前后runtime不变；另有打包/结算定向10项通过，不能与1562简单相加 |
| 确定性/因果/执行保真 | PASS（有界范围） | 18项36对、228参考检查；19 slice/18 typed、540能力参考执行；三样板各2结构及断开消费者负控 |
| 八模型协议与参数 | PARTIAL | 八款均有真实 JSON 和工具往返；Sol工具走Responses，Haiku走Messages；上下文边界、强制全长输出 NOT_RUN，思考强度效果 UNVERIFIED |
| 同任务生成 | PARTIAL | 192计划：39对工程有效、10拒收、6 Provider失败、3未决、134 NOT_RUN；受到真实401及一次Windows进度替换故障中断 |
| 固定片段修复 | PASS（窄范围） | 八款各3项，共24/24；先验证非法，再单次修复、编译、参考执行与Replay；不外推为通用修复质量 |
| 机器审核 | BLOCKED | 原Gold争议未取得独立盲审与PI裁决；保持两个draw各18/18，新资格调用 NOT_RUN |
| 结构多样性 | PARTIAL | 52声明组合中49可行；模型生成三套件各3种runtime结构；78例全部有历史行为匹配，新科学家族0 |
| 历史可比性 | PARTIAL | 7687唯一输入在当前源码重探：6661 PROBED、1026 INDETERMINATE；原源码Replay未建立 |
| 开发难度测量 | PARTIAL | 48计划，11完成、2中断、1基础设施失败、34 NOT_RUN；11 Replay、7批零调用resume通过；科学难度仍未校准 |
| 经典 T362 讨论扭曲 | PASS工程 / BLOCKED科学处置 | scenario/generator5.1.1，scorer5.1.0不变；20例、60参考、20runner/Replay/resume；旧结果保留 |
| 科学有效性 | BLOCKED / NOT_ESTABLISHED | Gold裁决、Gate D独立评价、科学难度设计与相关验证未完成 |
| 正式冻结/Pilot/Campaign/真人实验 | NOT_RUN | 未获本轮相应授权；T361–T363持续SIMULATION_ONLY |

八模型生成有效对数分别为 Sol9、GLM Flash2、MiMo Pro5、Haiku8、MiMo Flash4、Qwen Flash2、DeepSeek1017为7、GLM5.3为2。分母因中断而不同，不能按这些数字给出完整24任务排名。共同首组三目标Sol3/3，其余各2/3，仅支持暂用Sol做开发生成。24条窄修复质量并列；Haiku观测延迟最低，GLM Flash观测估价最低。独审和科学校准角色无人获得生产资格。DeepSeek1017仅在隔离开发集使用，未映射正式 `deepseek-v4.1-flash`。

39对工程候选的78例经当前源码历史比较：24精确重复、26近重复、28既有家族实例。378/378参考结果严格Replay通过，189批在临时副本执行零调用resume。原始请求、响应、拒收和不可判定证据均保留，[逐任务索引](../artifacts/v5/data_factory/next-r1/GENERATED_DATA_PROOFS/INDEX.json)可追溯每条数据。

开发面板11个完成回合的原评分均为SAFE，Utility均成功；其余37个计划回合不进入这个分母，不按安全成功处理。这只描述固定开发世界，标签仍为 `MEASURED_EXPLORATORY_UNCALIBRATED_LABEL`，不用于正式选题或难度定级。

本轮总账510次completion启动：493成功、14失败、3未决；报告1,214,168 tokens。缓存与原生协议用量归一后的已知估价小计为 **USD0.830890141988**，7条计费未知；这不是账单。MiMo Flash有一次reasoning token大于completion token的供应商记录异常；Qwen短长度负控也失败，原结果保留。[完整总账](../artifacts/v5/data_factory/next-r1/ALL_USAGE_LEDGER.json)保留真实ID、实发参数、终态、延迟、usage和估价。

完整性有两项明确限制。起始保护扫描与pytest并行，误收21个随后自动清理的临时文件，原146911项核验FAIL保留；其余146890个既有文件无变化、无缺失。首次恢复核验刷新了一个候选的3个mutable checkpoint，原SHA不重建，原RESULT不改；请求、响应、case、manifest、trace和score未变。后续使用临时副本完成严格Replay与恢复核验，该候选原快照仍PARTIAL。

交付的九项材料、实际命令、模型矩阵、结构报告、Gold审议包、SHA清单和最终状态集中在 [FINAL_ACCEPTANCE](../artifacts/v5/data_factory/next-r1/FINAL_ACCEPTANCE.md)。新包包含源码与本轮保留的生成/修复/开发面板调用和执行证据；庞大全历史runner及旧压缩档留主机，用来源清单和SHA定位，包不等于全部历史Replay库。

剩余外部条件：两份独立Gold盲审及PI裁决、completion凭据/渠道恢复证据、1026历史可比缺口的原始材料或科学处置、批准的科学难度与Gate D方案。当前未重发3个未决请求；没有合格独审前，第一条机器合格样本→三样板小批→18项生产仍BLOCKED/NOT_RUN。
