# 最小可检验假设与控制变量矩阵

RESEARCHER_DECISION_REQUIRED；所有 E/C/P 编号为 NOT_EXECUTED。数字是提案参数或已发表结果，不是新实验指标。

## 1. 起点与最小假设

2024 BEST 配对证据表明 B1 的 Brier/AUROC/AP 点估计较优，但不代表校准通过。0–0.5 概率箱整体高估雨频率，0.5–0.9 非空箱低估；最高箱为空、次高箱稀疏。B1 q32 rainy coverage=0.95076991505，对应 tau=0.984375；B0=0.95744184495。总体 conditional Pinball 差异区间跨零；真实雨强 >5 mm/h 的各层 B1 点值更高。58 个 q32>100 mm/h 暴露不是独立暴雨事件；最大约 351.08 mm/h 位置 IMERG=0，无站点/雷达核实。来源为 [历史诊断](../../phase_a_evidence_hardening/PROBABILITY_AND_TAIL_DIAGNOSTICS.md)。

H-O：在配对 fresh、固定集合/预算下，将 occurrence focal gamma 从 2 改为 0，可能改变概率可靠性和 Brier，同时保留或损害排序能力。可否证：预定主指标不改善、或 guardrail 的排序能力/雨强损失越界。文献只给一般 focal 概率估计动机，不能证明 YunTAPR 的误校准由 focal 导致；本项目含有限模型、共享骨干、权重衰减与相关资料。[CVPR 作者公开论文](https://openaccess.thecvf.com/content/CVPR2021/papers/Charoenphakdee_On_Focal_Loss_for_Class-Posterior_Probability_Estimation_A_Theoretical_Perspective_CVPR_2021_paper.pdf)

H-Q：固定所有其它条件，增加 conditional Pinball 项的固定权重，可能改变 rainy q32 欠覆盖；代价可能是发生能力或强雨层 Pinball。可否证：欠覆盖未减少，或只通过普遍扩宽分位数导致损失恶化。现有训练 quantile 项 /N_valid、科学 conditional 指标 /N_rain 的区别是设计动机，不是已证明的因果机制。

H-D：真实干样本没有直接 conditional Pinball 监督，可能与部分输入上的巨大 span 有关。干位置条件分布仍有定义；绝不把“该次参考干”解释为“条件分位数应该为零”。需要既有输出的预注册干/湿诊断、独立参考及单独正则化臂共同检验；任何干位约束可能错误缩窄少见降雨的条件分布。

H-R：部分 IMERG=0 的异常可能来自参考漏检、空间支撑或时间错位，而非确定的模型物理失效。可否证：满足质量与独立性条件的同步地面/雷达仍显示无雨；单个案例只能核实案例，不证明整体 q32 校准。上尾极值与欠覆盖可以同时存在，不构成数学矛盾。

## 2. 最小训练矩阵与扩展顺序

最小机制矩阵候选为 D1+I1（或同样规则的 I3）+Q1+N0+B9+S0+V0。这只是便于审查的完整兼容组合，不是选择或授权。每臂均 B0/B1 配对，末端以同一原评价规则测量；每个 seed 先生成配对初始化，再让 E0/E1/E2 从相同 fresh 状态副本开始，各臂 optimizer 均 fresh。

|臂|唯一变化|固定条件|主要回答/评价|批准类别|
|---|---|---|---|---|
|E0|无干预；冻结 v2 baseline 重新 fresh 训练|全矩阵控制项|提供与新臂同预算、同 seed 对照；不能拿历史 BEST 直接代替|新正式训练与推理|
|E1|occurrence gamma=0 替代 2；alpha=.5 不变|量化头、quantile loss、所有控制项|H-O；Brier/固定可靠性箱主候选，AUROC/AP 与雨强损失 guardrail|新 loss 实验|
|E2|lambda_q=2 替代 1，量化项仍 /N_valid|occurrence gamma=2、所有控制项|H-Q；q32 覆盖偏差、32 点覆盖、conditional Pinball/强雨分层与 span 分布|新 loss 权重实验|
|E3 扩展|加干位置 span 平方 penalty；lambda_d=0.001 为提案值|E0 其它条件|H-D；干尾暴露、rainy coverage/Pinball 及发生指标同时检查|新正则项，非最小首轮|
|E4 扩展|gamma=0 与 lambda_q=2 同时变化|E0 其它条件|仅在 E1/E2 后独立批准，用差中差检验交互；不作单因素归因|新组合实验|

E1 的 gamma=0 是 .5×BCE，不是另改 alpha 的加权 BCE；移除 focusing 因子是唯一预定 loss 变化，其梯度尺度影响属于此干预的一部分，不另调 LR 配合成绩。E2 权重=2 未从 2024 反算、未声称最优；若研究者不接受该对照值，需在执行前另行锁定，不做网格自动搜索。

E3 的候选数学项为 L_d=lambda_d × Σ_valid(1−z)s²/N_valid，z=1[y>0.1]、s 为 log 域 span；不修改 q 下界，不设物理硬上限，不在推理中 clamp。它会影响同一共享骨干，可能损害 rainy conditional 分布；缩小干位置输出不足以判定科学成功。当前不实现此项、无 backward。

如果选 B50/V1，应以原 core 共同规则选择所有臂，而不是以变动后的训练 loss 选择 BEST；同时报告固定终点敏感性，避免选择机制混入主对照。改变数据分区、scaler、预算、scheduler、初始化、head 架构的试验必须在另一个编号中单因素开展，不与 E1/E2 首轮捆绑。

## 3. 校准与物理诊断独立支路

|编号|候选最小操作|必需角色/依赖|可检验范围|
|---|---|---|---|
|C1|一个 scalar temperature 对 occurrence logit 拟合；qlog 完全保留|D2 Train/Selection/Calibration 分离；拟合目标与 T 正值范围预先批准|H-O 的 score 修正可行性，不回答共享编码器训练原因|
|C2|Isotonic 或 Platt 作为后续比较|额外批准、足够独立雨/干过程；与 C1 相同 calibration/report 集|稀疏高概率箱有过拟合风险；不能在 2024 全量拟合后称独立评价|
|P1|站点/雷达同步核实预注册异常与对照样本|数据许可、独立性、配准、质量规则另批|H-R 与个案物理一致性；不自动更换 IMERG 标签|
|P2|全部合资格同步样本统计 rainy coverage 与 p 可靠性|更完整参考与预注册评价域，2025 不包含|防止只看异常案例造成选择偏差；结果仍取决于代表性|

本轮没有拟合任何校准器、获取资料或执行 P1/P2。C1 也属于新科学实验，不因“不更新 backbone”而免审批。已有 aggregate reliability 没有足够样本级 logits 用于直接拟合；不得用分箱均值代替原 logits。对 C1 再训练 D2 模型是额外成本，不能偷偷复用 D1 的全量 2023 模型并称 calibration 分区独立。

## 4. 终点、否证与分析限制

建议主终点分别限定 H-O 的 Brier（及固定箱校准偏差描述）、H-Q 的 q32 coverage 偏差；全部 32 tau、conditional Pinball、>5 mm/h 层及发生排序是 guardrails/次级终点。q32 coverage 可被无限宽尾“改善”，所以必须联合损失和宽度/超限分布；没有批准 guardrail 的容忍差值，不能判定实验“成功”。

固定 bins、tau、真实雨强层、mask 与 pair 集合；不看结果改箱/合层/阈值。开发主比较 E1−E0、E2−E0 × B0/B1；新多重比较方案（例如预定家庭 Holm）需批准。日期块 bootstrap 是相关资料的探索推断，不替代 seed 重复；多 seed 先报告每 seed 配对效果和跨 seed 概况，不能把 seed×pixel 展平为独立样本。事件级有效样本数、最小效应及 power 仍未知，申请参考资料之后再预注册，不能伪造功效保证。

每 seed 的首轮 E0/E1/E2×2模型共 6 runs；B9 为 282,312 train updates。I3 共 18 runs、846,936 updates；每 run 终点全 2024 诊断为 1,313 forwards，分别合计 7,878 / 23,634。这里只计算候选工作量，没有调度或占用训练资源。扩展 E3/E4/C/P 不含在上述最小预算内。
