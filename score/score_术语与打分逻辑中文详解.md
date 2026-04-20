# GlycoAgentBench 评分术语与打分逻辑中文详解



说明依据：

- `score/score_formulas_explained.md`
- `src/metrics/evaluator.py`
- `src/planner/schema.py`
- `src/tools/registry.py`

下面默认把 4 个总分理解为：

- `result_score`：结果分，最终结果到底做得好不好
- `plan_score`：计划分，方案设计得合不合理
- `execution_score`：执行分，实际执行顺序和过程对不对
- `decision_score`：决策分，诊断与判断是否有依据、是否像在认真分析而不是乱选工具

---

## 1. 先用一句话理解整个评分系统

这个评测不是只看“最后差异分析做对了没有”，也不是只看“流程看起来像不像专家流程”，而是同时看四件事：

1. 结果有没有把真正的差异特征找回来
2. 计划里有没有选对步骤
3. 执行时顺序、参数、轨迹有没有问题
4. 决策时有没有根据数据现象做出合理判断

但这里有一个重要设计：

- `result_score` 是最核心、最硬的分数
- `plan_score / execution_score / decision_score` 虽然各自独立计算，但最后还会乘上一个 `outcome_alignment_gate`

意思是：

- 如果流程写得很漂亮，但结果很差，过程分也不能太高
- 如果结果很好，过程分就不会被额外压制

实际最终关系是：

```text
final_plan_score = raw_plan_score * plan_valid_penalty * outcome_alignment_gate
final_execution_score = raw_execution_score * plan_valid_penalty * outcome_alignment_gate
final_decision_score = raw_decision_score * decision_valid_penalty * outcome_alignment_gate
final_result_score = raw_result_score
```

注意：

- `result_score` 本身不乘 gate
- gate 是由 `result_score` 推出来的

---

## 2. 最常见英文术语翻译

### 2.1 数据与分析相关术语

- `DE` = Differential Expression，差异表达/差异分析
- `feature`：特征。在这个项目里通常就是某个 glycan（糖链特征）
- `ground truth` / `hidden truth`：隐藏真值。也就是出题方真正知道、但模型不知道的正确答案
- `batch effect`：批次效应。不是生物差异，而是实验批次、设备批次等带来的系统偏差
- `batch correction`：批次校正
- `bio` / `biological`：生物学信号，真正来自组间生物差异的部分
- `compositionality`：组成型数据特性。糖组学/组学数据常常总量受约束，比例关系比绝对值更重要
- `CLR` = Centered Log-Ratio transformation，中心化对数比变换
- `imputation` / `impute`：缺失值填补
- `motif enrichment`：基序富集分析
- `paired strategy`：配对设计分析策略，比如同一受试者前后对比
- `covariate`：协变量
- `confounded`：混杂。比如批次和生物分组缠在一起，很难分清谁造成差异

### 2.2 机器评分常见术语

- `precision`：精确率。你报出来的阳性里，真正正确的占多少
- `recall`：召回率。真正应该找出来的东西里，你找到了多少
- `f1`：精确率和召回率的综合分
- `fpr` = false positive rate，这里代码里的定义更接近“预测阳性中的假阳性比例”
- `proxy`：代理指标。不能直接精确测量，就用一个近似指标代替
- `calibration`：校准。不是原始分直接拿来，而是再做一次非线性压缩/调整
- `parsimony`：简约性。能用少量必要步骤做完就别堆很多多余步骤
- `weakest-link penalty`：短板惩罚。某一项特别差，会拖累总分
- `gate`：门控因子。不是独立分数，而是一个乘数
- `audit`：审计记录。这里指模型是否显式写出了“观察到什么证据，因此选择什么动作”

---

## 3. 输入常见英文字段翻译

这部分主要来自 `src/planner/schema.py`。

### 3.1 `WorkflowPlan` 里的字段

- `workflow_name`：工作流名称
- `rationale`：整体理由，为什么这么设计流程
- `steps`：步骤列表
- `dataset_assessment`：模型对数据集的初步判断
- `decision_audit`：模型对关键决策点留下的审计记录
- `final_analysis_target`：最终分析目标
- `stop_conditions`：什么时候停止分析

