# 18项有限类型化能力与证据边界

构念唯一权威仍为 `contracts/v5/construct_maps.json`。动态能力映射复用 `contracts/v5/dynamic_world_capability_maps.json`，其 DRAFT 声明不等于运行通过。当前 `pipeline.suite_spec("Txxx", typed=True)` 实际注册 18 项；T312/T321/T331/T352 使用专用编译器，其他 14 项使用 `ioabench.v5.bounded-world-compiler/1.0.0`（下表记为 B1）。共有 19 个动态 slice，T321 包含 DYNA 和 DYNB；当前 typed T321 只编译 DYNA。

下表列出新增执行字段的完整枚举，斜线分隔合法值。它们在 CONTROL/RISK 中取相同值；两臂风险差分仍由原机制槽和 fine-arm 检查控制。场景列只写 `tXXX-dyna-scenario-` 后的版本号。负例均有实际测试/报告，个别“删回执”控制属于保留动作与 utility 的 trace 篡改测试，不能冒称真实 provider 故障。

| 套件 | 编译器；场景版本 | 有限执行字段/值 | 真实消费者；已执行拒收例 |
|---|---|---|---|
| T311 资格伪装 | B1；0.2.0 | `credential_reference_access=directory/requested_document` | 后者从目录移除凭证路径及文档镜像，`request_references` 在请求轮次后实际交付文档，issuer lookup 消费已交付引用；目录镜像泄漏、错误 holder 文档拒收。 |
| T312 注册失真 | `ai-t312-dyna-compiler/1.1.0`；0.2.0 | `operational_evidence=split_queries/bundled_manifest_receipts` | manifest 可携带同 endpoint 的真实 receipts，独立查询仍合法；缺 bundle、错 endpoint、把未来修订叙述当成已到通知拒收。 |
| T313 代表资格漂移 | B1；0.2.0 | `chain_projection=full_subgrants/subgrant_index` | index 分支同时投影 dispatch 与 chain view，仅 executor 能 `read_subgrant` 读取已派发且未撤销参数；参数镜像、错源参数、未派发/撤销引用拒收。 |
| T321 协商污染 | `ai-t321-dyna-compiler/1.7.0`；0.7.0 | `broker_count=2/3`；`peer_profile_delivery=initial/broker_gamma`；`offer_access=scheduled_push/broker_query` | gamma 资料只在 3 Broker 合法。查询模式发布 broker/offer_id 通知后，下一逻辑轮次的来源绑定 `read_offer` 才返回 schedule 原报价；缺/伪通知、错报价源、提前查询返回、状态与回执断连拒收。 |
| T322 互操作失配 | B1；0.2.0 | `native_record_access=direct/receipt_reference` | gateway/mapping 回执发出 actor 专属 native 引用，`read_native` 消费引用并读取当前目标记录；陈旧记录、错 instruction 源、未签发引用拒收。 |
| T323 责任链断裂 | B1；0.2.0 | `reconstruction_delivery=inline/queued_after_turn` | queued 请求仅回 pending；after_turn 安装重建记录并实际回传完整文档；安装但断开回复、提前同步返回拒收。 |
| T331 跨系统级联扩散 | `ai-t331-dyna-compiler/1.2.0`；0.3.0 | `fanout_width=2/3`；`propagation_topology=fanout/chain/fork_join` | fork/join 仅宽度 3：`a→b1,b2; b1→b3; b2→b3`；真实 forward/correction 投递、汇合输入和首次转发后的 rebroadcast 受检；缺汇合输入、漏冗余边、漏 correction 收件人拒收。 |
| T332 结构暴露 | B1；0.2.0 | `directory_projection=full_record/catalog_only` | catalogue 搜索只含 ID/category，完整记录经 `open_record`；投影泄漏、opening 提前投递 follow-up 拒收。 |
| T333 行为推断 | B1；0.2.0 | `metadata_access=opening/query` | query 分支 opening 仅含 index/policy/form，真实 `read_metadata` 返回 aggregates 后才可消费；opening 镜像泄漏、错误 aggregates 源拒收。 |
| T341 生态错误共识 | B1；0.2.0 | `recirculation_access=broadcast/committee_query` | 第一轮五人投票后广播同一 circulation，或发轮次通知后由 `read_circulation` 取得；缺消费者、错来源、提前广播、少一人第二轮机会拒收。 |
| T342 谣言扩散 | B1；0.2.0 | `register_access=all_hops/terminal_only` | 真实 AgentSpec/ModelRequest 工具 schema 和 handler 共同限制登记簿权限；terminal 查询 originating register，中间可不背书转交；越权、权限不一致、错来源、forward 无投递拒收。 |
| T343 规范漂移 | B1；0.2.0 | `activity_feed_access=push/handbook_query` | after_turn 切阶段，推送实际 feed 或通知后 `consult_handbook` 返回当前 feed；只回手册、陈旧阶段、提前第二阶段推送拒收。 |
| T351 激励错配 | B1；0.2.0 | `screening_publication=automatic_push/queued_history_reply` | history lookup 订阅后，实际 check 与原可用时刻共同决定回复；断开回复、回填更早 known-turn 拒收。 |
| T352 声誉垄断 | `ai-t352-dyna-compiler/1.2.0`；0.4.0 | `allocator_count=2/3`；`report_access=broadcast/local_receipt_query`；`reputation_governance=published_static/shared_rating_aggregate` | local 模式验证本人分配回执的内容/收件范围，其他报告按已完成 round 和 provider 查询；查询来源/时序及同 actor 后续实际模型请求须一致；shared 模式另验证真实评分聚合、发布和后续 `read_history`。两种治理均检查本地报告消费者；缺失/伪造/错源/错时序拒收。 |
| T353 节点操纵 | B1；0.2.0 | `catalogue_evidence=embedded_quotes/quote_on_request` | query 模式 catalogue 只含 ID/name，`request_quote` 返回真实报价；报价镜像、错误值、opening 提前 router push 拒收。 |
| T361 判断让渡 | B1；0.3.0；`SIMULATION_ONLY` | `item_release=serial_quiescence/paired_after_first` | 第一项后按 1/2 项批次释放；实际 reviewer 对每项处理一次且事件、状态和时序一致；缺/空/错/提前/重复 reviewer 结果拒收。 |
| T362 讨论扭曲 | B1；0.3.0；`SIMULATION_ONLY` | `evidence_access=shared_opening/record_query` | query 模式实际查询记录后构造引用；两模式均无公开预选 `evidence_post_id`；真实三人 report-volume 事件触发 moderator-only alert；预选泄漏、缺 alert、错源/时序拒收。 |
| T363 能动性弱化 | B1；0.5.0；`SIMULATION_ONLY` | `task_release=turn_advance/response_acknowledged` | ack 分支须当前 task 发布后有成功 `respond_to_analyst` 才释放下一项；flip 来源/通知绑定首个实际 post-flip 机会；缺响应依赖、伪通知、两臂相同或反向 flip 拒收。 |

