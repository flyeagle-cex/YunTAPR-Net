# v2 paired Phase-A 科学验收证据包

研究者科学批准仍待定；本材料不批准 Phase-B。

|指标|B0-Matched-v2|B1-v2|B1−B0|相对 B0|配对差异 95% 探索区间|
|---|---:|---:|---:|---:|---:|
|Core_loss|0.0487596076194|0.0478164042666|-0.000943203352734|-1.9344%|[-0.00143966598285, -0.000484231515629]|
|Brier|0.0968676263395|0.0952534705091|-0.0016141558304|-1.6664%|[-0.00289945117453, -0.000368152753011]|
|AUROC|0.886357037272|0.893468821807|0.00711178453496|0.80236%|[0.00387920853917, 0.0106056827962]|
|AP|0.567232691216|0.585904924452|0.0186722332362|3.2918%|[0.0102268290363, 0.0286734552282]|
|conditional_pinball|0.124885458292|0.124113222868|-0.000772235423817|-0.61835%|[-0.00169888874576, 0.00023502796591]|

分析对象是冻结 common intersection 的 10,501 个 2024 验证场景、36,018,430 个有效云南 scene-pixel 暴露和 4,496,600 个真实雨像元暴露。场景不是独立样本；像元也不是独立重复。所有点估计逐字段复核已发表的全量 BEST 结果，零容差一致；新逐日期统计只用于分层、校准和不确定性。两个 BEST 均为 Epoch 9，本次不重新选择。

UTC target window_start 日期从 2024-03-01 至 2024-10-31 分成 35 个固定、互不重叠的连续 7 日区块。每次有放回抽取 35 块，两模型共享相同区块次数，保留块内所有时次、空间格点和原有效/真实雨条件；seed=2026，2,000 次，2.5/97.5 百分位区间。Core、Brier、pinball 用全局分子/分母重新累计；AUROC/AP 对抽中的原始 BF16 概率精确并列分数组重新排序累计，不平均日期 AUC，不独立抽像元。相对差异=(B1−B0)/|B0|×100%。

