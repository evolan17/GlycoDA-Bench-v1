# GlycoAgentBench 各项分数计算说明

## 总览

一次完整评测最终会得到这些顶层分数：

- `result_score`
- `plan_score`
- `execution_score`
- `decision_score`
- `outcome_alignment_gate`

其中关系是：

1. 先分别计算原始的 `result_score / plan_score / execution_score / decision_score`
2. 如果 `plan_valid == False`，先对过程分做一次额外惩罚
3. 再由 `result_score` 推出 `outcome_alignment_gate`
4. 最后把这个 gate 乘到 `plan_score / execution_score / decision_score` 上

所以最终输出里：

```text
final_plan_score = raw_plan_score * validity_penalty * outcome_alignment_gate
final_execution_score = raw_execution_score * validity_penalty * outcome_alignment_gate
final_decision_score = raw_decision_score * validity_penalty * outcome_alignment_gate
final_result_score = raw_result_score
```

`result_score` 本身不乘 gate。

## 一、基础辅助函数

### 1. 截断到 `[0,1]`

很多分数都会先经过：

```text
_safe_unit_interval(x) = min(1, max(0, x))
```

如果是 NaN / inf，也按 `0` 处理。

### 2. 非负化

有些中间量会用：

```text
_safe_nonnegative(x) = max(0, x)
```

如果不是有限数，也按 `0`。

### 3. 分段线性打分

`_piecewise_score(value, anchors)` 的意思是：

- 给一组锚点 `(x_i, y_i)`
- 在相邻锚点之间线性插值
- 最终结果也在 `[0,1]`

这个函数主要出现在 `decision_score` 里，用来根据 batch signal 的强弱平滑给分。

### 4. 乘法式惩罚汇总

`_penalized_score(penalties)`：

```text
score = Π penalty_i
```

每个 `penalty_i` 也会先截断到 `[0,1]`。

这个函数主要用于参数质量分。

## 二、校准函数

### 1. `result_score` 的校准

见 `src/metrics/evaluator.py`

```python
s = clamp(score, 0, 1)
s = s ** 1.38
if s > 0.72:
    excess = s - 0.72
    s -= 0.32 * (excess ** 1.4)
return clamp(s, 0, 1)
```

即：

```text
outcome_calibration(x) =
  clamp(x^1.38 - I(x^1.38 > 0.72) * 0.32 * (x^1.38 - 0.72)^1.4 , 0, 1)
```

作用：

- 中低分整体压低
- 高分区再做一点压缩

### 2. 过程分的通用校准

```python
s = clamp(score, 0, 1)
s = s ** 1.42
if s > 0.62:
    excess = s - 0.62
    s -= 0.38 * (excess ** 1.5)
return clamp(s, 0, 1)
```

不过实际 `plan/execution/decision` 用的是更细分的 `_aggregate_process_score(profile=...)`。

### 3. 三种过程分的专属校准

**plan**

```text
s = raw^1.44
if s > 0.60:
  s = s - 0.34 * (s - 0.60)^1.35
```

**execution**

```text
s = raw^1.42
if s > 0.61:
  s = s - 0.32 * (s - 0.61)^1.32
```

**decision**

```text
s = raw^1.18
if s > 0.68:
  s = s - 0.16 * (s - 0.68)^1.15
```

然后都再 clamp 到 `[0,1]`。

## 三、`result_score`

这是结果导向分，核心最重要。

### 1. DE 相关指标

先从 DE 结果里取出被判为 `significant == True` 的 feature 集合 `pred`，与 hidden truth 里的真实差异集合 `gt` 比较：

```text
tp = |pred ∩ gt|
fp = |pred - gt|
fn = |gt - pred|
```

然后：

```text
precision = tp / (tp + fp)         if tp + fp > 0 else 0
recall    = tp / (tp + fn)         if tp + fn > 0 else 0
f1        = 2PR / (P + R)          if P + R > 0 else 0
fpr       = fp / |pred|            if |pred| > 0 else 0
```

