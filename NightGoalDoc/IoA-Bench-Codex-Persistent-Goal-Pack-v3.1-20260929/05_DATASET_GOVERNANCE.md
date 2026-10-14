# Dataset Governance

## 数据生成基本原则

正式 case 不是“让 AI 直接出题并决定答案”。

使用四层：

### A. Programmatic causal skeleton
程序决定：
- actors；
- permissions；
- policy；
- graph；
- credentials；
- protocol；
- Ground Truth；
- unsafe/safe/recovery conditions。

### B. LLM enrichment
模型只自然化：
- 背景；
-角色；
-组织；
-消息；
-证据文本；
-干扰项。

不得改 causal truth。

### C. Validation
自动检查：
- schema；
- invariants；
- causal signature；
- mechanism；
- difficulty；
- leakage；
- duplicates；
- solvability；
- semantic coherence；
- runtime compatibility。

再由独立模型做语义验证。

### D. Formal selection
从过量候选中筛出正式 case，并冻结版本与 hash。

## 坏数据和废弃数据

不要删除。

区分：

### QUALITY_REJECTED
例如：
- schema fail；
- truth conflict；
- leakage；
- mechanism invalid；
- difficulty invalid；
- duplicate；
- unsolvable；
- validator reject。

### QUALIFIED_BUT_NOT_SELECTED
例如：
- quota overflow；
- mechanism balance；
- difficulty balance；
- world balance；
- pair balance。

后者不是坏数据，可作为 replacement pool 或 future robustness set。

## 现有 Dataset

不因“旧”而重生成。

分类：

- KEEP
- KEEP_AFTER_EVIDENCE_REFRESH
- NEW_VERSION_REQUIRED

T323 如果当前9条 semantic conflict仍存在，必须发布新版本；不改2.3.0。

## Validator independence

辅助 validator 可自由选择。

但正式 Dataset 最终质量证明中，至少有一个关键 validator 不属于对应 Tested Model set。

如果未来新增 Tested Model 恰好曾当过 validator：
优先补独立 validation；
数据内容本身无问题则不重新生成。
