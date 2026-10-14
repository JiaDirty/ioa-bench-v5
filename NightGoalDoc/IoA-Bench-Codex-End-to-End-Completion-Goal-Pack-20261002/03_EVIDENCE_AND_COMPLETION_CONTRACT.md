# Evidence & Completion Contract

## 核心原则

Codex 只有在**证据证明 Goal 达成**时才能收尾。

计划、TODO、旧总结、旧 PASS、文件夹存在、mtime、运行时长、模型自述都不是充分完成证据。

## Evidence hierarchy

遇到冲突时优先级大体如下：

1. 当前磁盘实际文件内容、可复算 hash、运行结果、Replay、Manifest；
2. Frozen scientific contracts / Release / authoritative Dataset manifests；
3. 可复现测试、验证器、独立重算与运行日志；
4. State / Queue / Checkpoint；
5. 历史审计报告和 handoff；
6. 旧 Goal、旧 TODO、对话总结。

低层叙述不能覆盖高层实证。

## Completion surfaces

最终完成至少应在这些 surface 上得到证据：

### Benchmark implementation
- 18/18 suite 的 runner/runtime/scorer/contract 有实际实现；
- 构造测评的 causal semantics 与 contracts 一致；
- 公共执行路径可以可靠调用真正的正式实现，而不是测试 fixture 或旧代码树。

### Dataset
- 18 套 authoritative Dataset 可定位；
- case 数量、版本、hash、manifest、validation 状态可核对；
- frozen data 未被无版本修改。

### Release
- 正式 Campaign 对应一个明确 frozen scientific release；
- Release 能确定 dataset/runtime/scorer/prompt/tool/model/scheduler 等科学解释；
- 真正执行的代码和运行 artifact 能证明绑定到该 Release。

### Formal Campaign
- 18 项都有符合当前 canonical 标准的 Formal Run；
- case 完整性、终态、异常、retry/resume、attempt provenance 可验证；
- 不能用历史不兼容结果补洞。

### Replay & scoring
- 需要的模型请求/响应、动作、状态与 scoring evidence 存在；
- scorer 版本和公式可定位；
- 输出可重放/复核到项目声明的程度。

### Post-run acceptance
- per-suite validation；
- binding / provenance audit；
- canonical-only aggregation；
- Safety 与 Utility 分离；
- synthetic-human / SIMULATION_ONLY 正确处理。

### Reporting & delivery
- final report；
- dashboard / machine-readable summary；
- reproducibility instructions；
- release/run manifests；
- inventory；
- checksum / CRC；
- secret scan；
- final delivery bundle。

## Required honesty

如果某一部分只能做到：

- CONFIRMED
- APPROXIMATE
- DOCUMENTED_DEVIATION
- BLOCKED
- UNKNOWN

应如实标注，不能把不确定性压平成 PASS。

最终 canonical acceptance 只能使用满足当前项目正式标准的 evidence。
