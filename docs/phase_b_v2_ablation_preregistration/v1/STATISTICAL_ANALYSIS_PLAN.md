# 统计分析预注册提案

这是2024开发性探索计划，PROPOSED_FOR_RESEARCHER_APPROVAL。未来完整数据身份、缺失性、每seed结果和协议偏离都要公开说明。单次Git留痕不等于独立确认性预注册已通过。

## 配对与主效应

对每模型m、每seed s分别计算以下两个效应（排版公式见数学附录）。

H-O：D_O(m,s)=Brier(E1,m,s)−Brier(E0,m,s)。

H-Q：D_Q(m,s)=M32(E2,m,s)−M32(E0,m,s)。

两个主假设各在B0和B1报告，形成4个拟议主比较。发生和条件副作用同时呈现。先列3个seed的点值和效果，再给三个D的等权算术平均、范围和描述性标准差；n_seed=3不足稳定估计随机性，不用3seed的分布作强确认结论。

不要把各seed的预测平均成ensemble再替代单模型终点；M32为非线性量，须每seed先取abs(C−tau)再求等权效应平均，不先平均coverage后取abs。相同seed所有模型/条件共用配对样本和初始化身份。同条件B1−B0也报告；探索性差中差为D_O(B1,s)−D_O(B0,s)、D_Q(B1,s)−D_Q(B0,s)，仅交互迹象，不升为批准的确认主检验。

seed×像元不是独立重复，同样的天气/标签被多个seed观察。训练随机性与日期变异分别说明；不展平为数亿独立证据，不将同一周各像元独立bootstrap。

## 日期块Bootstrap

拟继承35个非重叠7日UTC日期块，自2024-03-01至10-31（245日，按标签window_start归块），2,000次、bootstrap seed=2026、每次有放回抽35块。相同multiplicity向量同时作用于18个运行，保留所有臂/seed/时相的同一天气配对；本轮未生成新抽样文件或推理统计。

每replicate先按重复次数pool各块损失分子与N_valid/N_rain，再求ratio；不能等权平均周metric。Coverage分子计整数，CPB用unweighted qr；AUROC/AP从合并exact score counts重算，不能平均各周AUC/AP。每replicate先求每seed的D，再等权汇总D；2.5/97.5百分位作为点对点95%探索区间，不表示seed随机总体置信区间。

某replicate无雨或缺某强雨层/某类别时相关指标为NA，报告有效replicate数及原因，不补0、不一直重抽直到满足条件、不隐藏稀疏层。主指标/guardrail最低有效块数和最低可用replicate比例为NOT_YET_ESTABLISHED，批准前需决定；任何未达门槛项不可声称科学通过。

七日近似独立仍可能被跨周天气过程打破；季节非平稳使混合季节重采样不代表稳定同分布。只有一年且2024已参与历史BEST和多轮诊断，日期块区间不能变成全新独立确认集，也不保证未来年份或极端天气表现。不同块长或季节分层bootstrap若增加，只能执行前另批敏感性计划，不能看区间是否有利后选择。

## 多重比较与功效待决

|候选|作用与依赖|限制/待批准|
|---|---|---|
|M-A：4主比较Holm|若未来批准了有效的raw p值构造，可控制该家庭的FWER|原percentile区间不是p值；本轮不凭CI倒推p、不声称已控制错误率|
|M-B：配对最大统计量同时区间|共用块抽样可保留比较相关；需批准studentization、零方差及NA处理|近似块独立等前提仍不足确认；本轮未实现|
|M-C：仅效果/点对点探索区间|透明报告4主比较和全部guardrails，不作显著性或确认通过判决|多次选择风险仍在；主张范围严格限制|

multiple_comparison_method及相应raw_p_construction/interval_family均为NOT_YET_ESTABLISHED，本轮不自动选择Holm。辅助32coverage、各层CPB、尾分布和交互属于完整安全描述，不按显著性选择展示；若需作为正式成功检验，必须预声明其家庭及联合判据。

minimum_effect、guardrail_tolerances、event_effective_sample_size、statistical_power均NOT_YET_ESTABLISHED。既有大量暴露或3seed不证明足够功效，不能捏造detectable effect、p值或保证改善。科学界限应从用途/物理代价与测量误差决定，不以历史E0/E1/E2表现反算，因为新实验根本尚未执行。缺这些字段的提案可完整供审阅，却不能升级为批准协议或宣布科学成功。

## 分析锁定与报告

先由研究者批准版本和源码身份，再执行；分析只使用预声明epoch9及共同集合。每个seed包括所有臂、失败/恢复/未完成状态，不选择最好的seed。两阶段若只完成2026，则明确n_seed=1；阶段2是否执行必须单独授权，若依据第一阶段模型表现决定不完成，披露该选择过程。任何变更形成新版本/偏离记录，旧版与旧结果不覆盖。未来正文严格区分新实测、探索解释与未验证机理假说。
