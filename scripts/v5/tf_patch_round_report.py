from pathlib import Path

p = Path('artifacts/v5/tree_factory/tf-20261024-r1/ROUND_REPORT.md')
t = p.read_text(encoding='utf-8')
t = t.replace('（_tmp_offline_treat/_tmp_offline_audit 演示',
              '（scratch/_tmp_offline_treat 与 scratch/_tmp_offline_audit 演示')
addendum = '''

---

## 2026-10-24 在线续篇（网关恢复后的 v1.2b/v1.2c 轮，本节为最新状态）

**传输根因与修复**：三条 REQUEST_UNRESOLVED 均为 AIHubMix 对非流式连接约 80-100 秒静默的硬切（STOP_RESOLUTION 3-6）。修复=适配器新增 SSE 流式与分块聚合；随后 16384 输出预算被思考耗尽（29 笔 finish=length）→ 预算回 65536 且 max_tokens 掺入请求 ID。修复后单次生成最长 104 秒完整收流。

**冻结 A/B 全量执行**：18/18 单元完成。工程 16 PASS、2 笔全历史去重正确拒收（T321-t1-T、T331-t1-B——真实漏斗数据）。

**重审（v1.2b→v1.2c）**：v1.2b 交付 **7 对真实新 DEV_ACCEPTED**——T331×3（t1-T、t2-T、t2-B）、T362×4（t1-T、t2-T、t3-T、t2-B），全部通过相同硬门+6 行严格 Replay+全历史新颖性+双档 v1.2 审核+准入。v1.2c 合同修订（world_delta_paths 入程序事实值、程序事实引用绑定规则；06 号文档允许的误拒合同优化）后，T321 剩余 3 个 baseline 候选连续被网关随机流切打断（STOP_RESOLUTION 9/10 + 待写的 11），**T321 尚未达标**。

**T321 六席消耗明细**：1 诚实去重拒收；2 个 v1.2b 合规隔离（已被 v1.2c 修订针对；t3-T 在 v12b 曾出现单档零错误 ACCEPT，证明可合规）；1 双档意见分歧诚实隔离（t2-B：high REJECT vs max ACCEPT）；2+3 次传输中断。

**账本**：77 笔付费完成回执，最坏单价上界 $10.01（软限 $5 已触发通知；实际用量远低于上界），0 次 401/403，9 笔终态未知请求全部永久禁发（清单见各 STOP_RESOLUTION）。交接目录整理：75 个临时诊断脚本移入 scratch/（字节保全）。

**当前 goal 状态**：IN_PROGRESS_T321_GATEWAY_WINDOW——仅差 T321≥1 对；恢复路径见 GOAL_PROGRESS.json resume_instructions。
'''
p.write_text(t + addendum, encoding='utf-8')
print('ROUND_REPORT updated, bytes:', len(t + addendum))