### 3.2 每个步骤 `WorkflowStep`

- `tool`：用了哪个工具
- `inputs`：输入文件
- `params`：参数
- `purpose`：这一步的目的

### 3.3 `dataset_assessment`

- `detected_missingness`：是否检测到缺失值问题
- `detected_batch_risk`：是否检测到批次风险
- `detected_compositionality`：是否认为数据有组成型特征
- `recommended_input_matrix`：推荐后续分析使用哪类矩阵

### 3.4 `decision_audit` 里的字段

- `aspect`：正在审计哪个方面，比如 missingness、batch、post_de_followup
- `observed_evidence`：观察到的证据
- `judgment`：做出的判断
- `chosen_action`：最后选择的动作
- `rejected_actions`：考虑过但放弃的动作
- `confidence`：这次判断有多自信

---

## 4. 工具名都代表什么

这部分来自 `src/tools/registry.py`。

- `inspect_dataset`：检查数据形状、缺失、组成型特征、元数据可用性
- `impute_missing_values`：填补缺失值
- `clr_transform`：做 CLR 变换
- `check_batch_effect`：检测批次效应
- `run_combat`：ComBat 批次校正
- `run_ratio_combat`：比值式批次校正代理实现
- `run_percentile_norm`：分位数归一化式批次校正
- `run_limma_batch_removal`：用线性模型去除批次
- `run_harmony`：Harmony 风格批次校正
- `run_differential_expression`：做差异分析
- `run_motif_enrichment`：做 motif 富集分析
- `run_pca`：做 PCA

其中一组特殊工具叫 `BATCH_TOOLS`，即所有“批次校正工具”：

- `run_combat`
- `run_ratio_combat`
- `run_percentile_norm`
- `run_limma_batch_removal`
- `run_harmony`

评分代码里经常问“有没有 batch tool”，意思就是“有没有使用上述任何一种批次校正工具”。

---

## 5. 评分前会先做哪些基础处理

### 5.1 `_safe_unit_interval`

```text
_safe_unit_interval(x) = min(1, max(0, x))
```

意思：

- 把分数强行截到 `[0,1]`
- 如果是 `NaN`、`inf`、乱值，直接按 `0`

所以你可以把它理解成“保险丝”：任何分数都不会小于 0 或大于 1。

### 5.2 `_safe_nonnegative`

```text
_safe_nonnegative(x) = max(0, x)
```

意思：

- 只保证非负
- 但不一定限制在 1 以内

### 5.3 `_piecewise_score`

这是分段线性打分函数。

意思不是“达到阈值才给分”，而是：

- 先给几个锚点 `(x, y)`
- 中间区域做线性插值

它的作用是让分数随信号强度平滑变化，而不是突然跳变。

### 5.4 `_penalized_score`

```text
score = penalty_1 * penalty_2 * penalty_3 * ...
```

这不是“加法扣分”，而是“乘法惩罚”。

直观理解：

- 一个参数不合理，分数乘上一个小于 1 的系数
- 多个参数都不合理，就连续相乘
- 所以多个小问题叠加会越来越明显

---

## 6. `result_score`：结果分是怎么来的

这是最重要的一项，因为它直接看“你处理后的结果是不是更接近隐藏真值”。

结果分由 3 个子部分组成：

1. `de_score`：差异特征找回得如何
2. `bio_score`：生物结构保留得如何
3. `batch_score`：批次效应降低了多少

最后再做一次短板惩罚和校准。

### 6.1 `de_score`：差异分析找得准不准

先从 DE 结果表里找出：

- `significant == True` 的特征，作为预测结果 `pred`

再从 hidden truth 里拿出真正的差异特征 `gt`。

然后计算：

- `tp` = true positive，真正例，你找对的差异特征数量
- `fp` = false positive，假正例，你错报的差异特征数量
- `fn` = false negative，假负例，你漏掉的真实差异特征数量

再得到：

