# IoA-Bench 工作区入口

更新：2026-10-28。项目目标仍是完整的18项IOA测评。当前重点是补齐树状业务生成、验证真实数据质量和多样性，再扩量、校准、冻结并运行完整测评。

## 当前进度

- 18项已有基础原型；12项有可执行业务树，其中11项通过共享入口工程检查，共23个套件与行业组合。
- 药品补货、支付结算、物流交接三类业务可执行；物流目前只接跨系统级联扩散。代表资格漂移使用只读结算资料，不增加付款权限。
- 最新R22原始源码检查有2295项v5+m1测试、8组授权链结构、48条严格回放通过。程序测试、脚本回放、真实模型生成和正式合格数据分别统计。
- R19真实生成4对、8条研发案例通过两轮研发审核；R20规范漂移样例执行通过，但审核连接中断而隔离。R22没有新增模型调用或正式数据。
- 结构暴露、行为推断、生态错误共识、谣言扩散、判断让渡、能动性弱化六项待接业务树。审核可靠性、难度校准、正式冻结与18项完整交付尚未完成。

## 从这里开始

| 要做什么 | 入口 |
|---|---|
| 看当前状态、继续工作 | [项目状态](state/PROJECT_STATE.yaml)、[工作队列](state/WORK_QUEUE.yaml)、[AGENTS.md](AGENTS.md) |
| 看18项逐项进度 | [测评与业务接入表](docs/v5/SUITE_BUSINESS_MATRIX_20261026.md) |
| 看行动顺序 | [整体交付计划](docs/v5/IOA_DELIVERY_ACTION_PLAN_20261026.md) |
| 准备汇报 | [当前汇报口径](docs/v5/REPORT_BRIEF_AND_PRIORITIES_20261027.md)、[展示案例说明](docs/v5/EXAMPLES_FOR_REPORT_20261027.md) |
| 查看本次同步及验收范围 | [工作区整理与GitHub同步](docs/WORKSPACE_STATUS_20261028.md) |
| 查看R22可公开检查结果 | [验收摘要](docs/v5/checkpoints/20261028-r22/FINAL_VERIFICATION.json)、[程序测试记录](docs/v5/checkpoints/20261028-r22/REGRESSION.xml) |
| 运行、续跑、评分和回放 | [系统使用说明](docs/v5/V5_SYSTEM_HANDOFF_20261012.md) |
| 查看完整旧入口与历史检查点 | [整理前工作区记录](docs/archive/WORKSPACE_HISTORY_20261028.md) |

## 文件位置与同步范围

`src/`为运行代码，`scripts/`为入口，`tests/`为测试，`contracts/`和`config/`为规则与配置，`state/`为项目状态，`docs/`为使用和设计说明。业务素材放在`prompts/`、`roles/`、`worlds/`、`scenarios/`和`templates/`。

当前GitHub仓库为公开的[JiaDirty/ioa-bench-v5](https://github.com/JiaDirty/ioa-bench-v5)。本次同步源码、测试、文档及脱敏检查摘要。仓库中已有历史数据与发布记录保留原样；新增实验数据、完整模型记录和本地恢复材料不随源码上传。

本地`data/`、`artifacts/`、`release/`、`exports/`、`archive/`保留历史数据、证据与交付包；`scratch/`保留历史辅助脚本。`.env`、本机工具记忆和无关专利材料留在本地。公开源码仓库不等于完整历史回放包；依赖未公开实验资料的测试需要对应本地文件。

## 本地命令

```powershell
python -B scripts/v5/evaluate.py --help
python -B scripts/v5/tree_factory_trial.py --help
python -B -m pytest -p no:cacheprovider tests/v5 tests/m1 -q
```

全量测试需要项目对应的历史案例与证据资料。运行模型前遵循当前实验决定和调用范围；凭据从环境或本机`.env`加载。T361–T363继续标为`SIMULATION_ONLY`。
