# Methods 与 Experimental Design 初稿框架

中文可编辑初稿；目标期刊与英文投稿稿尚未决定。标记规则：COMPLETED 只引用已发表 Phase-A 事实；PROPOSED/NOT_EXECUTED 为候选；HYPOTHESIS 为待检验解释；EXPECTED_PATTERN 表示用于否证的可能方向，不是已测结果。没有新 Results、没有新增指标数值。

## Methods 1：研究域、目标与时间语义（COMPLETED）

本研究以云南复杂地形的近实时降水反演为目标，使用静止卫星B13亮温观测预测降雨发生概率及有雨条件下降水强度分位数。输入原生501×501格网映射至100×100目标格网，研究评价限制在冻结云南中心入界mask的3,430个格点。模型卷积保留周边上下文；区域外输出不用于云南主评价。SP04映射和mask版本身份来自冻结科学合同，不能按预测误差重选。

IMERG V07 Final提供半小时窗口[T,T+30min)参考平均雨强，单位mm/h；分析时刻A=T+30min。B1使用A之前六个十分钟nominal时隙，A−60至A−10min，按旧到新输入；实际obs_end须≤A。B0使用相同场景的最新合资格时隙。这一观测因果约束并不证明历史业务传输可用性；因此文稿将“近实时”作为研究目标，避免声称已完成业务延迟验证。IMERG是多源融合参考，且Final带GPCC月尺度调整，不是独立地面真值。[NASA IMERG说明](https://gpm.nasa.gov/data/imerg)

## Methods 2：资格、分割和归一化（COMPLETED）

Phase-A按冻结M1严格六帧完整交集配对，2023三月至十月Train共10,455场景，2024同期Validation共10,501场景；2025最终测试仍封存。两模型使用同一目标、资格和scaler。亮温归一化使用2023 shared统计mean=271.60515414265217K、std=19.93959597783802K，不在2024拟合；normalization SHA见协议候选。场景是时空采样单位，36,018,430有效场景像元暴露及4,496,600参考有雨暴露不是同等数量独立事件。

## Methods 3：配对v2模型与双头（COMPLETED）

B0-Matched-v2和B1-v2沿用48/96/192/256通道主要骨干与SP04输出网格；只有1帧与6帧输入形状不同，参数数分别4,329,410与4,331,810。发生头输出一个logit与sigmoid概率。条件头先输出33 raw通道，由32个正allocation和一个正span形成32个严格递增qlog，定义在log1p(mm/h)域，tau_i=(i−0.5)/32。参数化公式及finite/支撑/次序守卫见冻结head；没有输出排序或推理clamp。q32的tau=.984375是条件覆盖目标，不是单次极端降水概率或确定性预报。

## Methods 4：损失与优化（COMPLETED）

设z=1[y>float32(0.1)]，u=log1p(y)。发生focal alpha=.5、gamma=2；pinball rho_tau(e)=e×(tau−1[e<0])。S_occ为所有有效云南暴露的发生loss之和，S_qr为参考有雨暴露上32tau平均pinball之和。训练core=(S_occ+S_qr)/N_valid；科学报告conditional Pinball=S_qr/N_rain，两者分母不同。条件分位数只在参考有雨位置直接监督，干位tail风险解释仍属假设。

Phase-A使用AdamW，基础LR=1e−4、最低LR=1e−6，Conv2d.weight decay=1e−4，gradient clip=5；物理batch=2，每epoch5,228updates，seed2026配对fresh，同形状参数拷贝。一个epoch warmup之后使用固定50epoch cosine horizon，max50epoch，原core早停patience8、min_delta=1e−4。BF16 forward、FP32参数/raw头、FP64量化参数化与pinball；TF32关闭。未来投稿的精确硬件、包版本与run identity应引用历史环境文件，不填猜测设备。checkpoint只能在完成训练与验证epoch边界形成；恢复需独立审批。

## Methods 5：评价与不确定性（COMPLETED）

报告global core、Brier、AUROC、Average Precision、参考有雨conditional Pinball和所有32分位数覆盖。Brier衡量整体概率误差，AUROC/AP衡量排序区分，可靠性箱比较平均预测概率与参考雨频率；三类不能互换。覆盖分母是参考有雨暴露，指标均基于2024开发验证。原paired bootstrap采用35个不重叠七日UTC块、2,000抽样、seed2026，同一配对场景和block权重；按分子/分母pooling，AUROC/AP按合并分数分布处理ties。点态百分位区间未修正多重比较、BEST选择和训练seed方差；天气系统跨块和季节性相关仍可能存在。

## Experimental Design 1：已完成配对实验（COMPLETED）

两模型BEST均为epoch9。已发表2024指标如下，仅用于叙述实验背景。

|指标|B0-Matched-v2|B1-v2|口径|
|---|---|---|---|
|Core Loss|0.048759608|0.047816404|log域loss，每有效暴露|
|Brier Score|0.096867626|0.095253471|发生概率误差，全部有效暴露|
|AUROC|0.886357037|0.893468822|发生排序，全部有效暴露|
|Average Precision|0.567232691|0.585904924|发生排序，全部有效暴露|
|Conditional Pinball|0.124885458|0.124113223|log域，参考有雨暴露|

该结果支持六时相在开发集合上的部分发生指标改善；不支持全部雨强、季节或未来年份全面优越。conditional Pinball配对探索区间跨零，强雨层B1点值更高。q32的欠覆盖与干参考位置巨大尾部为下一阶段待检验问题，尚未经独立量器或雷达证实。

## Experimental Design 2：拟议机制消融（PROPOSED / NOT_EXECUTED）

候选固定D1配对集合、fresh初始化、同一scaler/预算/scheduler/评价，只在E1改变focal gamma，在E2改变conditional loss固定权重；E0为同预算重新训练对照。多seed、干span正则化、交互臂与post-hoc校准属于另行批准的扩展。Methods原文不能随候选讨论偷偷改成“采用了gamma=0”或“进行了温度缩放”。

HYPOTHESIS：loss形态可能影响发生校准；量化项相对权重可能影响上尾覆盖；缺少干位直接量化监督与reference错配可能参与异常。EXPECTED_PATTERN：若假设成立，特定主终点可能改善，但排序、conditional Pinball或其它覆盖可能恶化；失败方向同样可报告。没有任何预期提升数字、显著性声明或最优参数。

## Experimental Design 3：拟议独立物理验证与最终拟合（PROPOSED / NOT_EXECUTED）

计划先确认雨量站、雷达QPE和其它主动观测的时间支撑、QC、许可及共享源链，再按预注册资格和冻结格网配对。点站、雷达足迹、半小时平均的支撑差异需单列，不能将小时量均分或相加quantile。独立性不明的融合场仅作辅助；已知2024个案与完整参考集合的用途分开。

如未来选择F1，以合资格2023/2024合并训练后，2024不再用作独立验证；最终2025测试必须另行解封批准。本轮尚无新的v2 Phase-B正式协议、runner、参数更新、reference数据或FinalFit结果。

## Reproducibility / Governance 文稿保留段

Phase-A结果与源文件有Git/SHA证据；B1从epoch14 LAST的历史恢复存在独立研究者恢复审批不足，BEST9早于该恢复段，但技术可追溯性不等同研究者批准。正式科学验收与历史偏差处置仍待决定；本稿不得声称恢复已经追认。公开仓库仅包括允许公开的代码、聚合证据和候选文档，不含原始卫星/站点资料、权重、optimizer或访问凭据。

证据导航：[原验收材料](../../v2_scientific_acceptance/README.md)、[已完成补强](../../phase_a_evidence_hardening/README.md)、本版本manifest与Git发布收据。候选报告构建和合成计划测试不作为正式模型实验通过记录。