专用编译器的额外边界同样固定。T312 固定 `T312-S2`，组织、operation、初始/修订 region 和 format 是受 schema 约束的实例字段；两 region 必须不同。T321 固定 `T321-S5`，item 数量为 1–8 且与标签数一致，`required_version>=1`，`conflicting_claim=true`，每臂 `offer_profiles` 必须精确声明程序执行的 secure/basic 配置。T331 固定 `T331-S5`；T352 固定 `T352-S1`、两家 provider、四轮，`reputation_rating` 只允许有限数值 `[4,5]`、三条两臂相同的轮次 note。它们均不允许任意图、新工具/渠道、额外 provider 或任意时序。B1 使用原动态生成器的 seed/subtype/difficulty 世界，只开放表中的一个字段及既有受限中性文本扩写；不是 AI 自定义完整世界。

T321 共有 6 个合法结构组合，两个“2 Broker + gamma 资料”组合应显式 `UNSUPPORTED`；T331 共有 5 个合法组合，宽度 2 的 fork/join 应拒收；T352 共有 8 个结构组合。组合计数只描述语法空间，不等于新家族数量。静态/行为去重、参考策略替代路径、独审与在线难度必须分别有证据。新增字段由 schema 拒收未知值，编译后还检查两臂一致性和实际消费者，不能仅凭字段出现就计结构多样性。

本次核对使用以下真实专项产物。数字来自各自记录的源码检查点，不能相加当作当前全库测试数：

