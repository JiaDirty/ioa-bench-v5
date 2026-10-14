# AI 场景数据工厂：从“换皮 Blueprint”到实质新颖且可执行的任务

## 1. 角色与输入输出

**生产模型** `mimo-v2.6-pro`，负责生成业务合理、机制明确且有任务/证据/拓扑差异的**Blueprint**，不是直接写 `oracle`/`scorer`/最终风险标签；目前实测原型采用 `thinking=disabled, max_tokens=4096, response_format=json_object`，但要因任务复杂度和官方/网关实证重新评估预算，不能一刀切 4K 导致难场景截断。

**编译器**（确定性/经过验证的程序），用统一动态世界能力组件 + Suite-specific capability map，把 Blueprint 转换为有状态、可执行、可评分的 CONTROL/RISK 成对 `Case`。需产出 `proposal_to_runtime_mapping`：每条关键任务依赖、证据、风险操纵和工具能力 -> 最终可执行对象或明确不可表达原因。对不能实现的关键字段返回 `CAPABILITY_GAP`，而不是静默忽略。

**验证者**：先 JSON Schema/专属约束/引用闭包/无循环与角色访问规则，再做世界转移合法性、细粒度 arm delta、oracle decidability、泄漏、参考策略/替代路径、暴露/机会、scorer、事件回放和跨数据重复检查；**审核模型** `glm-5.3-flash` 仅在硬性门槛通过后，以独立的冻结上下文复核实际编译 Case 的构念有效性、业务语义、歧义、真实性和真实结构新颖性，不仅审核原始蓝图的自述。其 PASS 不豁免程序拒收。

**数据工厂输出**：append-only 原始 Prompt/响应、请求参数、真实模型身份/usage/finish_reason、Blueprint/Case 双哈希、编译保真报告、两臂差异、参考轨迹、形式化验证、结构签名、独立审阅详情、接受或拒收理由、版本化 manifest；实验池先于科学候选池，科学候选池再先于冻结正式数据集。

## 2. 真正的多样性：以“执行后的结构”为准

明确至少四种不同概念：

1. **表面变化**：行业/公司/实体/数字/自然语言；保留可作生态真实性，却绝不能单独构成新 family。
2. **任务结构变化**：目标依赖、工具前置条件、多方参与者关系、授权路径、交互拓扑、可行替代策略。
3. **信息结构变化**：证据出处/权威/传播链、可见顺序、冲突/撤销/过期、证据核验成本。
4. **机制执行变化**：风险刺激投递、错误信任传导、授权跨越、状态失真和行为后果，在**同一预注册风险构念内部**的子类型覆盖。

签名必须从**编译后的可执行世界与观测到的能力约束**提取；生成者的 `novelty_claim` 只是一条待证假设。跨 run/candidate/current baseline 构建持久索引；候选必须留 `compared_against`, `nearest_neighbors`, `structural_delta`, `coverage_cell`, `novelty_proven` 的可核验证据。`comparisons=[]` 不得被判 `novelty_proven=true`（首个空库例外必须明确 `NO_REFERENCE` 而不是宣称创新已被证明）。

用 exact structural signature + mechanism-aware distance + near-duplicate/graph similarity + 团簇/有效 family N 组合判断。比较必须区分：同 family 的不同实例是合法复现，并不都是拒收；但达到 family 覆盖目标不能靠这种实例计数。每次质量报告同时列名义 family 和真正经对比认可的独立 family。

## 3. 审核模型的可复核性

审核格式用严格类型：`PASS | FAIL | ABSTAIN`、每一维数值评分范围、结构化证据引用、拒收原因、uncertainty；混用自由文本覆盖数值字段要拒收或 ABSTAIN。通过前校验 GLM 输出自身的 schema。

在正式大批量之前先建立 **validator negative-control set**：

- 换行业名称但结构完全同构；
- CONTROL/RISK 偷换非机制字段、非同源 base；
- 错误例外授权、过期/冲突证据、无可行安全路线；
- AI 蓝图提出的关键步骤编译时丢失；
- oracle 与 tool effect 不一致；
- 评分故意模糊或越出构念；
- 审核以语言流畅度替代实质证据。

同时设正例：两种合法路线、非传统但合规的任务解法、业务不同且实际结构不同的案例。量化审核在已知正负集上的拒收敏感度、误拒和弃权；AI 审核仍不能替代 Gate D 人类独立专家审阅。

## 4. 有效率与反馈闭环

单 Suite 分 subtype/难度/证据拓扑设缺口覆盖目标 -> 一条候选 -> 结构验证 -> 编译 -> Gate -> 去重 -> GLM 审核 -> 接受/拒收 -> 更新覆盖矩阵；只有当错误有明确可修正的因果原因时才改提示/编译/能力约束。保留每轮 Prompt 版本与原始拒收，不对同一失败盲目重试。

建议报告指标：每100次候选各个 Gate 的通过/拒收率、每个实质新 family 所需调用数、编译保真丢失率、CAPABILITY_GAP 分布、机制覆盖、难度及拓扑覆盖、有效 family N、审核准确度和弃权、后续真实模型诊断中的 exposure/utility/invalid。用户不以模型调用费为主要限制，但工效仍以“获得一个科研有效新 family 的成本与耗时”为中心。

## 5. 与正式测评严格隔离

- 生成/审核角色不得读正式被测模型 `deepseek-v4.1-flash` 的安全通过率进行逐题筛选；不要为了提高观察到的失误率而泄漏测量或选择性淘汰。区分探索/诊断池与冻结确认池。
- 每个 Suite 有自己的科学能力图、编译器检查和评分验证，统一接口/组件可复用，但不能用 T321 的安全规范假装 T333 等不同构念。
- 不能因 JSON 正确、GLM PASS、witness 过关就宣称科研数据已冻结或满足 Gate D。
- 既有2160条旧候选与所有新实验候选只读或分命名空间管理；有明确版本与 PI 决策后才能将真正合格的新候选纳入正式数据版本，生成过程/筛除规则必须冻结并可复现。
- 若某机制无法在当前环境中构造可执行、因果干净且可判分案例，应暂停该 Suite 子机制、提科研/能力缺口建议，而非调整 scorer 硬通过。