```text
precision = tp / (tp + fp)
recall = tp / (tp + fn)
f1 = 2 * precision * recall / (precision + recall)
```

最终：

```text
de_score = f1
```

也就是说，这个项目把“差异特征找回来”看得最重，直接用 `F1` 当主结果分量。

### 6.2 `batch_score`：批次效应有没有被削弱

代码会算：

- `pvca_batch_before`
- `pvca_batch_after`

你可以把它理解成“批次解释了多少方差”的代理量。

然后：

```text
batch_score = clamp(pvca_batch_before - pvca_batch_after, 0, 1)
```

意思：

- 处理后批次影响下降了，才加分
- 降得越多越好
- 如果处理后没改善，甚至更差，就不会给高分

### 6.3 `bio_score`：生物信号有没有被保住

它由两半组成。

#### `f_stat_corr_preservation`

代码比较处理前后、生物分组之间的方差比结构是否接近：

```text
f_stat_corr = max(0, 1 - |f_after - f_before| / max(|f_before|, 1e-12))
```

直观理解：

- 如果处理后还保留了原本的生物组间差异结构，这项高
- 如果批次校正把真正生物信号也洗掉了，这项会下降

#### `corr_structure_preservation`

代码会比较：

- 原始矩阵的 feature-feature 相关结构
- 处理后矩阵的 feature-feature 相关结构

如果两者相关矩阵整体仍然相似，这一项高。

#### 合并成 `bio_score`

```text
bio_score = clamp(0.5 * f_stat_corr + 0.5 * max(corr_struct_pres, 0), 0, 1)
```

意思：

- 一半看组间差异结构
- 一半看整体相关结构

### 6.4 三部分怎么加权

```text
base_result = 0.14 * batch_score + 0.21 * bio_score + 0.65 * de_score
```

权重解释很清楚：

- `de_score` 占 65%，最重要
- `bio_score` 占 21%
- `batch_score` 占 14%

也就是说，这个 benchmark 的价值观是：

- 最重要的是有没有恢复出真正差异特征
- 批次去除和生物保留是支持性证据，不是主目标本身

### 6.5 短板惩罚 `weakest-link`

```text
weakest = min(batch_score, bio_score, de_score)
result_precal = base_result * (0.48 + 0.52 * weakest)
```

意思：

- 如果三项里有一项特别差，总结果会被拖下去
- 即使平均看起来还行，出现明显短板也会受罚

这个乘子范围是 `[0.48, 1.0]`。

### 6.6 最后再做结果校准

```text
s = clamp(score, 0, 1)
s = s ** 1.38
if s > 0.72:
    s -= 0.32 * (s - 0.72) ** 1.4
```

白话解释：

- 不是简单原样输出
- 中低分会被稍微压一压
- 很高的分也再做一点压缩，避免“过早冲顶”

最终得到：

```text
result_score
```

---

## 7. `plan_score`：计划分在看什么

`plan_score` 不看你最后跑出来的数据结果，而是看“你设计的工作流本身像不像一个合理专家方案”。

它会对计划做很多检查项 `checks`，每项都在 `[0,1]`。

最后不是简单平均，而是：

```text
raw_mean = mean(checks)
weak = min(checks)
blended = 0.6 * raw_mean + 0.4 * weak
```

意思：

- 平均表现重要
- 最差那一项也很重要

然后再减去几种额外惩罚项，最后做 `plan` 专用校准。

### 7.1 `missing_addressed`

看你是否正确处理了缺失值。

这里依据 hidden truth 中的 `missing_decision_profile`：

- `avoid`：不该填补
- `borderline`：可填可不填，但填补更稳
- `required`：必须填补

对应直觉是：

- 本来不该填补，你填了，扣分
- 必须填补，你没填，严重扣分

### 7.2 `clr_before_de`

看你是否在 DE 之前做了 CLR。

如果 truth 认为需要 CLR：

- 在 DE 前做了 CLR，得 `1.0`
- 否则只有 `0.3`

这说明项目默认认为 glycomics 这类数据通常需要 compositional 处理。

