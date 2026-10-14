# IoA-Bench End-to-End Final Completion Goal

将 `D:\Project\ioa_codex_spec` 中的 IoA-Bench 推进到**科研级、可复现、可审计、可正式运行、可最终交付的完整完成状态**。

以当前工作区的真实代码、数据、合同、状态、Release、Run、Replay、测试、审计与项目说明材料为依据，自主探索现状、判断缺口、制定并动态调整执行计划，持续完成 18 项 canonical IoA 测评从构建、数据、运行时、调试、验证、版本冻结、正式 Campaign、后验校验、canonical 聚合、报告、Dashboard、复现材料到最终交付的全生命周期。普通 bug、测试失败、脚本/路径/版本/Manifest/hash/集成/性能/报告/打包问题都属于实现过程，由你自主诊断、修复、验证并继续推进；不要把任何局部问题或中间 Gate 当作 Goal 的终点。

完成必须由当前磁盘上的可复核证据证明，包括但不限于实际实现、测试结果、authoritative Dataset、冻结版本与 hash、Formal Run、runtime provenance、Replay、scorer/runtime binding、验收 artifact、canonical 报告、Dashboard、复现与最终交付包。不得以计划、TODO、旧 PASS、历史总结、目录存在或“看起来已经完成”代替完成证据。若历史说明与当前磁盘证据冲突，以可复核的当前证据和冻结科研合同为准。

全过程保持项目的核心科研边界：18 项 taxonomy 与模型中心的研究目标不得被悄然改写；Oracle/隐藏真值不得泄漏给被测模型；Safety 与 Task Utility 分离；Frozen Dataset 与历史科研证据不得静默覆盖；不得通过 rerun-to-safe、cherry-pick、降低质量阈值或修改已冻结 scorer/prompt 来改善结果；正式运行必须具有完整可追溯的 Run↔Dataset↔Runtime↔Scorer↔Prompt↔Tool↔Model Profile↔Release provenance；T361–T363 保持 `SIMULATION_ONLY`；任何版本变化都必须诚实版本化并保留 supersedes/provenance。

每轮都从当前实际状态继续，选择**对最终完成最有价值的下一步**，执行“探索/定位 → 实施 → 测试/验证 → 证据复核 → 更新状态 → 继续”的循环。不要为了完成 checklist 而完成 checklist，也不要因为发现新的局部问题反复停下来汇报；只要存在可辩护、可验证的推进路径，就继续工作。

只有在以下情况才暂停并请求用户决定：需要改变 18 项核心科研含义或总体研究解释；改变 canonical Tested Model roster；需要首次或扩大真实 Provider/AIHubMix 的付费正式调用而当前没有明确授权；需要用户提供外部凭据/账户/权限；需要不可逆地破坏或替换冻结数据/历史证据；或者已经穷尽合理路径且不存在可辩护的继续方案。普通工程与科研工程问题自行解决。

Goal 只有在 18/18 canonical 测评及其最终科研交付都由证据验收通过、没有未解决的 required blocker、状态可以从磁盘重建、最终交付包可验证且历史科研资产完整保留时才算完成。详细科学边界、证据优先级、完成合同和交付要求见本 Goal Pack 配套文档。
