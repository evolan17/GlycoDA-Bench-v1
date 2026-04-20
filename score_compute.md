把旧的评分系统，从：

+  4 个总分 
+  每个总分下很多连续子项 
+  再做 shortest-link / calibration / gate 

改成：

+ **11 个并列方面分数**
+  每个方面由若干子项组成 
+  子项按关键程度分级 
+  子项先离散打档 
+  方面再输出为 `1 / 0.5 / 0`

最后报告中直接展示这 11 个方面分数，不再生成四大总分。

---

# 二、最终保留的 11 个方面分数
这 11 个是最终版本，不再额外汇总。

## A. 流程与方法设计类
1. `core_workflow_correctness`
2. `case_awareness`
3. `parameter_soundness`
4. `workflow_economy`

## B. 判断与解释类
1. `diagnostic_reasoning`
2. `action_selection`
3. `audit_closure`

## C. 结果质量类
1. `de_set_recovery`
2. `de_ranking_quality`**（新增）**
3. `batch_removal_quality`
4. `biological_signal_preservation`

其中，**新增的方面**只有 1 个是完全新增的结果维度名称：  
`de_ranking_quality`

但为了实现这些方面，下面还会引入一些**新增子项**，我会明确标出来。

---

# 三、哪些旧分数/旧机制删除
Cursor 需要直接删除或停用下面这些旧聚合机制：

## 1. 删除四大总分最终输出
不再输出：

+ `plan_score`
+ `execution_score`
+ `decision_score`
+ `result_score`

它们可以内部暂时保留用于兼容，但**最终评测结果不要再以这四个为主**。

## 2. 删除 `result_score` 的总聚合
旧的：

+ `base_result = 0.14*batch + 0.21*bio + 0.65*de`
+  再乘 `weakest-link`
+  再做 `outcome_calibration`

这一整段不要再作为主输出。

## 3. 删除 `outcome_alignment_gate`
旧的：

$ 0.84+0.16result_score
​ $

这个 gate 会把过程分再压一层，但压缩很温和，既会混淆“过程能力”和“结果能力”，也不利于你想要的区分度。

## 4. 删除 process calibration
包括 plan / execution / decision 的 profile-specific calibration，不再作为最终评分必经步骤。旧体系里这些校准本身就会进一步压缩差异。

## 5. 删除参数质量的乘法惩罚
旧的：

$  $



不要再用。这个机制会把多个小问题机械叠加，不够公平。

## 6. 删除 audit 缺失默认保底 0.35
旧体系里 audit 缺失直接给 0.35。这个太宽松，会抬高很多模型的底分。

---

# 四、评分总原则
## 1. 子项分三级关键程度
### A 类：致命关键项
打分：`1 / 0`

### B 类：强关键项
打分：`1 / 0.5 / 0`

### C 类：普通项
打分：`1 / 0.75 / 0.5 / 0`

## 2. 方面分计算规则
每个方面分两步：

### 第一步：A 类 gate
如果该方面中任一 A 类子项 = 0，  
则该方面分数直接 = `0`

### 第二步：规则式计数
否则，不做加权平均。

+ 若大多数子项处于高档：`1`
+ 若至少一半左右子项处于中档或以上：`0.5`
+ 否则：`0`

## 3. 最终输出
最终每个 case、每个模型只输出 11 个方面分数，取值为：

+ `1`
+ `0.5`
+ `0`

不再输出总分作为主结论。

---

# 五、11 个方面的最终定义
下面是 Cursor 需要实现的核心。

---

## 1. `core_workflow_correctness`
### 含义
核心流程有没有犯硬错误。

### 对应旧子项
+ `missing_addressed`
+ `clr_before_de`
+ `batch_before_de`

这些都来自旧 plan / execution 逻辑。旧体系本来就把这类顺序和关键步骤看得很重。 

### 子项与等级
+ `missing_required_and_done`：A 
+ `clr_required_and_before_de`：A 
+ `batch_required_and_before_de`：A 

### 评分
+  所有 required 核心约束都满足：`1`
+  任一 required 核心约束失败：`0`

### 说明
这个方面**不设 0.5**。

---

## 2. `case_awareness`
### 含义
模型有没有根据 case 条件做判断，而不是套模板。

### 对应旧子项
+ `batch_judgment`
+ `assessment_missing`
+ `assessment_batch`
+  reasoning acknowledgement 里的 compositionality / confounding awareness 

### 子项与等级
+ `missing_case_judgment`：B 
+ `batch_case_judgment`：B 
+ `compositionality_awareness`：B **（新增子项）**
+ `confounding_awareness`：B 

