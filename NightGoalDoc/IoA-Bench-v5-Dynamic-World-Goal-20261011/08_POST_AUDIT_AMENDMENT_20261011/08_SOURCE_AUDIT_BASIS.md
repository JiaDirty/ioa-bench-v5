# 文件依据、时间点与审计局限

## 已核实输入

- `IoA-Bench-source-20261011.zip`：ZIP 内 1,098 个文件、前缀 `IoA-Bench-v5-workspace/`。提供的 `PACKAGE_VERIFICATION(2).json` 记录 ZIP SHA-256 `947c0bcb3919a30d531f04e9cdd36f99213de2ea589c5fa7f429bb9a786f2a81`（请在 Windows 侧复核）。
- `2026-10-11_1305_IoA-Bench v5 长期目标整合与 M0-M10 建设.md/json`：739条 ZCode 消息，最后更新于 2026-10-11 17:34 左右，原会话报告 M0–M4、M6、M7 已完成，M5/M8 后续/M9/M10 未完成。
- 源码包含：`src/ioabench/v5/core/{authority,engine,events,monitor,evidence,clock}.py`、`src/ioabench/v5/dynamic/{signature,gates,t321_slice,t321_slice_b,t312_slice,...}.py`、`src/ioabench/v5/runner.py`、`scripts/v5/build_dynamic_dataset.py`、`state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml`。
- 原设计包 `NightGoalDoc/IoA-Bench-v5-Dynamic-World-Goal-20261011/00–07`；本修订只增加验收条款，不改变总任务和科研构念。

## 限制与表达纪律

源码包明确排除 `.env`、约3.9GB历史 data/、多数旧 artifacts，因此其独立复现覆盖不等于 Windows 完整工作区。本修订不会声称亲自验证今天之后或未随包上传的独立 Codex 最新结果。负例记录为“源码可见的潜在错误和上一轮已观察到的复现”；修复必须在最新源码和实际运行入口重新验证。

不把没有观察到的事件宣称为现实世界真相；没有 Provider 原始响应不声称已发生新的真实 MiMo/GLM 调用；不能将 ZCode 测试 PASS 视作独立的科学效度认证。

## 当前 5 个代码定位线索

1. `core/engine.py::_execute`, `::_authority_reference` 调 `AuthorityLedger.check` 未传 `audience/at_turn`；`core/authority.py::_chain_valid` 和 `check` 允许空值跳过约束。
2. `core/monitor.py::ledger_integrity` 将 tool events 压为 `(actor,action)` set；`evaluate_timing` 将动作与证据 seq 直接比大小。
3. `dynamic/signature.py::signature, structural_delta, signature_digest` 的 metadata/比较/hash 定义不一致。
4. `scripts/v5/build_dynamic_dataset.py` 为 slice.generate 驱动，本批 digest 去重，历史 overlap 主要注记，没有 Provider 生成/审核。
5. `runner.py::run_case` 通过原 frozen suite registry 加载 `suite_id`，不支持 `T321-DYNA` 等动态 ID 直接进入统一测量管线。
