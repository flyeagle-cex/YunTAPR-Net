# 科学协议定稿候选

PROPOSED_FOR_RESEARCHER_APPROVAL；所有 Phase-B 科研结果 NOT_EXECUTED。继承[预注册协议](../../phase_b_v2_ablation_preregistration/v1/protocol_proposed.json)与[指标口径](../../phase_b_v2_ablation_preregistration/v1/METRICS_AND_GUARDRAILS.md)，未改写旧文件。

## 固定矩阵与控制

|臂|alpha|gamma|lambda_q|相对 E0 唯一因素|
|---|---|---|---|---|
|E0|0.5|2|1|v2 基准配方|
|E1|0.5|0|1|发生 Focal gamma|
|E2|0.5|2|2|训练条件 Pinball 权重|

B0-Matched-v2 / B1-v2 × 三臂 × seeds 2026、2027、2028 = 18 个待批运行。E3、E4、校准器、DEM/GFS、新架构、FinalFit 不纳入。D1：冻结 2023 年 3–10 月 Train 10,455 场景；冻结 2024 年 3–10 月 Development 10,501 场景。Q1：两模型同一 M1 严格配对资格；不得补样、跳样或重新排序原始清单。N0：冻结 2023 shared scaler 共用，不拟合。2025 封存。

I3：同模型同 seed 跨臂 fresh 初态 SHA 一致；B0/B1 同名同形状参数相同，输入形状差异保留已定义原生初始化；不得载入历史 BEST/LAST。因果 B13 六帧 oldest→latest，分析前 60/50/40/30/20/10 分钟，B0 取最新帧；100×100 SP04 与真实云南 3,430 中心入界格点不变。FP32 标签严格 y>float32(0.1 mm/h)，再提升 FP64；不修改 32 tau、单调参数化、epsilon、数值守卫。

B9：9 完整 epoch；batch=2、accumulation=1、不丢尾批。S0：原 50 epoch LR 轨迹前 9 epoch，一轮 5,228 更新，warmup/AdamW 参数分组/clip=5 保持原定义；不能压缩为 9 epoch cosine。V0：每轮完整开发验证、保存完成边界；仅第 9 epoch 终点评价，不用 BEST/early stopping。训练 shuffle 继承 seed+零基 epoch 的确定性规则；验证原序、无新增增强。真实 loader 的顺序兼容仍待正式集成核验。

## 假设、数学和评价分母

令 V 为有效云南监督像元，R 为其中真实有雨像元，z 为 FP32 阈值硬标签，p_t 为对应真实类别概率：

$$S_{\rm occ}^{(\gamma)}=\sum_{j\in V}\alpha_{z_j}(1-p_{t,j})^\gamma\,{\rm BCEWithLogits}(\ell_j,z_j),\quad \alpha_0=\alpha_1=0.5.$$

E1 是 0.5×BCE，不能遗漏类别系数。令 u=log1p(y)、q_i 在同一对数域，tau_i=(i−0.5)/32：

$$S_{\rm qr}=\sum_{j\in R}\frac1{32}\sum_{i=1}^{32}\max\{\tau_i(u_j-q_{ji}),(\tau_i-1)(u_j-q_{ji})\}.$$

$$L_{\rm train}=(S_{\rm occ}^{(\gamma)}+\lambda_q S_{\rm qr})/N_{\rm valid};\quad
{\rm Core}_{\rm common}=(S_{\rm occ}^{(2),FP64}+S_{\rm qr}^{FP64})/N_{\rm valid};\quad
{\rm CPB}=S_{\rm qr}^{FP64}/N_{\rm rain}.$$

训练只给 S_qr 乘一次 lambda；共同评价固定 gamma=2 且不带 lambda。空雨训练 S_qr 为连通计算图的零，科学 CPB/覆盖为 NA；零有效/非有限/支持或严格单调性破坏立即停止，不自动修补。这是工程停止条件，不是性能成功判据。

实际公式来源：[occurrence_numerator](../../../src/yuntapr/experimental/phase_b_v2_ablations/focal.py)、[conditional_pinball_numerator](../../../src/yuntapr/experimental/phase_b_v2_ablations/pinball.py)、[candidate_loss / combine_numerators](../../../src/yuntapr/experimental/phase_b_v2_ablations/total.py)、[LogDomainValidation.add/report](../../../src/yuntapr/training/phase_a_validation_v2.py)。SHA 见 source_registry.json。本轮没有调用这些函数。

对模型 m 和 seed s，H-O：D_O(m,s)=Brier(E1,m,s)−Brier(E0,m,s)；H-Q：D_Q(m,s)=|C32(E2,m,s)−0.984375|−|C32(E0,m,s)−0.984375|。均负向为点估计改善，不能自动解释为显著或有实际意义。C_i=sum_R 1[u≤q_i]/N_rain。B0/B1 分别报告四个主比较；先按 seed 求绝对覆盖误差，再等权平均效应，不先平均预测/覆盖率。记录 B1−B0、时相×损失差中差，仅探索交互。

## 全量报告与解释边界

Brier、十个固定概率箱（n、mean p、雨频，空箱 NA）、exact-score AUROC/AP、共同 Core、未加权 CPB、全 32 覆盖及带符号偏差同时报告。真值雨强层固定 (0.1,1]、(1,5]、(5,10]、(10,20]、(20,30]、(30,50]、(50,inf) mm/h；每层 CPB、N_rain 和稀疏性均保留。

尾诊断继承 q32>10/50/100/500/1000 mm/h 的对数域比较，全 valid 与干/雨计数、场景数、去重格点数；不等于独立极端事件或确定性暴雨预报。q27–q32、q32−q1、derived span 的完整暴露分布摘要按旧候选 Type7 规格，仍待批准与工程化，不能以 forward 最大值分布代替。

2024 已用于 BEST 选择与反复诊断：拟议结果只可解释为开发探索。三 seed 的点值、效应、等权平均、范围及描述性 SD 完整报告；一个 seed 不能替代 I3。不得将 seed×像元当独立重复，或仅凭覆盖更接近 tau 宣称分位数更好。改善阈值、副作用和功效见[待决选项](EFFECT_THRESHOLDS_AND_MULTIPLICITY_OPTIONS.md)；无批准阈值不出科学“通过”判决。独立物理验证和业务近实时能力另有证据门槛。
