# 参数修正与源码交付补充（2026-10-19 R2）

本轮实际修正辅助模型调用参数，并执行6个模型的新基础JSON/身份预检。MiMo Pro/Flash、GLM输出上限131072；Sol/Luna128000；Gemini65536。Sol Medium、Luna Max、Gemini High和GLM文档推荐Max均保留。详见[完整参数与命令](v5/V5_AUXILIARY_FULL_PARAMETERS_20261019.md)。

共享ModelPort调用栈不再用8192/16384/65536覆盖文档上限，也不再静默降低思考档位。旧低预算预检不能授权新配置；独审资格必须绑定相同参数下的固定正负控制和当前运行源码。工具协议不兼容则明确拒绝，不用降档绕过。正式DeepSeek SUT配置保持原样。

6次真实请求全部完成，prompt202/completion601/total803Token，目录估价USD0.0015529412，非账单；本批无未决请求。DeepSeek精确整数上限未证实、Qwen Next ID未唯一解析，两者本批NOT_RUN。

完整回归实际1496项通过，0失败/错误/跳过，207.34秒，包含4项打包正负测试。源码SHA-256：`c3d0cdaf53f2a486149da9e03947caaf35b129a924e173b005f636c6bc41e6c1`。回归结果、源码身份、精确请求与响应在`artifacts/v5/provider_contracts/full-parameters-20261019-r1/`：`REGRESSION.xml`、`REGRESSION.txt`、`IMPLEMENTATION_CHECK.json`及逐模型证据。首轮回归失败记录保留在`artifacts/v5/provider_contracts/parameter-policy-20261019-regression.txt`；旧夹具缺少严格schema绑定已补全，运行中源码变化造成的Replay绑定失败通过源码稳定后的完整复跑核实，不降低检查。

新源码包入口：`exports/source-code-20261019-r2/IoA-Bench-source-code-20261019-r2.zip`；实际包验收见同目录`PACKAGE_VERIFICATION.json`。复用既有打包器，检查CRC、逐文件SHA、凭据扫描及独立解压源码对照；脚本及计划路径不表示已通过。旧10月19日及10月18日包保留。

R13实施结果和局限仍见[原完成文档](WORK_COMPLETION_20261019.md)。结构容量49、全历史新科学家族0、原开发面板和独审记录没有被本轮重算。新配置的独审控制、难度面板、生产链、确认性Pilot、正式Campaign和真人实验均NOT_RUN；机器独审仍无当前合格者，科学有效性NOT_ESTABLISHED，formal_accepted=false，publication_ready=false，T361–T363仍SIMULATION_ONLY。