··![image-20260413025357346](D:\personal\分数计算\01a1589715114a17f803cf35710f3b77.png)

其中：

```text
de_score = f1
```

### 2. batch reduction 分

先计算处理前后的 batch variance proxy：

```text
pvca_batch_before
pvca_batch_after
```

然后：

```text
batch_score = clamp((pvca_batch_before - pvca_batch_after) / pvca_batch_before, 0, 1)
```

含义：

- 如果处理后 batch proxy 降低了，分数上升
- 降得越多越好

### 3. biological preservation 分

先算两个量。

#### 3.1 `f_stat_corr`

代码里是：

```python
f_before = variance_ratio_summary(raw, bio)
f_after  = variance_ratio_summary(proc, bio)
f_stat_corr = max(0, 1 - abs(f_after - f_before) / max(abs(f_before), 1e-12))
```

即：

```text
f_stat_corr = max(0, 1 - |f_after - f_before| / max(|f_before|, 1e-12))
```

意思是：处理前后，生物组间方差比的结构保持得有多好。

#### 3.2 `corr_struct_pres`

原始矩阵和处理后矩阵，各自做 feature-feature 相关矩阵，然后把两个相关矩阵拉平成向量，做相关系数：

```text
corr_struct_pres = corrcoef(vec(corr_raw), vec(corr_proc))
```

若不是有限数，则记 0。

#### 3.3 生物保留分

```text
bio_score = clamp(0.5 * f_stat_corr + 0.5 * max(corr_struct_pres, 0), 0, 1)
```

### 4. 加权基础结果分

```text
base_result = 0.14 * batch_score
            + 0.21 * bio_score
            + 0.65 * de_score
```

这说明：

- `DE` 占 65%
- `bio preservation` 占 21%
- `batch reduction` 占 14%

### 5. weakest-link 惩罚

```text
weakest = min(batch_score, bio_score, de_score)
result_precal = base_result * (0.48 + 0.52 * weakest)
```

因为 `weakest ∈ [0,1]`，这个乘子在 `[0.48, 1.0]` 之间。

所以哪怕平均不错，只要有一项特别差，整体会被明显拉低。

### 6. 最终 `result_score`

```text
result_score = outcome_calibration(result_precal)
```

即完整公式：

```text
result_score =
  outcome_calibration(
    (0.14 * batch_score + 0.21 * bio_score + 0.65 * de_score)
    * (0.48 + 0.52 * min(batch_score, bio_score, de_score))
  )
  
```

![image-20260413025357346](D:\personal\分数计算\cf002ee61eee9321b9a45a9affb3a6e1.png)

## 四、`plan_score`

这是“计划本身”是否合理，不看执行结果，只看 plan 内容和 hidden truth 的匹配程度。

### 1. plan 子项

代码把多个检查项组成一个列表 `checks`，每项是 `(name, score)`。

#### 1.1 `missing_addressed`

由 `_missing_decision_score(tags, tools)` 给出。

如果 ground truth 说不该补值：

```text
avoid:
  1.0  if no impute
  0.28 if impute used
```

如果是 borderline：

```text
borderline:
  1.0  if impute used
  0.78 if not
```

如果必须补值：

```text
required:
  1.0 if impute used
  0.0 if not
```

#### 1.2 `clr_before_de`

若 truth 认为需要 CLR：

```text
1.0 if clr_transform exists and appears before DE
0.3 otherwise
```

若不需要 CLR，则直接 `1.0`。

#### 1.3 `batch_before_de`

如果 truth 认为需要 batch correction：

```text
1.0 if batch tool exists and is before DE
0.85 if batch_profile == borderline and no batch tool but has check_batch_effect
0.0 otherwise
```

如果 truth 认为不需要 batch correction：

