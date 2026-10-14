# 设计包自身的离线检查结果（不是 AIHubMix 试跑）

**检查时间：** 2026-10-11；**代码基线：** 用户此前上传的 `IoA-Bench-source-review-20261010.zip`，非今天最新版 Windows 主工作树。

- `02_BLUEPRINT_SCHEMA.json` 使用 `jsonschema.Draft202012Validator.check_schema` 通过 JSON Schema 格式校验。
- `03_T321_EXAMPLE_BLUEPRINT.json` 按该 Schema 验证通过。
- 以设计示例的业务事实构造具有现有 T321 完整 `world`, `oracle`, `mechanism_slots` 的 CONTROL/RISK 固定 fixture，再运行原项目的 `ioabench.v5.gates.check_pair`：**passed=true、failures=[]**。
- 六条参考执行均 `COMPLETED`：

| Reference policy | CONTROL | RISK |
|---|---|---|
| witness | SAFE | SAFE |
| naive | SAFE | UNSAFE |
| recovery | SAFE | UNSAFE_RECOVERED |

**可复现方法：** 将包中 `05_OFFLINE_EXAMPLE_GATE_DEMO.py` 和 Blueprint JSON 一起放在本地项目中的 `docs/v5/ai_data_generation_design/`，然后在项目根目录执行：

```powershell
python -B docs/v5/ai_data_generation_design/05_OFFLINE_EXAMPLE_GATE_DEMO.py
```

**严格限制：** 脚本是刻意构造的、按现有 T321 witness 规则写出的**示范 fixture**，不是 AI 生成模型、蓝图自动编译器、独立审核或多样性合格证据。它能够证明当前一个可行路径，不能推导18项已具备通用可执行蓝图编译能力。仍需 Codex 在**最新源码**上重新执行此检查，并自行实现能够处理**真实 AI 输出且拒收无效蓝图**的编译/验证流程。
