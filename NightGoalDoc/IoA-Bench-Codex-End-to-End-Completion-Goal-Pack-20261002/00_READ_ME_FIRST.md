# IoA-Bench Codex End-to-End Completion Goal Pack

这是一个**最终结果导向**的 Goal Pack，不是 bug checklist，也不是某一轮 corrective audit 的任务清单。

## 为什么这样设计

Codex Goal 适合“终点清楚、路径会随着探索而变化”的长任务。这个项目当前正属于这种情况：18 项 Benchmark 的最终完成状态是明确的，但真正到达终点所需的修复、验证、版本化、运行与收口动作要由当前磁盘证据决定。

因此本包刻意只固定三类东西：

1. **最终要达到什么状态**；
2. **哪些科研边界不能为了赶进度而破坏**；
3. **什么证据才算真正完成**。

普通实现细节、局部 bug、脚本接线、Manifest、hash、测试、路径、版本、报告等问题，不写进主 Goal 的逐项 checklist。Codex 应在追求最终目标的过程中自行发现和解决。

## 使用方式

建议把本目录放入：

`D:\Project\ioa_codex_spec\NightGoalDoc\IoA-Bench-Codex-End-to-End-Completion-Goal-Pack-20261002`

然后在新的 Codex thread 中：

1. 先让 Codex 阅读工作区根目录 `AGENTS.md`；
2. 阅读本目录 `00_READ_ME_FIRST.md` 与需要的配套文档；
3. 把 `GOAL_DIRECT_PASTE.txt` 内容作为 `/goal`；
4. 让它从**当前磁盘**独立判断项目现状并持续推进。

不要在启动 Goal 后继续给它一串小修复任务，除非你想主动改变目标或科研边界。

## 本包文件

- `GOAL_DIRECT_PASTE.txt`：直接粘贴给 Codex 的 `/goal`
- `GOAL_TEXT.md`：Goal 正文
- `01_MISSION_AND_FINISH_LINE.md`：最终使命与高层生命周期
- `02_SCIENTIFIC_CONSTITUTION.md`：不能随意突破的科研边界
- `03_EVIDENCE_AND_COMPLETION_CONTRACT.md`：什么证据才算完成
- `04_AUTONOMY_AND_ITERATION_POLICY.md`：Codex 如何自主推进、避免陷入局部
- `05_PROJECT_EVIDENCE_MAP.md`：工作区材料的读取与证据优先级
- `06_USER_DECISION_BOUNDARIES.md`：什么情况才需要回来问用户
- `07_FINAL_DELIVERY_CONTRACT.md`：最终科研交付必须具备什么
- `08_STARTUP_HANDOFF.md`：新 thread 的启动方式
- `GOAL_CONTRACT.yaml`：结构化 Goal 契约
- `PACK_MANIFEST.json`：本包内容与 SHA-256