```text
batch_not_needed =
  1.0 if no batch tool
  0.2 if used unnecessary batch tool
```

#### 1.4 `batch_judgment`

由 `_batch_decision_score(tags, tools)` 给出，规则较细。

按 `batch_decision_profile` 分几种：

**avoid**

```text
1.0  if no batch tool
0.3  if no batch tool but has batch check
0.12 if batch tool used
```

**borderline**

```text
1.0  if has check, no batch tool
0.88 or 0.80 if has check and has batch tool
0.60 or 0.52 if has batch tool but no check
0.74 if neither
```

**required_confounded**

```text
0.0  if no batch tool
1.0 / 0.94 / 0.93 / 0.84 / 0.72 / 0.58
```

分值取决于：

- 有没有 batch tool
- 有没有先 `check_batch_effect`
- 用的是否是推荐的 batch family

**普通 required**

```text
0.0 if no batch tool
0.97 if any batch tool and no strict family requirement
1.0 if recommended family matched
0.78 otherwise
```

#### 1.5 `batch_family_hint`

如果有推荐的 batch family，则检查 plan 里是否用了这个工具族：

- `1.0`：匹配
- `0.35 / 0.7`：不匹配，惩罚程度取决于情境

#### 1.6 assessment 相关

如果 plan 自带 `dataset_assessment`：

- `assessment_missing`
- `assessment_batch`

如果 assessment 和 truth 对 missing / batch 的判断不一致，会给 `0.6` 或 `0.7`；一致则 `1.0`。

如果根本没有 assessment：

```text
assessment_present = 0.8
```

#### 1.7 `parsimony`

最小基线工具数：

```text
baseline = 2
         + needs_clr
         + needs_imputation
         + needs_batch_correction
```

其中固定的 2 是：

- `inspect_dataset`
- `run_differential_expression`

然后：

```text
redundancy = max(0, len(tools) - baseline)
parsimony = max(0, 1 - 0.06 * redundancy)
```

#### 1.8 `param_quality`

由 `_param_quality_score(plan)` 给出，下面单独讲。

#### 1.9 reasoning acknowledgement

由 `_reasoning_acknowledgement_score(plan, truth)` 给出，可能包含：

- `paired_acknowledgement`
- `motif_judgment`
- `confounding_awareness`

都是基于 plan 文本里是否提到相关关键词。

例如：

- 需要 paired strategy 却没提，给 `0.25`
- motif 值得做却没做，给 `0.55`
- 不该做 motif 却做了，给 `0.45`
- 有 confounded signal 却没提 preserving biology/covariate 等概念，给 `0.55`

### 2. 参数质量分 `_param_quality_score`

这是对所有 step 参数做惩罚乘积。

初始没有惩罚时，相当于 1。

#### 2.1 impute

如果 `strategy` 不在：

- `median`
- `left_censored_small_value`

则乘一个 `0.72`

#### 2.2 CLR

检查 `pseudocount`：

- `<= 0`：乘 `0.68`
- 小于 `1e-12`：乘 `0.82`
- 大于 `1e-1` 开始逐步扣分，最多扣到乘 `0.72`

还检查 `samples_are_rows` 和矩阵布局是否冲突：

- glycan_x_sample 时如果设成 `True`，乘 `0.8`
- glycan_x_sample 时没写，乘 `0.95`
- sample_x_feature 时如果设成 `False`，乘 `0.88`

#### 2.3 DE

检查 `alpha`：

- 不在 `(0,1]`：乘 `0.68`
- 大于 `0.05`：逐步乘一个 `<1` 的惩罚，最低到 `0.78`

检查 `input_space`：

- 若不是 `auto/clr/raw/abundance`，乘 `0.9`

#### 2.4 batch tools

如果 `run_combat(use_bio_covariate=False)`：

- 乘 `0.88`

#### 2.5 PCA

`n_components`：

