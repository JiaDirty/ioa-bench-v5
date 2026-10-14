# 2026-10-11 审计后执行队列：P0–P5

> 此队列是 `state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml` 的待合并补充任务，**不能作为独立 Goal / 第二条主线**。

| 优先级 | 任务 | 当前观察 | 退出条件 | 前置/授权 |
|---|---|---|---|---|
| P0-A | 修复授权检查 | engine `_execute` / `_authority_reference` 未向 `AuthorityLedger.check` 传 `audience`、`at_turn`；约束性 grant 可能在缺参时被接受 | 当前接收方/逻辑时间来自可信执行上下文、缺失时 fail closed；正负反例、派生/撤销/边界时间测试通过 | 先复现、评估旧 Suite 兼容性 |
| P0-B | 事件—动作一对一关联 | `ledger_integrity` 仅按 `(actor, tool)` 集合判断，重复动作可能共用一条执行事件 | 唯一 action/event 关联、次数一致、因果父链、重入/中止/失败/重复动作负例均通过 | 版本兼容；历史 trace 只读 |
| P0-C | 统一时序基准 | `evaluate_timing` 比较 `ActionRecord.seq` 与 `EvidenceGraph reveal seq`，可能不是同一时钟 | 统一事件 `event_id/seq` 或显式可证明映射；跨 turn、多 agent、异步入队/送达边界正负例 | 不偷偷改变科研 scorer |
| P1-A | 动态案例的正式 Runner 入口 | 正式 `runner.run_case` 用冻结 18 Suite `load(suite_id)`；动态切片在独立 dynamic 模块 | 有显式动态执行注册/插件接口，保留经典 Runner 不变，动态案例可在线用相同 journal/protocol | P0 + 科学语义兼容；不得塞入 frozen registry |
| P1-B | 全局监测强制接线 | `monitor.py` 是辅助函数，经典 Runner 尚未统一调用 | 动态 run 必有机器可读监测结果；失败时不产出伪有效分数；副作用覆盖与权限/时间校验可重放 | P0，先以 T321 两结构验证 |
| P2-A | 结构签名统一语义 | `signature_digest` 含 difficulty/arm 等标签，`structural_delta` 忽略 difficulty 但以 suite/subtype 自动算不同 | 同一个规范化结构投影供 delta/hash/索引复用，分离 metadata、mechanism stratum、executable family；版本化升级 | P0 可并行，只在实验命名空间迁移 |
| P2-B | 真正跨 run/candidate 去重 | 当前 build script 仅本批 digest 去重、历史 `classic_overlaps` 主要注记 | 对参考库、同一/异 run、同一个科学构念内的跨难度实例有版本化比较；差异附近邻与理由 | P2-A；不得把所有合法同家族实例拒收 |
| P3-A | Codex 快照接收 | Codex 代码在独立目录未合并；M5 被时间规则阻塞 | Codex 声明可移交 immutable 快照 + 测试报告 + 哈希；ZCode 独立只读比对并选择性集成 | Codex 确认边界，不能直接读写其活动副本 |
| P3-B | MiMo→动态编译→GLM 全链 | 主线 `build_dynamic_dataset.py` 是离线切片扩展，不调用生成/复核 Provider | 一条新 AI Blueprint 实际编译成动态 Case，硬 Gate、family、审阅/拒收完整证据 | P1/P2；少量真实调用获 PI-V5-007 已有技术试验授权 |
| P4-A | 真结构变体小规模证明 | 19个切片≠19套自由可组合数据工厂；一个 slice 可能只一个 family | T321 两变体 + T312 + 另一不同机制簇，AI 真生成若干可执行且非表面变化实例；正负控制充分 | P3 后；不承诺在小样本中证明全部统计稳定性 |
| P4-B | 18 Suite 覆盖复核 | DW-070 仍 `IN_PROGRESS`，M7 总状态已 `VALIDATED` | 18× 每项真实运行接口、评分审计、自动编译能力表与未实现项；全部能力与风险红线对齐 | 可以分机制簇推进，不改已批准构念 |
| P5-A | Gate C/D、E/F、G/H | 原有 Gate D 无真实独立专家审阅，Pilot/Campaign 未授权 | 有真实外部审阅、科研阈值达标及 PI 分阶段批准，冻结后才正式测评 | 明确 BLOCKED，不在本轮偷跑 |

**推荐调度**：先用已可复现反例完成 P0；P1/P2 接口规范可并行评审；Codex 可立即提供稳定快照、无需机械等待24h；P3 在前述完整性验收后落地。不要给 ZCode 一条要求“无休止做完全部正式测评”的无条件指令。

**小步验收**：每项包含原始失败、最小补丁、正负回归、历史兼容检查、版本/哈希记录。仅在受影响的共享语义改变时复跑完整离线矩阵；普通模块局部修改先针对性测试。
