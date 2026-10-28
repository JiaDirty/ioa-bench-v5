# 直接在 ZCode 新会话中使用

操作：打开 `D:\Project\ioa_codex_spec`，选择 GLM-5.3 Max、可编辑/运行模式；把本目录放入 `docs/plans/zcode_tree_factory_r2_20261024/` 后，发送下面这条**完整的一行 `/goal`**（不需要把每个文档全文粘贴进去）。

```text
/goal 接管 D:\Project\ioa_codex_spec 当前最新 HEAD，严格以 docs/plans/zcode_tree_factory_r2_20261024/GOAL.md 为本轮唯一验收合同，先通读本目录的00–09配套文档及 AGENTS.md/最新 state。直接修复 Tree→BusinessBinding→MechanismIR→Compiler→Runtime 在线强制消费、非法 IR 仍可投影、业务切换仅改 Prompt 的缺陷；复用原有编译器和6个新机制因子，完成 T321/T331/T362 的真实业务上下游联动、双臂执行见证、因果/Oracle/历史去重/strict Replay 和精简事实审核。模型生成及研发审核使用 AIHubMix deepseek-v4.1-flash-1017，凭据只从本地环境读取；本轮用户已授权充分付费调用，移除5/20美元预算停机，充分利用原生约1M上下文以及网关实测允许的131072/262144/最高393216输出上限，默认high、复杂用max，SSE完整终态与JSON验证，不能为了省钱截短输出。旧STOP/UNKNOWN/账本和已有7对新入池结果全部只读；使用全新run和request id，不重发未知POST。按M0–M6自治修代码、测试、真实调用和回归，先获得T321全新DEV_ACCEPTED，再确保T331/T362各至少一对全新研发入池，做新旧同题对照与Tree/IR离线消融，交付源码Diff、证据、全部失败分母、当前HEAD全量回归与本地Git提交、两个审阅ZIP。普通工程问题自主解决，不要反复写计划或每步询问；18项既有科学/评分门不变，不宣称科研独立审核。全部R2-G0~G6有运行证据才结束；真实外部阻塞则准确报告PARTIAL/BLOCKED，不假装通过。
```

如果复用当前仍有旧 Goal 的 ZCode 会话，按官方语法使用 **`/goal replace <上面/goal后面的目标描述>`**；若创建新会话，直接 `/goal <目标描述>` 即可。

ZCode 官方：https://zcode.z.ai/cn/docs/goal