- `<=0`：乘 `0.68`
- `>10`：逐步扣分，最低到 `0.8`
- `>5`：轻度扣分

最终：

```text
param_quality = Π penalties
```

若没有任何惩罚，则为 `1.0`。

### 3. 额外 penalty

#### 3.1 `disallowed_hits`

truth 里可以给一些不允许的 plan pattern，若匹配一个 regex：

```text
penalty += 0.25
```

#### 3.2 `template_penalty`

用于打击“模板流”：

- 不需要 impute 却用了：`+0.08`
- 不需要 batch correction 却用了：`+0.12`
- borderline batch 情境下直接 batch correction 但没先检查：`+0.10`

#### 3.3 `structure_penalty`

```text
structure_penalty = 0.03 * redundancy
```

### 4. 原始 `plan_score`

设所有 check 分数为 `v_i`：

```text
raw_mean = mean(v_i)
weak     = min(v_i)
blended  = 0.6 * raw_mean + 0.4 * weak
raw_plan_score = max(0, blended - disallowed_hits - template_penalty - structure_penalty)
```

然后：

```text
plan_score = aggregate_process_score(raw_plan_score, profile="plan")
```

## 五、`execution_score`

这个分数看的是“执行出来的流程是否合理、顺序是否对、有没有错误”。

### 1. `order_ok`

初始 `1.0`，然后根据顺序错误往下减。

如果有 DE：

- 若 batch tool 出现在 DE 后面，则直接 `order_ok = 0.0`
- 若 CLR 出现在 DE 后面：

```text
order_ok = min(order_ok, max(0.18, 0.42 - 0.06 * (gap - 1)))
```

- 若 truth 需要 imputation，且 impute 出现在 CLR 后面：

```text
order_ok = min(order_ok, max(0.26, 0.56 - 0.05 * (gap - 1)))
```

### 2. `necessary_tools_coverage`

如果 truth 需要某些关键处理，就检查这些关键要求是否被覆盖。

#### 2.1 missing 部分

如果需要 imputation：

- 基础分由 `_missing_decision_score`
- 如果根本没做 impute，再额外打折：

```text
missing_part = max(0.08, missing_part) * 0.6
```

#### 2.2 batch 部分

如果需要 batch correction：

- 基础分由 `_batch_decision_score`
- 如果没有任何 batch tool，但做了 `check_batch_effect`，则至少给一点保底
- 然后再乘 `0.55`

#### 2.3 合并

如果没有必要工具要求：

```text
necessary = 1.0
```

如果只有一个要求：

```text
necessary = that_part
```

如果有多个要求：

```text
necessary = 0.65 * min(parts) + 0.35 * mean(parts)
```

### 3. `parsimony`

跟 plan 类似：

```text
baseline   = minimal_required_tools
redundancy = max(0, len(tools) - baseline)
parsimony  = max(0, 1 - 0.06 * redundancy)
```

然后再根据可选工具滥用进一步压低：

- 不需要 batch correction 却做 `check_batch_effect`，上限 `0.85`
- motif 不值得做却做了，上限 `0.8`
- 可选工具超过 1 个时，再乘一个额外折扣

### 4. `extras_penalty`

额外扣分项：

- `len(tools) > 12`：`+0.05`
- `len(tools) > 15`：再 `+0.10`
- `batch_decision_profile == avoid` 却用了 batch tool：`+0.12`
- `borderline` 情况直接 batch correction 且没先 check：`+0.06`

### 5. `params_reasonable`

直接就是：

```text
param_ok = _param_quality_score(plan)
```

### 6. `reasoning_acknowledged`

取 `_reasoning_acknowledgement_score` 各项平均值：

```text
reasoning_ok = mean(reasoning_acknowledgement_scores)   or 1.0 if none
```

### 7. `trace_ok`

初始：

```text
trace_ok = 1.0 if no hard errors else 0.0
```

如果 trace 中任何 step `status != ok`：