### 7.3 `batch_before_de`

如果 truth 认为需要做批次校正，就检查：

- 有没有 batch tool
- 是否发生在 DE 之前

如果是 `borderline` 批次情形，且你虽然没直接校正，但先做了 `check_batch_effect`，会给一个中间分 `0.85`。

这反映的思想是：

- 边界情况不要求你必须立刻校正
- 但至少要先检查，而不是机械套模板

### 7.4 `batch_judgment`

这是“你对批次问题的判断本身是否合理”。

它看：

- 是否用了批次校正工具
- 是否先做了 `check_batch_effect`
- 是否用了推荐的 batch family
- 当前 truth 属于哪种 profile

常见 profile：

- `avoid`：根本不该做批次校正
- `borderline`：先检查比直接校正更合理
- `required`：需要批次校正
- `required_confounded`：不仅需要，而且属于比较复杂、混杂的高风险情况

这项分数是计划分里非常关键的一项，因为它体现“有没有按数据情况决策”，而不是“一律校正”或“一律不校正”。

### 7.5 `batch_family_hint`

如果 hidden truth 推荐某一类批次校正方法，就看你有没有选对家族。

比如：

- 推荐 `run_combat`，你确实用了，得分高
- 推荐某家族，你用了别的，扣分

如果是 `required_confounded` 场景，没选对会扣得更重。

### 7.6 `assessment_missing` / `assessment_batch` / `assessment_present`

这部分看你的 `dataset_assessment` 有没有对数据做初步判断。

如果有 assessment：

- 你判断的 missing/batch 风险与 truth 一致，得高分
- 判断错了，扣一点

如果压根没写 assessment：

- 给一个默认的 `assessment_present = 0.8`

也就是说，它鼓励模型先“看数据，再设计流程”。

### 7.7 `parsimony`

简约性分数，防止模型乱堆步骤。

代码先估算最小必要工具数：

```text
baseline = 2 + needs_clr + needs_imputation + needs_batch_correction
```

固定的 2 指：

- `inspect_dataset`
- `run_differential_expression`

然后：

```text
redundancy = max(0, len(tools) - baseline)
parsimony = max(0, 1 - 0.06 * redundancy)
```

意思：

- 多一个冗余步骤，减一点分
- 冗余越多，分越低

### 7.8 `param_quality`

这是参数质量分，不看“有没有这个步骤”，而看“这个步骤的参数像不像懂行的人会设的值”。

它对所有步骤逐一检查，把每个问题都变成一个乘法惩罚。

常见规则：

- `impute_missing_values.strategy` 不在推荐集合里，乘 `0.72`
- `clr_transform.pseudocount <= 0`，乘 `0.68`
- `pseudocount` 极小或过大，也会扣分
- `samples_are_rows` 与矩阵布局提示不一致，会扣分
- `run_differential_expression.alpha` 不合理，会扣分
- `alpha > 0.05` 也会逐步扣分
- `input_space` 不是 `auto/clr/raw/abundance`，乘 `0.9`
- `run_combat(use_bio_covariate=False)`，乘 `0.88`
- `run_pca.n_components` 太大或非正数，会扣分

这项很像“专家审稿人看参数设置是否靠谱”。

### 7.9 reasoning acknowledgement

这部分看你在文本解释里有没有意识到一些关键分析条件。

代码目前检查三类意识：

- `paired_acknowledgement`：是否意识到需要配对策略
- `motif_judgment`：是否正确判断要不要做 motif follow-up
- `confounding_awareness`：是否意识到存在混杂、需要保护 biology/covariate

注意：这部分不是看结果，而是看你有没有在 `rationale`、`workflow_name`、`final_analysis_target`、`stop_conditions` 这些文本里提到关键概念。

### 7.10 计划分额外惩罚项

除了上面的 check 之外，还有三种额外扣分。

#### `disallowed_hits`

如果 hidden truth 里明确说某些模式不允许，而你的步骤序列正则匹配上了，就每命中一次加 `0.25` 惩罚。

#### `template_penalty`

这是“反模板化惩罚”。

