# Benchmark Stabilization Plan

## 目标

把当前工作区从“18 项已经分别实现很多内容”整理为：

**一个整体统一、可以冻结、可以让多个 Tested Model公平执行的 Benchmark Release。**

## 当前阶段不采用固定顺序

Goal 每次恢复时，根据 Gate 和依赖选择当前最早可执行任务。

但完成 Benchmark Freeze 前，必须覆盖以下工作面：

### 1. Authoritative Reconciliation
统一：
- Dataset identities；
- Run identities；
- pilot/formal status；
- valid/canonical/superseded；
- source hash；
- campaign status。

### 2. Current-source Re-anchor
对当前源码重新建立：
- source hash；
- Contract/runtime/scorer mapping；
- changed-component regression；
- formal dispatcher evidence。

### 3. 18-suite Dataset Acceptance
逐套确认：
- truth；
- mechanism；
- difficulty；
- leakage；
- semantic quality；
- dedup；
- solvability；
- runtime compatibility；
- validator evidence；
- provenance。

### 4. T361–T363 targeted redesign
按 model-based Synthetic Human protocol 更新并重新验收。

### 5. All-suite representative dry run
18/18 都必须试跑。

不是只证明几个 suite。

覆盖：
- Control/Risk；
- Easy/Medium/Hard；
- mechanisms；
- multi-agent；
- tools/A2A；
- invalid output；
- provider error path；
- Replay；
- Scorer；
- Utility。

### 6. Benchmark Release Freeze
所有公共科研条件冻结后，才允许新的完整 formal Campaign。

## Freeze 后原则

正式 Campaign期间不修改科研语义。

若发现科学性 bug：
- stop affected scope；
- impact analysis；
- versioned fix；
- invalidate only affected runs；
- preserve unaffected valid research results。
