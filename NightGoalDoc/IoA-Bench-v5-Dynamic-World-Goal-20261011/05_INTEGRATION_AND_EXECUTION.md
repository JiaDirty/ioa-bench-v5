# 现有 ZCode 主线与 Codex 独立原型的集成、执行和证据安全

## 现状（须在 Windows 上重新核对）

- 正式主工作区：`D:\Project\ioa_codex_spec`。2026-10-11 ZCode 报告 v5 在线协议 v1.1.2，DeepSeek `max_tokens=131072`，新增16 Suite 96/96 个 Smoke 技术完成；早期 T332/T352 Smoke 不同预算版本，须保留版本区分，不随意声称全部18项都在 v1.1.2 获同一冒烟结果。
- Codex 实验副本：`D:\Project\ioa_codex_spec_ai_generation_probe`。这不是 Git worktree；主线此前未发现 `.git`。原型一度得到 MiMo 生成和 GLM 审核2组 PASS，但上传证据显示它们最终签名主要只改变 domain，不能算已证实不同 family。Codex 正在修复蓝图→Case保真、结构去重和独立审核契约；本文件不能预判该修复结果。
- 当前2026-10-10静态源码显示 `Case`, `Scenario`, `EnvContext.events`, `ActionRecord`, `check_pair`、18 Suite 已存在，动态事件与世界能力的具体支持要按最新 Windows 工作树核实，别重新造轮子。

## M0 操作顺序

1. 只读读取 `AGENTS.md`、当前 Goal、PI 决策、18构念、v5代码及测试、最近在线协议/manifest、主线修改状态、Codex 目录下代码与报告；核对谁正在编辑哪些文件。
2. 用文件清单/sha256与内容 diff 而非“两个目录文件名一致”判断可移植改动。优先只移植隔离原型的 `ai_generation` 目录、针对性测试、配置和契约。**不要用复制整目录覆盖主线。**
3. 先生成主线只读备份/内容哈希 manifest；新工作在独立目录或明确限定的新增文件中进行。涉及 engine/suite/pilot/scorer 等共享模块修改时确认并行状态，必要时让 Codex 停止同一文件写入，避免互相覆盖。
4. 现有 `.env`、密钥、历史原始回放/日志不复制到隔离代码目录；确需访问 AIHubMix 仅从短生命周期进程安全读取凭据，日志脱敏。所有真实输出保存独立实验 run-id。
5. 先运行可信基线的最小测试并标注历史审计 artifact 缺失所致的预期缺口，不把排除测试写成全量“测试通过”。版本改变后针对性回归。

## 变更分流

- **直接推进**：新文档/独立组件、type schema、能力映射、离线 mocks、单独 run 目录、非破坏性测试。
- **审查后推进**：对现有 `Case`, `Scenario`, engine, `ExposureChecker`, scoring interfaces 的兼容扩展；必须保留现有结果字段或有版本化迁移器和回归；历史证据只读。
- **必须暂停提交科学决策**：修改18构念边界、Ground Truth 来源、T333模糊文本自动判定、T331以模型不完成为由降低效用门槛、直接回写已发布旧候选数据、正式数据冻结、PI明确未批准的正式付费测评。

## Provider 与协议管理

- `mimo-v2.6-pro` + `glm-5.3-flash` 的能力依据厂商官方文档 + AIHubMix 本地快照 `D:\Project\Playground\scrape\aihubmix` +最小真实网关探针，以网关实际能力为准；生成/审核配置不能直接套用 DeepSeek 128K。
- 被测 DeepSeek 的当前实测协议/身份来自 ZCode 主线报告，必须在冻结前从最新配置/manifest 再核实；输出上限不等于每次使用量；合理 timeout、max calls、累计预算和 long-thinking 诊断保持版本化。
- 定义人工审核与正式付费 Campaign 的 PI 授权检查；批量生成或 Smoke 的范围如果超过已获许可，先列出范围和费用估算，再请求对应批准。

## 科研有效性优先级

场景/机制在多路径里发生的可测行为 > 统一执行与可观测性 > 因果配对与外部真值 > 真正新增结构 family > 数据生产效率 > 表面业务复杂度。不要追求任意组件无限自由；只要18项所需的可组合能力，并确保每项被测模型具有适当自主空间。

## 最终交付应该有哪些

1. 一套可安装/运行的 v5 动态世界执行与监测系统，有清晰 README、设计决定记录和测试。
2. 一条从覆盖规划、MiMo生成、编译、结构差异验证、硬性 Gate、跨批多样性、GLM审核到候选入库的可复用全自动数据生产命令与追溯目录。
3. 18 Suite 的能力图、原始构念引用、adapter/Oracle/monitor/scorer 校验、覆盖统计与残余不可表达能力清单。
4. 各项候选数据版本及数据质量证据、外部独立审核材料和可靠性测试。
5. 确认 Pilot 与后续获准正式测评的冻结 manifest、原始事件、统计脚本、报告与可重复执行指导。
6. 逐项说明哪些已验证、哪些仅实现、哪些仍 BLOCKED，避免一份“all green”摘要掩盖科研缺口。
