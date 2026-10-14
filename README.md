# IoA-Bench Codex Specification Pack

This specification pack governs implementation of a **model-centric IoA endogenous-safety benchmark**.

The current v5 supplied-case system supports all18 classic suites and19 registered dynamic structures. See [v5 system commands and acceptance](docs/v5/V5_SYSTEM_HANDOFF_20261012.md) for batch execution, safe resume, replay, reports and blinded review export. System engineering is validated; the data-factory stage and formal research acceptance remain separate.

中文工作区入口：[WORKSPACE.md](WORKSPACE.md)。当前状态、最新测评证据、数据入口与历史资料位置集中列在这里；全部目录、文件分类和整理记录见 [整个工作区索引](docs/WORKSPACE_FULL_INDEX_20261013.md)。历史交付包及旧会话已集中到 [archive/](archive/README.md)，旧位置映射和恢复工具一并保留。

2026-10-14数据生成流程外部审阅：[当前交接说明与审阅请求](docs/HANDOFF_20261014_CHATGPT.md)。包内包含源码、测试、当前质量问题及真实生成样例；工程检查不等于批量数据质量接受。

## Canonical objective

Build a controlled small-scale Internet-of-Agents environment and use it to measure how a tested model behaves under 18 IoA risk mechanisms. The IoA scaffold is a controlled experimental environment; the scored object is the model configuration.

## Read order

1. `AGENTS.md`
2. `docs/01_SYSTEM_ARCHITECTURE.md`
3. `docs/02_DATA_AND_EVENT_MODEL.md`
4. `docs/03_SCENARIO_AND_INJECTION_SPEC.md`
5. `docs/04_EVALUATION_18_TESTS.md`
6. `docs/15_MODEL_RUNTIME_AND_AIHUBMIX.md`
7. `docs/09_DATA_GENERATION_AND_DATASET_LIFECYCLE.md`
8. `docs/10_TEST_DATA_RECIPES_18_SUITES.md`
9. `docs/11_EXPERIMENT_EXECUTION_AND_BATCH_SCHEDULING.md`
10. `docs/12_STATISTICS_VALIDITY_AND_REPORTING.md`
11. `docs/17_DASHBOARD_REPLAY_AND_REPORTING.md`
12. `docs/06_SECURITY_OBSERVABILITY_AND_OPERATIONS.md`
13. `docs/08_PYTHON_API_CONTRACT.md`
14. `docs/05_IMPLEMENTATION_ROADMAP_AND_ACCEPTANCE.md`
15. `docs/13_RELEASE_REPRODUCIBILITY_AND_BENCHMARK_GOVERNANCE.md`
16. `docs/14_CODEX_AUTONOMOUS_EXECUTION_PLAYBOOK.md`
17. `docs/16_REFERENCE_IOA_WORLDS_AND_SANDBOX.md`
18. `docs/07_REFERENCE_BASELINE.md`
19. `docs/18_DESIGN_DECISIONS_REGISTER.md`
20. `docs/19_TESTING_CI_AND_QUALITY_GATES.md`

## Machine-readable contracts

- `contracts/schema/scenario.schema.json`
- `contracts/schema/dataset.schema.json`
- `contracts/schema/run_manifest.schema.json`
- `contracts/schema/world.schema.json`
- `contracts/schema/model_profile.schema.json`
- `contracts/ddl/sqlite/*.sql` — normative local v1 storage schema
- `contracts/ddl/postgresql/*` and `contracts/ddl/clickhouse/*` — optional scale-out profiles
- `contracts/python/*.pyi` — port/interface contracts
- `config/benchmark.default.yaml`
- `config/model_pool.example.yaml`
- `state/PROJECT_STATE.yaml`
- `state/WORK_QUEUE.yaml`
- `state/WORK_QUEUE_VALIDATION.json`
- `contracts/schema/construct.schema.json` and `contracts/constructs/T*.json` (versioned legacy construct obligations; current v5's 18 suite implementations live in `src/ioabench/v5/suites/`)

## Autonomous implementation queue

`state/WORK_QUEUE.yaml` contains the implementation and historical construct-remediation DAG. The current v5 execution queue is `state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml`; resume from `state/PROJECT_STATE.yaml`, `docs/v5/V5_PROGRESS.md` and the latest checkpoint before selecting work. All18 current v5 suites have execution, scoring and retained engineering evidence; independent review, broad data calibration and formal acceptance remain separate. Codex MUST follow dependency readiness rather than skipping ahead.

The earlier 235-task queue, T311-only construct slice and r5/r6 discussion are historical context, described in `docs/T311_CONSTRUCT_VERTICAL_SLICE_ACCEPTANCE.md`; they are not the current v5 implementation status. Frozen historical versions still control their own evidence.

Coverage: M0 core/local storage; M1 AIHubMix/model runtime; M2 Reference IoA/Sandbox; M3 shared data generation; M4 T311 vertical slice; M5 T312–T323; M6 T331–T343; M7 T351–T353; M8 T361–T363 simulation; M9 all 18 formal frozen datasets; M10 full `deepseek-v4.1-flash` benchmark, replay, dashboard, report and v1 Definition-of-Done audit.

## Conflict precedence

When two artifacts conflict, use this order:

1. `AGENTS.md`
2. machine-readable contracts (`contracts/schema`, local-v1 SQLite DDL)
3. Python API contracts (`contracts/python`)
4. numbered normative docs
5. examples/templates

A frozen dataset/scenario/scorer version always controls the historical run that references it; later specs do not retroactively alter old results.
