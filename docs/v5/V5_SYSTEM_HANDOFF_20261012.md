# v5 测评系统交付说明 — 2026-10-12

按最新 PI-V5-012，当前阶段交付18项测评系统的本地工程验收，暂停新的 AIHubMix 调用和数据生成。系统能接收已实现的18项经典案例和19个注册动态结构，完成代理多步工作、行为记录、判分、保存、续跑、回放和报告。这个范围不等于任意新蓝图都已能编译，也不等于科研数据或正式实验已经完成。

## 日常使用

从 `D:\Project\ioa_codex_spec` 执行。输入是 Case JSONL，包含完整正常/风险配对；复用现有 Case 字段、隐藏 Oracle 和适配器，不另建数据格式。

```powershell
# 不调用API：验证环境、工具、判分和报告的完整接线
python -B scripts/v5/evaluate.py run --cases <案例文件.jsonl> --run-id <新运行ID> --suite all --mode reference

# 真实模型工程验证：固定DeepSeek、参数和本次精确身份
python -B scripts/v5/evaluate.py run --cases <案例文件.jsonl> --run-id <新运行ID> --suite all --mode smoke

# 原运行续跑：输入、模型、身份列表、参数和源码必须全部相同
python -B scripts/v5/evaluate.py run --cases <原案例文件.jsonl> --run-id <原运行ID> --suite all --mode smoke --resume

# 用保存的响应回放；不调用API
python -B scripts/v5/evaluate.py replay --run-id <原运行ID>

# 新建一版报告，保留以前版本
python -B scripts/v5/evaluate.py report --run-id <原运行ID>
```

`--suite T311 T352` 按测评项目选择经典和对应动态结构，也可指定精确动态结构。默认 `reference` 是脚本参考策略；`smoke` 才是被测模型自行选择工具、核验、委托、拒绝或恢复。参考策略只验证系统；不会强加给真实模型。代理的自由行动受角色权限、可见信息和案例预算限制。

运行目录：`artifacts/v5/evaluations/<运行ID>/`。其中 `manifest.json` 固定源码/模型/参数/案例哈希，`cases.jsonl` 保存输入，`checkpoint.json` 保存进度和报告路径，`results*.jsonl` 追加结果，`reports/report-N/` 保存 JSON、CSV 和中文 HTML。原始模型交互按次保存在 `data/runs/<运行ID>/attempts/`，不覆盖旧尝试。

## 已验证的处理方式

- 完成的案例续跑时直接跳过。没有响应的基础设施故障有界重试；产生过响应的中断案例保留原证据，标记失效，不重新测到通过。
- 单题工程异常保留诊断，后续题目继续。断电造成的 JSONL 不完整尾行保留原字节，结果写入新段；中间完整行损坏明确拒绝。
- 真实被测模型始终固定为 `deepseek-v4.1-flash`，不会转用其他模型。权威网关身份逐响应精确校验；正文仅接受启动前固定的目录别名与探针返回的精确快照名，不按前缀猜测身份。
- 回放按原响应顺序检查完整请求及角色，重新执行工具，比较行动、事件、终态、暴露、判分和监测。重复请求也不会合并。源码变化时必须使用原版本；r1 源码已归档，隔离恢复后验证了原真实轨迹。
- 安全、任务完成和恢复分别报告；失败、未暴露、无行动机会、监测不合格和评分弃权不计作安全成功。没有18项综合总分。真人相关三项继续标记 `SIMULATION_ONLY`。

## 一条命令验收系统

```powershell
python -B scripts/v5/verify_system.py --run-id <新的验收ID>
```

该命令复用已有场景构造工程样本：18项经典 + 19动态结构 × 正常/风险两臂 = 74条。分别跑谨慎策略和易受影响策略，共148次；逐例校验完成状态、计分资格、实际暴露、决策机会、事先声明的参考评分、事件完整性、SIMULATION_ONLY身份，验证续跑不重执行与148次严格回放。不调用API，不把工程样本计入合格数据产量。当前结果在 `artifacts/v5/system_acceptance/system-acceptance-20261013-final-r9/acceptance.json`。

本轮完整回归：`python -B -m pytest tests/v5 tests/m1 -q`，796通过，失败/错误/跳过均0。动态运行失败资格字段、重复终态回放拒绝、T312跨进程生成顺序、T332跨 hash seed 评分证据顺序、历史基线家族比较、家族注册类型注解和候选接入各有回归测试；此前的双代理隔离测试仍通过。目录内 `SYSTEM_STATUS.json`、`tests.xml`、两个源码ZIP分别固定验收、回归报告、运行源码与测试源码；逐文件哈希及CRC通过。

## 人工审阅软件

`build_review_package.py --cases <案例文件>` 现在支持经典和动态输入。按18项分层采样，导出盲材料、空白标注表、标注规范、证据哈希与裁决流程；样本不足明确报告。只把 `reviewer_materials.zip` 交给评审者，研究方保留 `sealed_key.jsonl`。

`agreement.py` 拒绝未知/空标签、重复提交和空审核人。AI标签不进入真人验收统计，有分歧的项目保留 `AMBIGUOUS`，由真人裁决。工程演示包：`artifacts/v5/review_package/system-20261012-engineering-r1/`；它不是完整 Gate D 包，也没有真人标签。

## 后续工作边界

本轮系统工程验收已完成；AIHubMix调用、在线/批量数据生成及候选试跑按最新用户指示暂停，离线历史基线预检已单独完成并记录在 `V5_DATA_FACTORY_HANDOFF_20261012.md`。不在此追认为正式数据完成。未来新增结构若缺运行能力，应登记具体缺口并补适配，不能把现有19个结构宣称为任意世界能力。

T331任务效用与T333评分弃权的科研审计材料已准备，实际判断仍在PI/专家路径；人审、预注册冻结、确认Pilot和正式Campaign按既有门槛执行。当前命令的 `ENGINEERING_REFERENCE` / `ENGINEERING_SMOKE` 报告不替代正式科研流程。原自动续行任务本轮查不到；未新建自动任务，也不声称应用关闭或断电后会继续运行。