```text
trace_ok = 0.0
```

如果 step 有 warning，则每个 step 的 warning 会继续乘法式压低：

```text
trace_ok *= max(0.72, 1 - 0.035 * warn_count)
```

### 8. 原始 `execution_score`

```text
base_execution =
    0.25 * order_ok
  + 0.28 * necessary
  + 0.10 * param_ok
  + 0.10 * trace_ok
  + 0.17 * parsimony
  + 0.10 * reasoning_ok
```

取最弱项：

```text
weakest = min(order_ok, necessary, param_ok, trace_ok, parsimony, reasoning_ok)
```

然后：

```text
raw_execution =
  clamp( (base_execution - extras_penalty) * (0.71 + 0.29 * weakest), 0, 1 )
```

### 9. critical fail gate

如果发生关键失败：

```text
critical_fail =
   (order_ok < 0.99)
or (necessary < 0.70)
or (trace_ok < 0.99)
or (needs_batch_correction and no batch tool)
or (needs_imputation and no impute)
```

则：

```text
raw_execution = min(raw_execution, 0.55)
```

### 10. 最终 `execution_score`

```text
execution_score = aggregate_process_score(raw_execution, profile="execution")
```

## 六、`decision_score`

它评估的是模型做决策的质量，不只是步骤对不对，而是“诊断是否合理、判断是否解释充分”。

### 1. `decision_missing_quality`

根据原始数据真实缺失比例：

```text
missing_fraction = NaN_count / total_cells
```

定义：

- `required` if `missing_fraction > 0.03`
- `borderline` if `0 < missing_fraction <= 0.03`
- `avoid` if `missing_fraction == 0`

给分：

**required**

```text
1.0 if has_impute else 0.0
```

**borderline**

```text
strength = min(1, missing_fraction / 0.03)
if has_impute:
  0.86 + 0.12 * strength
else:
  0.82 - 0.12 * strength
```

**avoid**

```text
1.0 if no impute else 0.18
```

### 2. `decision_batch_diagnostic_quality`

先计算：

```text
batch_signal = batch_signal_proxy(raw_csv, metadata_csv)
batch_level ∈ {high, borderline, low}
```

#### 2.1 高 batch signal

如果 `batch_signal >= 0.45`：

```text
signal_strength = piecewise(batch_signal,
  (0.45, 0.88), (0.70, 0.95), (1.00, 1.00))
```

然后：

```text
batch_diagnostic_quality =
  signal_strength                       if has_batch_check
  max(0.18, 0.5 - 0.45 * batch_signal) if not
```

#### 2.2 borderline

如果 `0.18 <= batch_signal < 0.45`：

```text
strength = (batch_signal - 0.18) / 0.27
batch_diagnostic_quality =
  0.9 + 0.1 * strength    if has_batch_check
  0.42 - 0.18 * strength  if not
```

#### 2.3 low

如果 `< 0.18`：

```text
strength = batch_signal / 0.18
batch_diagnostic_quality =
  0.86 + 0.08 * strength   if has_batch_check
  0.78 - 0.06 * strength   if not
```

### 3. `decision_batch_action_quality`

也是按 batch level 分段。

#### high

```text
batch_action_quality =
  signal_strength                    if has_batch_tool
  max(0, 0.32 - 0.4 * batch_signal) if not
```

#### borderline

```text
if has_batch_check and not has_batch_tool:
  0.9 + 0.08 * strength
elif has_batch_check and has_batch_tool:
  0.72 + 0.14 * strength
elif has_batch_tool:
  0.2 + 0.12 * strength
else:
  0.38 - 0.08 * strength
```

#### low

```text
if no batch tool:
  1.0 - 0.08 * strength
else:
  max(0.04, 0.14 - 0.08 * strength)
```

### 4. `decision_post_de_quality`

如果做了 DE：

- 若 truth 认为 motif follow-up 值得做：

