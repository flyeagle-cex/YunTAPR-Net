# 主指标与安全评价

PROPOSED_FOR_RESEARCHER_APPROVAL。所有新指标结果NOT_EXECUTED；效应大小和副作用容忍值NOT_YET_ESTABLISHED。遵循已有source_identity中的v2验证与科学observer口径，不按新成绩选择指标、分箱或集合。

## 固定评价域与分母

2024冻结10,501场景，云南有效暴露36,018,430、真实有雨暴露4,496,600来自历史发表统计，是复用集合的拟定核对值，未来身份/QC不符即停。发生指标针对全部valid云南暴露；conditional指标仅float32 y>float32(.1)的valid暴露。暴露不等于独立事件。季节/月/民用昼夜代理及真值分层若呈现，继承原定义并标明探索。

|量|定义与单位|角色|
|---|---|---|
|Brier|sum_valid(p−z)^2/N_valid，无量纲|H-O主指标；H-Q发生安全评价|
|可靠性十箱|[k/10,(k+1)/10)，最后含1；n、sum(p)/n、sum(z)/n|发生校准描述；空箱为NA，不填0|
|AUROC|exact equal-score分组ROC，ties半计，无量纲|排序安全评价；单类NA|
|AP|exact equal-score组末non-interpolated precision积分|排序安全评价；无正例NA|
|共同Core|gamma2/alpha.5的FP64 focal分子加unweighted Pinball分子，再/N_valid|三臂可比辅助，不选BEST|
|Conditional Pinball|sum_rain_valid mean_32 rho_tau(log1p(y)−qlog)/N_rain|H-Q分布质量及H-O副作用；log1p(mm/h)域|
|C_i|sum_rain_valid 1[log1p(y)≤q_i]/N_rain，全部32tau|覆盖，等值计入；无雨NA|
|M32|abs(C32−0.984375)|H-Q主指标，比例；Δ<0方向改善|
|带符号偏差|C_i−tau_i及C32(E2)−C32(E0)|区分欠/过覆盖，不能仅看coverage上升|

Brier混合了概率误差的多个方面，AUROC/AP只关乎排序，十箱也会受箱内异质性和稀疏性影响。不能用其中一个替代所有评价。概率阈值分类POD/FAR/CSI未冻结，本轮不引入。BF16发生分数沿历史exact-score约定，不能粗十箱近似AUROC/AP或遇到非BF16时静默round。

## H-Q必须同时呈现的分布与真值层

真值层固定(0.1,1]、(1,5]、(5,10]、(10,20]、(20,30]、(30,50]、(50,inf)，以原float32标签和边界语义分层，各层报告N_rain及Conditional Pinball。>5 mm/h四个以上强雨层不得因为样本少或表现不利而删除；无暴露为NA。全32覆盖同时报告，不能只挑q32。

上尾阈值继承10、50、100、500、1000 mm/h，使用q32_log>log1p(threshold)比较，避免不必要的物理expm1溢出。计数范围为全valid云南场景-像元，并分真值干/雨；另外给跨场景去重格点数、涉及场景数。阈值是已声明诊断阈值，不是独立极端事件定义，也不是确定性暴雨预测。N_valid固定，比较原始计数及count/N_valid。

候选分布摘要：q27–q32（原高组tau>.8）与q32−q1宽度，以及span_log_derived=q32_log−log1p(.1)，分别在全valid、dry、rainy域报告n/min/median/p90/p99/p99.9/max；empirical quantile用r=(n−1)p、相邻order statistics线性插值（Type7）。span是由输出反推的FP64对数跨度，受浮点回减舍入，不称未舍入raw span；不是物理mm/h。qlog摘要为主，只有在安全显式转换时附物理单位；转换不可用则NA加风险原因，禁止cap或修补。

摘要方式是新增候选诊断规格，需要批准和以后工程化；确切统计需要临时排序/存储预算，不能宣称现observer已提供。原每forward最大值的p99/p99.9继续作为逐epoch工程诊断，必须标明它是“forward最大值分布”，与上述“像元暴露分布”不同。本轮不运行任何observer。

## 成功与副作用门槛

H-O建议联合：Brier配对改善达到最小意义差值，同时AUROC/AP下降不超过容忍值、CPB及强雨层变化不越界，完整箱暴露/QC未改变。H-Q建议联合：M32配对下降达到意义差值、CPB及强雨层不恶化超过容忍值、发生指标不越界，并检查宽度/span与尾计数；不能将极宽分布导致coverage接近目标判为成功。

门槛字段全部未定：minimum_brier_improvement、minimum_abs_q32_error_reduction、maximum_cpb_degradation、maximum_strong_rain_cpb_degradation_by_bin、maximum_brier_degradation_HQ、maximum_AUROC_AP_drop、tail_distribution_acceptance_rule。字段单位、各模型与seed汇总规则都须预先批准；未批准时只能报告方向、数值和探索区间，不出“成功/失败”的科学判决。数值安全守卫与这些科学容忍值不同：非有限、支持/严格序丢失等直接停止，不等待效果门槛。

“物理可信”不能只凭IMERG内部比较判定；独立参考验证仍是另一路未批准工作。p×q32不是均值，p×mean(32physical q)只是历史诊断proxy，不纳入本轮主指标。
