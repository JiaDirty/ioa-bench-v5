# User Decision Boundaries

Goal 的默认原则是：**能由工程和证据解决的事情，Codex 自己解决。**

只有真正越过用户控制边界时才暂停。

## 必须向用户请求决定

### 1. 核心科研定义变化
例如：
- 改变 18 项 canonical meaning；
- 改变模型中心的研究对象；
- 改变 Safety/Utility 的核心解释；
- 把 SIMULATION_ONLY 改成真实人类结论。

### 2. Canonical Tested Model roster 变化
增加/替换正式被测模型需要用户明确决定。

### 3. 真实 Provider 成本或授权
如果当前没有有效授权，在首次真实 AIHubMix / Provider smoke、pilot、formal campaign 前暂停。

如果用户只授权了小 smoke，而后续需要大规模正式 Campaign，应按授权范围行事。

### 4. 外部凭据、账户、权限
不能自行制造或猜测 secret。

### 5. 不可逆破坏
需要删除/覆盖无法恢复的 frozen Dataset、历史 Run、Release 或科研证据时必须暂停。

通常应优先采用新版本、fork、supersedes，而不是破坏。

### 6. 无可辩护路径
如果经过合理尝试后，关键目标受外部缺失材料或不可恢复证据阻断，应给出：
- 已尝试路径；
- 证据；
- blocker；
- 能解锁的最小用户输入。

## 不需要用户决定

普通 bug、路径、测试、manifest、hash、版本号、脚本、报告、mock、验证器、打包、一致性等工程问题，不应频繁打断用户。

只要科研含义不变，Codex可以自主创建 successor candidate / non-semantic corrective release，并完整记录 provenance。