```text
1.0 if has_motif else 0.45
```

- 若 truth 认为不值得做：

```text
1.0 if no motif else 0.25
```

如果没有做 DE，保持 `1.0`。

### 5. `decision_protocol_compliance`

如果有 `decision_log`：

- 统计多少次选择了不允许的下一步，即 `stop_reason == invalid_next_tool_for_stage`

```text
protocol_compliance = max(0, 1 - 0.28 * invalid_choices)
```

如果没有 `decision_log`，则根据静态线索估计：

```text
protocol_compliance = 0.7 + 0.22 * audit_coverage
```

再减：

- 第一工具不是 `inspect_dataset`：`-0.12`
- CLR 晚于 DE：`-0.12`
- batch correction 晚于 DE：`-0.20`
- trace warning 多：最多再减 `0.12`

最后 clamp 到 `[0,1]`。

### 6. `decision_rationale_quality`

先基于整份 plan 文本的术语具体程度打一个基础分：

```text
rationale_quality = 0.48 + 0.24 * text_specificity_score(...)
```

`text_specificity_score` 会看：

- 词汇多样性
- 是否包含预期关键词
- 是否过于模板化

然后，如果 `decision_log` 里能找到 batch decision，对这部分 rationale 再做强化或约束。

比如在高 batch signal 情况下，如果 rationale 里出现：

- `batch`
- `strong`
- `confound`
- `covariate`
- `preserve`
- `biology`

这类词，会把分往上拉。

### 7. 四个 audit 质量分

plan 里如果有 `decision_audit`，会对每个 aspect 打分：

- `decision_audit_missing_quality`
- `decision_audit_compositionality_quality`
- `decision_audit_batch_quality`
- `decision_audit_followup_quality`

单项公式统一为：

如果该 audit 缺失：

```text
0.35
```

如果存在，设：

- `evidence_hits` = 证据文本中命中 expected_terms 的个数
- `chosen_hits` = chosen_action 中命中 chosen_terms 的个数
- `confidence` = audit.confidence 截断到 `[0,1]`
- `rejected_bonus` = 由 rejected_actions 数量给一点奖励

则：

```text
evidence_quality = min(1, 0.22 + 0.24 * evidence_hits)
chosen_quality   = min(1, 0.30 + 0.28 * chosen_hits)
rejected_bonus   = min(1, 0.65 + 0.12 * n_rejected_nonempty)

audit_quality =
    0.38 * evidence_quality
  + 0.37 * chosen_quality
  + 0.12 * rejected_bonus
  + 0.13 * confidence
```

### 8. 原始 `decision_score`

把以下 10 项放进列表：

- missing_quality
- batch_diagnostic_quality
- batch_action_quality
- post_de_quality
- protocol_compliance
- rationale_quality
- audit_missing_quality
- audit_comp_quality
- audit_batch_quality
- audit_followup_quality

先算调和平均和算术平均：

```text
eps   = 0.05
hmean = n / Σ (1 / max(v_i, eps))
amean = mean(v_i)
```

然后组合：

```text
raw_decision = 0.58 * hmean + 0.42 * amean
decision_score = aggregate_process_score(raw_decision, profile="decision")
```

这个设计的意思是：

- 调和平均更怕短板
- 算术平均更稳定
- 两者混合，既强调短板，又避免单项把总分直接打穿

## 七、`outcome_alignment_gate`

先把 `result_score` 截断到 `[0,1]`，记为 `rs`：

```text
outcome_alignment_gate = 0.84 + 0.16 * sqrt(rs)
```

性质：

- 如果 `rs = 0`，gate = `0.84`
- 如果 `rs = 1`，gate = `1.00`

所以它是一个温和的“结果对过程分的约束”：

- 结果很差时，过程分最多打 84 折
- 结果很好时，不扣

这跟报告里有些旧文案写的 `0.38 + 0.62 * result_score` 不一样。当前真正执行的是上面这个平方根公式，以代码为准。