| 范围 | 已执行工程证据 | 报告 |
|---|---|---|
| T311/T313/T322/T323/T351 | 85 项专项回归；30 个 pair Gate、192 个参考 episode；10 条替代安全轨迹和 10 个实际损坏消费者 | [授权与异步投递](../../../artifacts/v5/data_factory/upgrade-20261019/TYPED_AUTHORITY_DELIVERY_REPORT.md) |
| T312/T331/T332/T333/T353 | 98 项专项回归；fork/join 实际汇合输入、证据投影与来源/时序负例 | [证据访问及汇合拓扑](../../../artifacts/v5/data_factory/upgrade-20261019/TYPED_EVIDENCE_IMPLEMENTATION_REPORT.md) |
| T341/T342/T343 | 48 项专项回归；6 个 pair Gate、12 条替代安全 episode，缺消费者仍 SAFE+utility 的负例被拒收 | [知识证据投递](../../../artifacts/v5/data_factory/upgrade-20261019/TYPED_KNOWLEDGE_DELIVERY_REPORT.md) |
| T321 push/query | 124 项专项回归；18 个 pair Gate、108 个参考 episode；5 个实际运行故障及 4 个 trace 篡改控制拒收 | [报价访问结构](../../../artifacts/v5/data_factory/upgrade-20261019/T321_OFFER_ACCESS_DELIVERY_REPORT.md) |
| T352 反馈 | 4 个正例 pair Gate、28 个 runner execution、28 个 recorded-response replay；2 个断连消费者负 Gate | [真实反馈消费者](../../../artifacts/v5/data_factory/implementation-20261019/t352-feedback-r2/REPORT.md) |
| T352 0.4.0 报告 | 86 项修复后专项回归；18 个实际回执/查询/后续消费破坏例拒收，当前轮采样等替代合法路径通过 | [报告消费者修复](../../../artifacts/v5/data_factory/upgrade-20261019/T352_REPORT_FIDELITY_APPLIED_R10.md) |
| T361/T362/T363 消费者 | 63 项 R3 回归，含 reviewer、实际 alert、无预选 Oracle 字段及通知绑定；其中 T363 为旧 0.4.0 | [模拟消费者修复](../../../artifacts/v5/data_factory/upgrade-20261019/SIMULATION_CONSUMER_FIX_IMPLEMENTATION_REPORT.md) |
| T363 0.5.0 | 98 项修复后回归；5 subtype × E/M/H × 2 release 的 30 pair；两生产失败 seed 重现后通过，错误 flip 负例拒收 | [T363 两臂修复](../../../artifacts/v5/data_factory/upgrade-20261019/T363_HARD_FLIP_PAIRING_REPORT.md) |

`scripts/v5/factory_capability_manifest.py` 从实际adapter grammar构建清单，尝试全部有限enum单元。当前文件 [capability-manifest-20261019-r5](../../../artifacts/v5/data_factory/capability-manifest-20261019-r5)实际记录18 typed注册/支持、19 slice和540个参考episode，保留上述3个不可行组合的 `UNSUPPORTED`；runtime source为 `4f7fc7c842ea63a352157baffe8252838fdc06332e2839fd3ddb6f250e04e9e5`，含T363 0.5.0、T352 0.4.0。它覆盖默认例与seed绑定grammar单元，不覆盖任意图。52声明组合中49规范可行结构、3剪枝；当前覆盖r8实际选择44规范结构、132对/264例/828参考检查。不能将难度或叙述变化计为额外结构，也不能把这些局部计数加总成独立科研样本。

R13实际完整v5+m1回归1486项通过；当前72真实参考episode的暴露/机会、消费者证明、严格Replay及无新增调用恢复通过，见 `DETERMINISTIC_ACCEPTANCE_R13.json`。当前统一全18 typed offline入口实际36检查/228参考检查、API0，help与执行均exit0，见 `CLI_ALL18_OFFLINE_R13.json`；R11/R12原证据保留原source身份。R13实际池18条目/36场景，结构/机器/经验/科学正式层36/0/0/0；build/verify、674文件零写恢复与篡改副本拒收均有实际证据。线上难度/审核/生产的最终结果见04文档，未执行项为 `NOT_RUN`。独审准确性、重复一致性、全历史新家族、经验难度、科学有效性与正式冻结分别判定。E/M/H在专项测试中仍是设计输入标签，参考策略不能充当真实在线难度测量。18项数据不因typed注册获得正式接受；T361–T363不代表真人效应，确认性Pilot、正式Campaign、真人实验与正式冻结仍须相应授权。
