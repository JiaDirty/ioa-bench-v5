# Independent Reverification Protocol

Codex 不应仅把 ZCode 的审计结论复制进项目。

需要对决定性证据做一次独立、只读复核。

## 必查项

### A. 18 Dataset 三方绑定
每 suite：
- Dataset Manifest content hash；
- Formal Run Manifest dataset hash；
- Benchmark Release dataset hash；
必须一致。

### B. 18 Formal Run 身份
确认：
- exact Run ID；
- Dataset version；
- tested model ID；
- terminal 90/90；
- Replay 是否存在且可解析。

### C. Source compatibility
对每个 Run：
- 取 run-time source hash；
- 比较目标 Release source hash；
- hash 相同 → strict binding；
- hash 不同 → 必须做 semantic impact analysis。

不能用“hash 不同”直接判失败。

### D. 语义影响分类
只有以下路径的差异才可能影响 canonical 等价：

- suite runtime；
- scorer；
- prompt builder；
- Tool Schema；
- model adapter；
- invalid-output semantics；
- retry semantics；
- dataset loader；
- Oracle/SUT separation；
- Synthetic Human causality。

README、state、report、logging、packaging、其它 suite 的代码变化不能自动使本 suite 失效。

### E. Scorer
确认实际正式 Run 使用的评分入口，不得误用同名 wrapper/旧模块。

### F. Prompt / Tools
从 Replay / ModelRequest 重建实际 runtime prompt 与 tools 内容，并计算 hash。
不能只看版本号。

### G. T311
独立复核：
- max_tokens 实际是否触顶；
- finish_reason；
- completion token 最大值；
- concurrency 是否进入 case 内状态；
- contract 标签是否仅元数据。

### H. T361–T363
确认：
- Synthetic Human exact model；
- persona assignment；
- context isolation；
- 输出是否进入世界态和 scorer 因果链；
- `SIMULATION_ONLY` 传播链。

## 输出

生成：
- `artifacts/gates/CODEX_INDEPENDENT_REVERIFICATION.json`
- `artifacts/reports/codex_independent_reverification.md`

结论只能：
- CONFIRMED
- PARTIALLY_CONFIRMED
- CONTRADICTED
- UNKNOWN

有 UNKNOWN 时继续取证，不要直接 PASS。