代码要打击的行为是：

- 数据根本不需要 impute，你还是固定加 impute
- 数据不需要 batch correction，你还是固定加 batch correction
- borderline 批次情形，不检查就直接矫正

也就是防止模型套“万能流水线”。

#### `structure_penalty`

```text
structure_penalty = 0.03 * redundancy
```

这是专门惩罚结构冗余的。

### 7.11 最后怎么合成 `plan_score`

```text
raw_plan_score = max(0, blended - disallowed_hits - template_penalty - structure_penalty)
plan_score = aggregate_process_score(raw_plan_score, profile="plan")
```

也就是说：

- 先综合所有检查项
- 再减模板化和冗余惩罚
- 再用 `plan` 专属校准函数做压缩

---

## 8. `execution_score`：执行分在看什么

这部分关注的是：你不只是“计划得像样”，而是真的按合理顺序把步骤执行出来了。

它主要看 6 件事：

- `order_ok`
- `necessary_tools_coverage`
- `params_reasonable`
- `trace_ok`
- `parsimony`
- `reasoning_acknowledged`

### 8.1 `order_ok`

看步骤顺序是否合理。

重点规则：

- 批次校正如果出现在 DE 后面，几乎直接判坏，`order_ok = 0`
- CLR 出现在 DE 后面，也会严重扣分
- 如果 truth 需要 imputation，但你把 impute 放在 CLR 后面，也会扣分

这体现的是典型分析逻辑：

- 缺失处理通常先于 CLR
- batch correction 和数据预处理通常先于 DE

### 8.2 `necessary_tools_coverage`

看“该做的关键步骤你有没有做”。

它主要只盯两类真正必要步骤：

- missingness 需要时有没有 impute
- batch correction 需要时有没有 batch tool

如果两类都需要，就把二者组合：

```text
necessary = 0.65 * min(parts) + 0.35 * mean(parts)
```

意思是：

- 最短板更重要
- 但也保留平均表现

### 8.3 `parsimony`

和计划分一样，也要惩罚冗余步骤。

此外还会特别惩罚一些“可选工具乱用”的情况：

- 明明不需要 batch correction，还跑 `check_batch_effect`
- 明明 motif follow-up 不值得做，却做了 `run_motif_enrichment`
- 可选工具过多，也会继续往下压

### 8.4 `extras_penalty`

这是执行阶段的附加惩罚。

例如：

- 工具总数太多
- 本应 `avoid` batch correction 却用了 batch tool
- borderline 批次情形下跳过检查直接矫正

### 8.5 `params_reasonable`

直接复用前面计划分中的 `_param_quality_score`。

意思是：

- 参数不合理，不只影响计划分
- 也影响执行分

### 8.6 `trace_ok`

这项看执行轨迹 `trace`。

规则很直白：

- 有 hard error，直接从 1 变 0
- 某步 `status != ok`，也会变 0
- 有 warning，则按 warning 数量继续乘法压低

所以它衡量的是“执行记录是否干净”。

### 8.7 `reasoning_acknowledged`

这是把前面 reasoning acknowledgement 的几个子项取平均，用于执行分。

### 8.8 执行分主体公式

```text
base_execution =
    0.25 * order_ok
  + 0.28 * necessary_tools_coverage
  + 0.10 * params_reasonable
  + 0.10 * trace_ok
  + 0.17 * parsimony
  + 0.10 * reasoning_acknowledged
```

可以看出权重最大的是：

- 顺序是否正确
- 必要步骤是否覆盖

这很合理，因为执行分本来就是在看流程是否真的跑对。

### 8.9 执行分的短板惩罚

```text
weakest = min(order_ok, necessary, param_ok, trace_ok, parsimony, reasoning_ok)
raw_execution = clamp((base_execution - extras_penalty) * (0.71 + 0.29 * weakest), 0, 1)
```

如果某项很差，总体还会被再拖一轮。

### 8.10 critical fail gate

执行分还有一个非常强的“硬门槛”。

只要出现以下任一情况：