区块方法假设跨周依赖足够弱；天气系统可跨越区块边界，季节分布并非平稳，单一年份和 35 块限制有效信息量。7 日不是结果优化所得，也不宣称是最优块长。方法背景参见 [Künsch (1989)](https://doi.org/10.1214/aos/1176347265) 和 [Politis–Romano (1994)](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870)；本实现是预声明的固定非重叠周块方案，不等同于随机长度 stationary bootstrap。

全部区间属于开发验证集上的探索性分析，是点对点区间，未作多重比较校正，不给确认性 p 值。区间不校正利用同一验证集选择 BEST 的乐观偏差，也不估计训练随机种子变异，更不代表 2025 或真实未来泛化误差。实际有效重采样次数在 paired_uncertainty.json 中逐项记录；单一类别/空条件集合的指标保持不可计算。

## 六时相增益的解释与边界

B1 增加最近一小时的六个因果 B13 时次，B0 只用最新时次。配对样本、normalization、backbone/heads/loss/优化及评估相同；参数量为 4,329,410 与 4,331,810，增加 2,400，仅来自输入层接口。时间序列可能携带云系演变、移动和生命周期信息，但本实验没有对这些机制做独立因果消融，不能将指标变化证明为某一种物理机制。输入层参数数目也并非完全相同，应公开该限制。

冻结核心损失差异分解：occurrence 项变化 -0.000846796213202，以全部有效像元为分母的 quantile 项变化 -9.64071395321e-05。Conditional pinball 则使用真实雨暴露为分母，不与 core quantile 项混用。概率区分、总体损失、条件分位数和上尾风险应分别判断，不能用一个综合增益代替科学审查。

## 分层与缺失证据

固定雨强区间继承原 Scientific Review：干条件 ≤float32(0.1)，真实雨条件 (0.1,1]、(1,5]、(5,10]、(10,20]、(20,30]、(30,50]、(50,∞)。这些是依据 IMERG 监督真值的预声明诊断条件，不改变训练资格，也不是根据模型输出事后筛选。真雨区间内 AUROC 因单一正类无法定义，AP=1 属于数学平凡值，不是强雨检测成功。POD/FAR/CSI 保持 THRESHOLD_NOT_FROZEN，没有挑选概率阈值。

季节使用 MAM、JJA、SO（不完整秋季），月度为 3–10 月；日夜使用最新冻结 B13 nominal 在 UTC+8 的 [06:00,18:00) civil-clock proxy。它不是日出日落或太阳高度定义，没有从结果选择时段。该定义在补充推理前登记，属于描述性新增分层。没有既有正式地形区域/高程掩膜，terrain stratification=NOT_ESTIMABLE_NO_PREDEFINED_SUBREGION_MASK_AVAILABLE。未新建地形区域、未处理 DEM。未定义独立降水事件目录，事件数不可估计。

## 证据可靠性及治理

Scientific Freeze v2、model/head、loss、epsilon、LR、normalization、样本集合、划分及正式评价规则没有修改。2023 Train=10,455、2024 Validation=10,501；本次只读 2024。源代码执行 checkout 固定为 a1af0325b481202941c57e8fc94f3b20e441630a，完成证据基线为 166b1f86291bbcde167dbec30d3ae43ac23bba4c；科学批准提交为 d049f7ab7b8a382f47a5fe54384ea9416a22cde9。协议、head、normalization SHA 分别为 a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be、3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e、656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31。

两个模型在只读推理前后 state SHA 不变；238 项历史 checkpoint/epoch artifact 的 SHA 重新核验，代码与冻结配置不变。新分析的浮点分层汇总与原全局分母和点估计采用 1e-12 核验；原冻结 core 的 12 项字段和既有点估计则零容差一致。不得把分层浮点求和次序差异隐瞒成全量结果变化。

B1 独立恢复审批要求与实际沿用原始授权之间的治理偏差，见 RECOVERY_GOVERNANCE_DEVIATION.md。工程恢复和重放通过不能追认审批。失败、草稿更正、原始字节和恢复证据完整保留，科学可信度与治理处置由研究者分别判断。

## 新只读计数

- B0_MATCHED_V2: 新增只读 forward=1313；raw opens=42004；native decodes=31504；BEST SHA=c9ea052522557df8eaf869a447ec8ae013e657004888a56b9d3944db9a1fd5c2。
- B1_V2: 新增只读 forward=1313；raw opens=147014；native decodes=84009；BEST SHA=d5a45f9ac0f89a7870caff08eed6b5b209dbc0a62ad593ba2ba68271e570fc4a。

FORMAL_OPTIMIZER_STEPS_ADDED=0；BACKWARD_CALLS=0；MODEL_PARAMETERS_UPDATED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0；V2_PHASE_B_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true。

完整分层表、概率校准数据、上尾与治理报告及待填写决策表均位于本独立目录；图表生成状态单独登记。来源和分析代码逐文件 SHA 见 acceptance_manifest.json。

## 需要单独审查的结果

总体 Core loss、Brier、AUROC 和 AP 的配对探索区间方向一致；conditional pinball 差异为 −0.0007722354（−0.61835%），95% 探索区间 [−0.0016988887, 0.0002350280] 跨越零，不能据此宣称条件分位数提升已确定。固定真实雨强 5 mm/h 以上各区间的 pinball 点估计均是 B1 更高；最高区间仅 69 个 scene-pixel 暴露，其独立信息量更少。总体增益不能改写为所有强降水条件都改善。

低发生概率箱普遍高估真实雨频率，中高概率箱出现低估；Brier 改善不等于预测已经校准。q32 实际覆盖低于 0.984375，需结合全部 tau 图审查。未进行任何校准变换。

B1 云南 q32>100 mm/h 有 58 个 scene-pixel 暴露、44 个跨场景去重格点；B0 为零。二者云南 >500/>1000 均为零。这些是高条件分位数诊断，不是 58 次独立暴雨事件，也不自动视为科学合理。


## 完整图表与最终检查

[可编辑 LaTeX](PHASE_A_SCIENTIFIC_ACCEPTANCE.tex) / [PDF](PHASE_A_SCIENTIFIC_ACCEPTANCE.pdf)；[配对分层差异表](PAIRED_STRATIFIED_COMPARISONS.csv)。当前 14 项交付检查见 verification_tests_attempt_002.json；首轮失败另行保留。