### 评分规则
+  明确识别 missingness / batch / compositionality / confounding，并与 truth 一致：`1`
+  只识别了一部分，或方向对但不完整：`0.5`
+  明显模板化，或判断错误：`0`

### 这里的新增子项
`compositionality_awareness` 是**新增子项**。  
旧系统没有把它单独拉成一个明确评分子项，只是间接通过 CLR 相关规则体现。

---

## 3. `parameter_soundness`
### 含义
参数设置是否合法、是否科学合理。

### 对应旧子项
旧 `param_quality` 的内容，但**不再用乘法惩罚**。

### 子项与等级
+ `parameter_legality`：A **（新增子项）**
+ `parameter_reasonableness`：C 
+ `method_specific_settings`：C **（新增子项）**

### 评分规则
+  `parameter_legality = 0`：该方面直接 `0`
+  否则再看：
+  `parameter_reasonableness`
+  `method_specific_settings`
+  两个都好：`1`
+  只要不是两个都好、也不是两个都差：`0.5`
+  两个都差：`0`

### 这里的新增子项
+ `parameter_legality`：**新增**
+ `method_specific_settings`：**新增**

旧系统没有把“参数合法”和“参数合理但不优”明确拆开。

---

## 4. `workflow_economy`
### 含义
流程是否简洁，不冗余，不模板堆砌。

### 对应旧子项
+ `parsimony`
+  template penalty 
+  structure penalty 

### 子项与等级
+ `redundancy_level`：C **（新增子项）**
+ `unnecessary_tool_usage`：C **（新增子项）**
+ `template_stacking`：C **（新增子项）**

### 评分规则
+  看三个子项：
+  `redundancy_level`
+  `unnecessary_tool_usage`
+  `template_stacking`
+  三个都好：`1`
+  至少两个不差：`0.5`
+  明显模板化或多项冗余：`0`

### 这里的新增子项
这三个都算**新增子项**，因为旧系统只是用线性 penalty 打进去，没有明确拆分。

---

## 5. `diagnostic_reasoning`
### 含义
模型有没有真正做“诊断”，而不是只给动作。

### 对应旧子项
+ `decision_missing_quality`
+ `decision_batch_diagnostic_quality`
+  decision rationale 中与证据相关的部分 

### 子项与等级
+ `missingness_diagnosis_quality`：B 
+ `batch_diagnosis_quality`：B 
+ `risk_stratification_quality`：C **（新增子项）**
+ `evidence_specificity`：C **（新增子项）**

### 评分规则
+  4 个子项分别离散
+  3 个及以上达到高档：`1`
+  至少 2 个达到中档：`0.5`
+  否则：`0`

### 这里的新增子项
+ `risk_stratification_quality`：**新增**
+ `evidence_specificity`：**新增**

---

## 6. `action_selection`
### 含义
诊断之后，选的动作是否对。

### 对应旧子项
+ `decision_batch_action_quality`
+ `decision_post_de_quality`
+ `decision_protocol_compliance`
+  missingness action 部分 

### 子项与等级
+ `protocol_compliance`：A 
+ `missingness_action_quality`：B **（新增子项）**
+ `batch_action_quality`：B 
+ `followup_action_quality`：C **（新增子项）**

### 评分规则
+  `protocol_compliance = 0`：直接 `0`
+  否则看另外三个子项：
+  `missingness_action_quality`
+  `batch_action_quality`
+  `followup_action_quality`
+  三个都好：`1`
+  至少两个可接受：`0.5`
+  否则：`0`

### 这里的新增子项
+ `missingness_action_quality`：**新增**
+ `followup_action_quality`：**新增**

旧系统里 follow-up 有，但没有以你现在这种并列方面体系明确单列。

---

## 7. `audit_closure`
### 含义
证据—判断—动作闭环是否完整。

### 对应旧子项
旧的 `decision_audit_*_quality`，但**不再使用旧公式**。旧公式会按 evidence_hits、chosen_hits、rejected_bonus、confidence 线性加权，而且 audit 缺失还有 0.35 保底。

### 新子项与等级
对每个 audit 方面都检查四件事：

+ `has_observed_evidence`
+ `has_judgment`
+ `has_chosen_action`
+ `has_rejected_alternatives_or_risk_note`

这些都算 C 类。  
然后对 missing / compositionality / batch / followup 四个 audit aspect 分别判断，再汇总。

