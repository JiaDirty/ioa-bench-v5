# 2026-10-18项目检查与工作区整理

当前唯一开发目录为`D:\Project\ioa_codex_spec`。18项测评及19个注册动态结构已有实现；数据生成流程仍需增强实际结构多样性、验证独审质量、全历史去重和实测难度。最新评分修复的真实模型复测、独立审核及正式数据冻结/实验尚未完成。判断让渡、讨论扭曲、能动性弱化仍为`SIMULATION_ONLY`。

运行源码hash与2026-10-14一致：`1416449d4ae6fda00d3f487e9d32115f553baf0c2002f5bb41591d2a43787e7d`。本轮只做工作区检查、目录归并、文档和状态更新，不改运行代码、评分、测试或科研定义。2026-10-18实际重跑852项v5测试与4项打包测试，共856项通过，用时98.29秒，失败/错误/跳过均0；禁止HTTP和外网，实际尝试0，仅允许Windows本地进程通信，测试临时目录已清除。完整保护检查见[验证记录](../artifacts/workspace_maintenance/20261018-r1/VERIFICATION.json)，测试结果见[测试XML](../artifacts/workspace_maintenance/20261018-r1/PYTEST.xml)。

## 三个目录的处理

| 原目录 | 检查结论 | 处理与当前位置 |
|---|---|---|
| `D:\Project\ioa_codex_spec_ai_generation_probe` | 993文件，约5.94 MB；旧生成原型和交付快照有参考价值；多数公共源码已有主线版本，不能以旧版覆盖当前代码 | 整体迁入[主项目历史归档](../archive/external_workspaces/20261018/ioa_codex_spec_ai_generation_probe/)，文件逐一哈希核对，隔离标记保留 |
| `D:\Project\ioabench_spec` | 11个早期残片，10个与主项目相同；责任链断裂生成器是被当前实现扩展的旧版 | 保留恢复ZIP后删除原目录 |
| `D:\Project\ioabench` | 2个早期残片，与主项目相同，没有独立运行能力 | 保留恢复ZIP后删除原目录 |

两个残片目录的恢复包为[removed-code-fragments-20261018.zip](../archive/removed-code-fragments-20261018.zip)。旧原型是历史参考，未自动合并进`src/`、`scripts/`、`tests/`或配置。当前项目状态中的原型交付快照位置已更新；历史报告中的原绝对路径保留原样，通过[PLAN.json](../artifacts/workspace_maintenance/20261018-r1/PLAN.json)查找新位置。

## 主工作区清理

清点整理前主工作区约7.55 GB。已完成测试留下的5个`pytest-*`临时工作目录共4394文件、182907865字节，压缩为17209309字节，归档在[测试临时文件恢复包](../artifacts/workspace_maintenance/20261018-r1/test-temporary-files.zip)。原始测试XML、日志、导出源码包、Git工作副本、候选数据、真实模型轨迹、冻结材料及原有审计证据均保留。可恢复材料留在本机，不是对外分享包。

历史实验中相同内容的文件可能有不同来源和证据意义，未按字节重复批量删除。`.env`未迁移、打包或展示；主目录仍无Git元数据，本机Git工作副本在`exports/github-private-20261014/repository/`。此次整理未推送GitHub、调用模型或改变科研接受状态。

## 验证与恢复

整理前的文件清单和SHA-256保存在[INVENTORY_BEFORE.json](../artifacts/workspace_maintenance/20261018-r1/INVENTORY_BEFORE.json)，路径映射/删除范围/归档哈希在[PLAN.json](../artifacts/workspace_maintenance/20261018-r1/PLAN.json)。正式数据、原始实验轨迹和其他未声明修改的旧文件必须通过逐文件保护校验。

从主工作区执行：

```powershell
python -B artifacts/workspace_maintenance/20261018-r1/restore.py
```

默认只检查恢复材料和目标冲突，加`--apply`才把三个目录及测试临时目录恢复到原位置，并恢复本轮修改前的入口文档和项目状态。如果后续又修改了相关文件，恢复工具会拒绝覆盖。

本轮回归只验证现有代码与已覆盖案例，不会证明任意新数据都科学可靠；没有新增在线测评或正式数据验收。