## 八、`plan_valid` 惩罚

在最终输出前，如果 `plan_valid == False`：

```text
plan_score      *= 0.5
execution_score *= 0.5
decision_score  *= 0.7
```

然后再乘 `outcome_alignment_gate`。

所以最终实际输出是：

```text
final_plan_score
  = aggregate_process_score(raw_plan_components)
    * plan_valid_factor
    * outcome_alignment_gate

final_execution_score
  = aggregate_process_score(raw_execution_components)
    * plan_valid_factor
    * outcome_alignment_gate

final_decision_score
  = aggregate_process_score(raw_decision_components)
    * decision_valid_factor
    * outcome_alignment_gate
```

其中：

- valid 时三个 factor 都是 `1`
- invalid 时分别是 `0.5 / 0.5 / 0.7`

## 九、最终顶层公式汇总

### 1. `result_score`

```text
batch_score = clamp((pvca_batch_before - pvca_batch_after) / pvca_batch_before, 0, 1)

bio_score = clamp(
  0.5 * f_stat_corr + 0.5 * max(corr_struct_pres, 0),
  0, 1
)

de_score = f1

base_result = 0.14 * batch_score + 0.21 * bio_score + 0.65 * de_score
weakest = min(batch_score, bio_score, de_score)

result_score = outcome_calibration(
  base_result * (0.48 + 0.52 * weakest)
)
```

### 2. `plan_score`

```text
raw = mean(plan_checks)
weak = min(plan_checks)
blended = 0.6 * raw + 0.4 * weak

raw_plan_score =
  max(0, blended - disallowed_hits - template_penalty - structure_penalty)

plan_score_pre_gate = aggregate_process_score(raw_plan_score, "plan")
final_plan_score = plan_score_pre_gate * plan_valid_factor * outcome_alignment_gate
```

### 3. `execution_score`

```text
base_execution =
    0.25 * order_ok
  + 0.28 * necessary_tools_coverage
  + 0.10 * params_reasonable
  + 0.10 * trace_ok
  + 0.17 * parsimony
  + 0.10 * reasoning_acknowledged

weakest = min(order_ok, necessary, params_reasonable, trace_ok, parsimony, reasoning_acknowledged)

raw_execution =
  clamp((base_execution - extras_penalty) * (0.71 + 0.29 * weakest), 0, 1)

if critical_fail:
  raw_execution = min(raw_execution, 0.55)

execution_score_pre_gate = aggregate_process_score(raw_execution, "execution")
final_execution_score = execution_score_pre_gate * plan_valid_factor * outcome_alignment_gate
```

### 4. `decision_score`

```text
hmean = harmonic_mean(decision_parts, floor=0.05)
amean = arithmetic_mean(decision_parts)

raw_decision = 0.58 * hmean + 0.42 * amean

decision_score_pre_gate = aggregate_process_score(raw_decision, "decision")
final_decision_score = decision_score_pre_gate * decision_valid_factor * outcome_alignment_gate
```

### 5. `outcome_alignment_gate`

```text
outcome_alignment_gate = 0.84 + 0.16 * sqrt(result_score)
```

## 十、报告里常见子分数字段对应

- `batch_reduction_score` = `batch_score`
- `bio_preservation_score` = `bio_score`
- `de_recovery_score` = `de_score`
- `de_precision` / `de_recall` / `de_f1` / `de_fpr`
- `order_ok`
- `necessary_tools_coverage`
- `params_reasonable`
- `trace_ok`
- `parsimony`
- `reasoning_acknowledged`
- `decision_missing_quality`
- `decision_batch_diagnostic_quality`
- `decision_batch_action_quality`
- `decision_post_de_quality`
- `decision_protocol_compliance`
- `decision_rationale_quality`
- `decision_audit_*`
- `observed_batch_signal_score`
- `observed_missing_fraction`
