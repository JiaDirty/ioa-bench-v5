# IoA-Bench 工作区交接说明 — 2026-10-01

本包是当前工作区的整理快照，供继续开发和独立复核使用。它不是新 Benchmark Release，也不代表 v4 正式验收通过。本次只整理和打包，没有修复测评代码、运行测试集或调用模型服务。

## 当前状态

- 18 项都有生成与评分代码，并注册了场景适配和执行入口。已有历史运行、测试和验收材料；这些材料不能单独证明当前整套代码全部正确。
- 历史 v3.2 已按记录偏差的方式收口。旧结果继续作为历史证据，不能替代新的 v4 正式结果。
- `release/BENCHMARK_RELEASE_v4-corrective-20261001.json` 已冻结。
- v4 候选源码位于 `artifacts/scientific_closure_v4/corrective-candidate-v2/`；工作区 `src/` 与该候选版本必须区分。
- 18 份预冻结运行清单位于 `data/runs/_v4_manifests/`。
- 本次检查时没有 v4 正式运行目录；`provider_calls_allowed` 为 false。
- 判断让渡、讨论扭曲、能动性弱化测评继续标记 `SIMULATION_ONLY`，不能推断真实人类能动性。

本次重新核对的 v4 Release 文件 SHA-256：
`756194ab08c6aaad86fef973b51ffdf419b9a32898d530320fdcc2a2881b9987`

v4 候选源码树 SHA-256（按项目 `src/contracts/config` 算法）：
`2b72255bcb5d258322bb97c88714a443ae4bb4026092a3c4219d886d2083e6ff`

## 接手时应先处理的问题

以下是 2026-10-01 对当前源码的只读核对结果，本次打包没有修复这些问题。

1. 候选 `src/ioabench/cli.py` 创建运行清单时未向 `FullRunManifest.build()` 传入 `release`；`scripts/v4_validate_run.py` 检查的是 `_v4_manifests` 中的预冻结副本。需要把实际运行、实际使用的清单和后验验证接通。
2. `scripts/run_online_campaign.py` 沿用旧 `ONLINE_CAMPAIGN_STATE.json` 的完成标记，会跳过新运行；其历史目录存在即退出的条件也会阻止启动。新旧运行状态应隔离，历史目录仍须保留。
3. `scripts/v4_strict_binding_audit.py` 的输出缺少 `scripts/phase_c_campaign.py` 所需的 `base_release`、逐套 `evidence` 等字段，不能直接完成汇总。
4. 后验验证器需要核对真实尝试记录、重试顺序、案例集合、Replay 完整性及统计分母。仅检查目录数量、字段存在或同目录文件名不重复，不能证明严格执行语义。

因此，较早记录中的“全部离线工作完成、只差批准”不应作为当前就绪结论。`PROJECT_STATE.yaml` 中仍有历史里程碑、旧验收引用和旧套件完成状态；应结合版本、时间与原始证据阅读。

## 后续工作顺序

1. 修复已确认的运行与验收衔接问题，确认启动的是预期源码版本。
2. 复用已有合同和测试，逐项补齐风险暴露、模型可见信息、动作后果、评分、效用和边界情况的核验证据。
3. 在隔离目录验证重试、中断、恢复和证据保留；避免普通工作区测试覆盖历史 Gate。
4. 涉及冻结源码的修复创建新版本并重新冻结，不能原地修改已有候选快照或 Release。
5. 获得明确模型服务调用授权后，小规模真实试跑，再完成 18 项 × 90 案例的正式运行。
6. 逐套严格绑定验收，通过后生成报告、Dashboard 和科研交付包。

测评程序正确，不要求被测模型始终安全。模型的不安全行为和无效输出应如实记录，不能为了通过而重跑。

## 文件导航

| 内容 | 路径 |
|---|---|
| 科研边界和 18 项定义 | `AGENTS.md`、`contracts/constructs/` |
| 数据集及固定版本 | `data/datasets/DATASET_PACK_v4.yaml`、`data/datasets/` |
| 工作区源码与测试 | `src/`、`tests/`、`scripts/` |
| v4 冻结候选 | `artifacts/scientific_closure_v4/corrective-candidate-v2/` |
| 历史运行和原始结果 | `data/runs/`、`artifacts/runs/` |
| 审计与历史 Gate | `artifacts/scientific_closure_v3_2/`、`artifacts/scientific_closure_v4/`、`artifacts/gates/` |
| 进度与历史决策 | `state/`、`NightGoalDoc/`；其中历史指令不自动构成新的执行授权 |
| 本次整理证据 | `artifacts/workspace_maintenance/20261001-223139/` |

## 整理范围与恢复

- 将活动源码、脚本、测试的 81 个缓存目录移入本次维护目录的 `archived_caches/`，共 614 个文件、3,329,843 字节；不涉及历史快照内缓存。
- 将根目录 `tmp_baseline_lookup.py` 和 `scripts/_check_cli_release.py`、`scripts/_check_rt_manifest.py` 移入 `archived_diagnostics/`，保留原相对路径。
- 直接删除缓存被自动审批拦截，因此采用可恢复归档。没有把移动量当作释放磁盘空间。
- `cleanup-rollback.zip` 保存缓存、诊断脚本和修改前的两份状态文档；该备份只留在原工作区，不嵌入交接包。
- 恢复时按 `cleanup-plan.json` 中的原相对路径移回；如已有同名文件，先比较内容，不能盲目覆盖。状态文档的恢复只使用备份中的对应文件，并先保留后续修改。
- 19,606 个原受保护文件在整理前已逐文件核对无变化；整理后结果见 `maintenance-verification.json`。

## 压缩包范围和验证

压缩包保留当前源码、测试、文档、配置示例、冻结数据、历史运行、审计材料、Release 和候选源码快照。工作区中的旧压缩包保留原路径，新包不重复嵌套；索引及其 SHA-256 位于包内 `_snapshot/EXCLUDED.json`。

排除真实 `.env`、密钥容器、虚拟环境、依赖目录、缓存和 `exports/` 输出目录。需要模型服务时应自行设置凭据；包内不提供实际密钥。

包内 `_snapshot/FILES.json` 记录每个纳入文件的大小和 SHA-256。包外 `PACKAGE_VERIFICATION.json` 和 `.sha256` 记录整包校验结果。每个 ZIP 条目都读回验证 CRC，每个工作区文件都核对 SHA-256，并校验条目集合与清单一致。

复核现有包：

```powershell
python -B scripts/package_workspace_snapshot.py --verify <压缩包绝对路径>
```

某些历史完整性检查引用旧压缩包；这些原始 ZIP 不在新包内，因此脱离原工作区运行此类检查时，需要按排除索引取回它们。交接包校验通过不等于科学验收通过。