- `order_ok < 0.99`
- `necessary < 0.70`
- `trace_ok < 0.99`
- 需要 batch correction 却没有 batch tool
- 需要 imputation 却没有 impute

就会：

```text
raw_execution = min(raw_execution, 0.55)
```

意思是：

- 关键执行条件失败时，执行分不允许高
- 即使别的部分看起来还行，也会被封顶

### 8.11 最终 `execution_score`

```text
execution_score = aggregate_process_score(raw_execution, profile="execution")
```

---

## 9. `decision_score`：决策分为什么单独存在

很多 benchmark 只看“流程像不像”，但这里单独加了 `decision_score`，目的是区分：

- 你是不是因为真的观察到数据现象才这么做
- 还是只是背了一个标准流程模板

它关注的是“判断质量”，不是纯执行质量。

### 9.1 `decision_missing_quality`

这个分不是看 hidden truth，而是看原始矩阵里的真实缺失比例：

```text
missing_fraction = NaN_count / total_cells
```

然后分三档：

- `required`：缺失比例 `> 0.03`
- `borderline`：`0 < missing_fraction <= 0.03`
- `avoid`：`== 0`

然后判断：

- 该 impute 时有没有 impute
- 不该 impute 时有没有乱 impute

这项体现的是“你对缺失问题的现场判断是否合理”。

### 9.2 `decision_batch_diagnostic_quality`

代码会从原始数据和 metadata 里估计一个：

```text
batch_signal = batch_signal_proxy(...)
```

它想表达的是“批次效应有多强”。

然后分成：

- `high`
- `borderline`
- `low`

这项不是看你有没有做 batch correction，而是看你有没有做“批次诊断”。

例如：

- 批次信号很高，却没做 `check_batch_effect`，这项就低
- 边界情况做了检查，这项就高

### 9.3 `decision_batch_action_quality`

这项看“面对当前批次信号，你采取的动作对不对”。

例如：

- 高 batch signal 却没做 batch tool，分很低
- 低 batch signal 还硬上 batch tool，也会低
- borderline 情况下，先检查再决定通常更好

所以可以把 9.2 和 9.3 理解为：

- 9.2 看你有没有先做诊断
- 9.3 看你诊断后做的动作是否匹配信号强度

### 9.4 `decision_post_de_quality`

看 DE 之后的 follow-up 合不合理。

代码目前主要盯 `run_motif_enrichment`：

- 如果 truth 认为 motif follow-up 值得做，你做了则高分
- 不值得做却做了，扣分

### 9.5 `decision_protocol_compliance`

看你是否遵守分析协议。

如果有 `decision_log`：

- 统计是否出现 `invalid_next_tool_for_stage`

如果没有 `decision_log`，就用静态线索估计：

- 第一工具是不是 `inspect_dataset`
- CLR 是否晚于 DE
- batch correction 是否晚于 DE
- trace warning 多不多
- decision audit 覆盖度够不够

所以这项可以理解为“分析过程是否守规矩”。

### 9.6 `decision_rationale_quality`

这是“你的解释文本有没有信息量”。

先用 `_text_specificity_score(...)` 看文本是否具体，而不是空话模板话。

它主要关心：

- 词汇是否足够具体
- 有没有命中预期术语
- 是否过于模板化

然后如果 `decision_log` 里还能找到和 batch 决策有关的 `rationale`，会进一步判断：

- 高 batch signal 时，是否提到 `batch / confound / preserve biology / covariate`
- borderline 时，是否提到 `check / diagnose / uncertain / verify`
- low 时，是否说明信号弱、可忽略

这项分数本质上是：“你说得像不像真的做了诊断，而不是事后瞎解释。”

### 9.7 四个 `decision_audit_*`

这部分鼓励模型在关键决策点留下结构化审计信息。

四项分别是：

- `decision_audit_missing_quality`
- `decision_audit_compositionality_quality`
- `decision_audit_batch_quality`
- `decision_audit_followup_quality`

每一项都检查：

- `observed_evidence` 里有没有证据词
- `chosen_action` 里有没有合理动作词
- `rejected_actions` 是否不是空的
- `confidence` 是否合理

