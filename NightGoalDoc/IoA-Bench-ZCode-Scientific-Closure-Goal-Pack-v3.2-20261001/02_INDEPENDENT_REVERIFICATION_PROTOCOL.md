# Independent Reverification Protocol

当前 ZCode 会话不能仅继承上一轮历史审计的结论。

需要从磁盘实际证据重新复核决定性结论。历史审计是“待验证输入”，不是最终真相。

## 必查项

### A. Dataset 三方绑定
对 18 suite 验证：Dataset Manifest content hash、Formal Run Manifest dataset hash、Benchmark Release dataset hash，必须 18/18 一致。

### B. Formal Run 身份
对 18 suite 确认 exact Run ID、Dataset version、tested model ID、90/90 terminal、Replay 可解析，且不是 mock/exploratory Run。

### C. Source compatibility
取每个 Run 的 run-time source hash 与目标 Release source hash。hash 相同只能作为 strict-binding 证据之一；hash 不同时必须做 semantic impact analysis，不能直接判失败。

### D. 语义影响路径
重点检查差异是否进入 suite runtime、scorer、prompt builder、Tool Schema、model adapter、invalid-output semantics、retry semantics、dataset loader、Oracle/SUT separation、Synthetic Human causality。

README、state、report、logging、packaging、其它 suite 的代码变化不能自动使当前 suite 失效。

### E. Scorer
确认正式 Run 真正使用的评分入口，不能误用 wrapper、旧模块或同名但非运行路径的函数。

### F. Runtime Prompt / Tools
从 Replay / ModelRequest 重建实际 system prompt、role prompt、task/user prompt、tool definitions，并计算内容 hash。不能只比较 version 字符串。

### G. T311
独立复核 max_tokens 是否触顶、finish_reason、最大 completion tokens、concurrency 是否进入 case 内科研状态、contract label 是否仅元数据。

### H. T361–T363
确认 Synthetic Human exact model、5 persona 覆盖、deterministic assignment、tested model / synthetic-human context isolation、SH 输出是否进入世界态和 scorer 因果链，以及 SIMULATION_ONLY 的传播链。

## 输出

生成平台中性的：

- `artifacts/gates/INDEPENDENT_REVERIFICATION_V3_2.json`
- `artifacts/reports/independent_reverification_v3_2.md`

结论只能是：

- CONFIRMED
- PARTIALLY_CONFIRMED
- CONTRADICTED
- UNKNOWN

决定性 UNKNOWN 不允许直接 PASS；应继续取证。只有现有证据确实无法解决且必须由用户决定时，才暂停。