### 评分规则
+  每个 audit aspect 内部：
+  四要素全齐：`1`
+  至少 2 个：`0.5`
+  否则：`0`
+  总 `audit_closure`：
+  大多数方面高档：`1`
+  至少一半中档或以上：`0.5`
+  否则：`0`

### 这里的新增子项
上面 4 个闭环要素都算**新增子项**。  
你是从“关键词命中评分”改成“结构闭环评分”。

---

## 8. `de_set_recovery`
### 含义
最终显著特征集合恢复得怎么样。

### 对应旧子项
旧 `de_score = F1`。这个保留，因为 hidden truth 下用 F1 测集合恢复是合理的。

### 子项与等级
+ `de_f1_bucketed`：B 

### 评分规则
建议先用这组阈值：

+ `F1 >= 0.80` → `1`
+ `0.50 <= F1 < 0.80` → `0.5`
+ `F1 < 0.50` → `0`

若你重跑后发现整体太难，再改成：

+ `>= 0.70` → `1`
+ `0.35 ~ 0.69` → `0.5`
+ `< 0.35` → `0`

### 这里没有新增
这项不是新增，只是从连续分改为分档。

---

## 9. `de_ranking_quality`
### 含义
模型把真正差异特征排在前面的能力。

### 这是新增方面
旧系统没有这一项，F1 完全不看排序。

### 推荐实现
优先顺序：

#### 方案 A
如果 DE 结果表里有连续显著性或统计量：

+  用 `adj_p` 升序，或 `-log10(adj_p)` 降序 
+  以 hidden truth 的 `gt` 为正类 
+  计算 `average_precision`

#### 方案 B
如果实现 A 麻烦，就用：

+ `top_10_overlap`
+ `top_20_overlap`

### 子项与等级
+ `de_average_precision`：B **（新增子项）**  
或 
+ `de_topk_overlap`：B **（新增子项）**

### 评分规则
若用 AP：

+ `AP >= 0.75` → `1`
+ `0.40 <= AP < 0.75` → `0.5`
+ `< 0.40` → `0`

若用 top-k：

+  高 overlap → `1`
+  中等 → `0.5`
+  低 → `0`

### 这里的新增子项
+ `de_average_precision`：**新增**  
或 
+ `de_topk_overlap`：**新增**

---

## 10. `batch_removal_quality`
### 含义
batch 是否被合理削弱，而不是只看降幅。

### 对应旧子项
旧 `batch_score = clamp(before-after,0,1)` 只看 batch proxy 是否下降。

### 新子项与等级
+ `batch_reduction_magnitude`：B 
+ `batch_case_match`：B **（新增子项）**
+ `overcorrection_flag`：A **（新增子项）**

### 评分规则
+  batch 应该处理且被明显削弱，且无明显过校正：`1`
+  有改善但一般，或 borderline case 只做到部分合理：`0.5`
+  无改善、反而更差、或出现明显过校正：`0`

### 这里的新增子项
+ `batch_case_match`：**新增**
+ `overcorrection_flag`：**新增**

---

## 11. `biological_signal_preservation`
### 含义
生物信号有没有被保住。

### 对应旧子项
旧 `bio_score` 用：

+ `f_stat_corr`
+ `corr_struct_pres`  
两者各占 0.5。 

### 为什么要改
旧 `bio_score` 最大问题是：它更像在看“proc 像不像 raw”，而不是“是否更接近真实 biological truth”。如果 raw 本身含技术伪影，这不公平。

### 新子项与等级
+ `bio_truth_retention`：B **（新增子项）**
+ `bio_structure_preservation`：C 
+ `bio_group_separation_preservation`：B **（新增子项）**

### 推荐实现
#### `bio_truth_retention`
如果 truth 里有真实差异特征和方向，优先用：

+  gt features 的 effect 方向和强度在处理后是否保住 

如果暂时做不到，就先用更弱代理：

+  处理后 gt features 与 non-gt features 的 separation 是否仍明显 

#### `bio_structure_preservation`
保留旧 `corr_struct_pres`，但降为辅助项。

#### `bio_group_separation_preservation`
替代旧 `f_stat_corr`。  
不要再用“与 raw 的方差比接近度”，改成更直接的：

+  biological groups 在处理后是否仍能分开  
例如： 
+  silhouette on bio label 
+  组间/组内距离比 
+  variance explained by bio label 

### 评分规则
+  生物信号保留良好：`1`
+  部分保留：`0.5`
+  明显损伤：`0`

### 这里的新增子项
+ `bio_truth_retention`：**新增**
+ `bio_group_separation_preservation`：**新增**