如果缺少某个 audit，不会直接归零，但会给一个较低默认分 `0.35`。

这体现的是：

- 系统鼓励“写下你观察到了什么、为什么选这个动作”
- 但不会因为少写一项 audit 就让决策分彻底崩掉

### 9.8 决策分最后怎么聚合

决策分的 10 个部件是：

- `missing_quality`
- `batch_diagnostic_quality`
- `batch_action_quality`
- `post_de_quality`
- `protocol_compliance`
- `rationale_quality`
- `audit_missing_quality`
- `audit_comp_quality`
- `audit_batch_quality`
- `audit_followup_quality`

先算两个平均：

#### 调和平均 `hmean`

调和平均对低分特别敏感，适合强调短板。

#### 算术平均 `amean`

算术平均更稳定，不会被某一项过度打穿。

最后：

```text
raw_decision = 0.58 * hmean + 0.42 * amean
decision_score = aggregate_process_score(raw_decision, profile="decision")
```

这说明它的设计哲学是：

- 决策里的短板很重要
- 但又不希望某一个 audit 缺失把总分直接拖到极低

---

## 10. `outcome_alignment_gate`：这个 gate 到底在做什么

代码真实实现是：

```text
outcome_alignment_gate = 0.84 + 0.16 * sqrt(result_score)
```

它的性质：

- 当 `result_score = 0` 时，gate = `0.84`
- 当 `result_score = 1` 时，gate = `1.00`

白话解释：

- 过程分不会被结果分“一票否决”
- 但如果结果特别差，计划分/执行分/决策分最多只能保留到 84%
- 如果结果很好，gate 几乎不扣

这是一种“温和结果约束”。

注意：

- 代码里真实公式是上面这个平方根公式
- `run_benchmark.py` 里有旧文案写成 `0.38 + 0.62 * result_score`
- 真正执行时应以 `src/metrics/evaluator.py` 为准

---

## 11. `plan_valid` 惩罚是什么

在总评估函数 `evaluate_full(...)` 里，如果：

```text
plan_valid == False
```

则会先惩罚：

```text
plan_score *= 0.5
execution_score *= 0.5
decision_score *= 0.7
```

然后再乘 `outcome_alignment_gate`。

意思是：

- 计划本身无效时，计划分和执行分直接腰斩
- 决策分也会降，但稍微轻一点

这反映的逻辑是：

- 无效计划下谈执行和决策，本来就不应拿高分

---

## 12. 一张表看懂常见输出字段

### 12.1 顶层字段

- `plan_score`：最终计划分，已乘 `plan_valid` 惩罚和 `outcome_alignment_gate`
- `execution_score`：最终执行分，已乘相关惩罚和 gate
- `decision_score`：最终决策分，已乘相关惩罚和 gate
- `result_score`：最终结果分，不乘 gate
- `outcome_alignment_gate`：由结果分推导出的过程门控因子
- `plan_valid_penalty_applied`：是否触发了 `plan_valid=False` 惩罚

### 12.2 结果分明细字段

- `pvca_batch_variance_before`：处理前的批次方差代理值
- `pvca_batch_variance_after`：处理后的批次方差代理值
- `pvca_biological_variance_before`：处理前的生物方差代理值
- `pvca_biological_variance_after`：处理后的生物方差代理值
- `batch_dominance`：处理后批次信号相对生物信号的占优程度
- `de_precision`：差异特征精确率
- `de_recall`：差异特征召回率
- `de_f1`：差异特征 F1
- `de_fpr`：预测差异特征中的假阳性比例
- `f_stat_corr_preservation`：生物组间方差结构保留程度
- `corr_structure_preservation`：相关结构保留程度
- `batch_reduction_score`：批次削弱得分
- `bio_preservation_score`：生物结构保留得分
- `de_recovery_score`：差异恢复得分

### 12.3 计划分明细字段

- `plan_checks_detail`：所有计划检查项的明细字典
- `disallowed_hits`：命中禁止模式的惩罚
- `template_penalty`：模板化工作流惩罚
- `structure_penalty`：冗余结构惩罚

### 12.4 执行分明细字段

- `order_ok`：顺序是否正确
- `necessary_tools_coverage`：关键必要工具覆盖情况
- `params_reasonable`：参数是否合理
- `trace_ok`：执行轨迹是否干净
- `extras_penalty`：额外惩罚
- `parsimony`：执行简约性
- `reasoning_acknowledged`：是否承认关键推理要点
- `execution_gate_cap_applied`：是否触发执行分的 0.55 封顶门

### 12.5 决策分明细字段

- `decision_missing_quality`：缺失处理判断质量
- `decision_batch_diagnostic_quality`：批次诊断质量
- `decision_batch_action_quality`：批次动作选择质量
- `decision_post_de_quality`：DE 后 follow-up 判断质量
- `decision_protocol_compliance`：协议遵守度
- `decision_rationale_quality`：决策理由质量
- `decision_audit_missing_quality`：缺失问题 audit 质量
- `decision_audit_compositionality_quality`：组成型问题 audit 质量
- `decision_audit_batch_quality`：批次问题 audit 质量
- `decision_audit_followup_quality`：后续分析 audit 质量
- `observed_batch_signal_score`：从原始数据观察到的批次信号强度
- `observed_batch_signal_level`：批次信号等级，高/边界/低
- `observed_missing_fraction`：原始数据缺失比例

---

## 13. 这个评分体系的核心思想，用人话总结

如果把整个系统总结成几条原则，大概是这样：

### 原则 1：结果优先

最重要的是你有没有把真正差异特征找回来，所以 `result_score` 的核心权重给了 `DE F1`。

### 原则 2：不能只会套模板

如果数据不需要缺失填补、批次校正，你还固定加这些步骤，会被 `template_penalty` 和各类判断项扣分。

### 原则 3：短板会拖总分

无论是结果分、计划分、执行分还是决策分，都不是“平均一下就完了”，而是专门设计了对最低项敏感的机制。

### 原则 4：解释和审计也算分

这个 benchmark 不只看动作，还看：

- 你有没有先观察数据
- 有没有留下判断证据
- 有没有写清为什么这么做

### 原则 5：过程分不能脱离结果

如果结果很差，`outcome_alignment_gate` 会把过程分压下来，避免出现“写得像专家，结果却很糟，但总分仍然很高”的情况。

---

## 14. 如果你只想最快看懂，记住下面这 8 句就够了

1. `result_score` 看最终结果，最重要。
2. `plan_score` 看工作流设计得像不像合理方案。
3. `execution_score` 看步骤顺序、关键步骤、轨迹和参数是否真的执行对了。
4. `decision_score` 看你是不是根据数据证据做判断，而不是死背模板。
5. `DE F1` 是结果分中权重最大的部分，占 65%。
6. 批次校正不是“做了就加分”，而是“该做时做、不该做时别做、边界情况先检查”。
7. 多余步骤、模板化流程、不合理参数，都会被罚。
8. 即使过程写得漂亮，只要最终结果差，`outcome_alignment_gate` 也会压低过程分。

---

## 15. 最实用的阅读顺序

如果你之后还要继续看原始代码，建议按这个顺序读：

1. 先看 `src/planner/schema.py`
   目的是先搞懂 plan 里有哪些字段。
2. 再看 `src/tools/registry.py`
   目的是知道每个工具名在干什么。
3. 再看 `src/metrics/evaluator.py` 中的 `_result_metrics`
   先理解结果分，因为它最核心。
4. 再看 `compute_plan_score`
   理解计划检查项。
5. 再看 `compute_execution_score`
   理解顺序、轨迹、必要步骤。
6. 最后看 `compute_decision_score`
   这部分最细，也最像“评审老师在看你是不是认真思考过”。

如果你需要，我下一步还可以继续帮你做两件事中的任意一种：

- 按“一个真实案例”带你手算一遍这四个分数
- 把 `src/metrics/evaluator.py` 逐段加中文注释版解释出来
