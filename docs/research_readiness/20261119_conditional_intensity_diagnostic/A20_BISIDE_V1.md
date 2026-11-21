# A 点值强雨双侧监督

COSINE9 固定 E9 在 2024 Dev 的 717 个真强雨像元时中，A 最大为 **11.507703 mm/h**。同人口非强雨 A 最大为 **18.618254 mm/h**。对 A 使用任何全域单调非降的变换，再应用统一阈值，只要有真强雨越线，就至少有一个非强雨像元时越线。保持零误报时，检出数仍为零。这个结论直接来自已保存的分组最大值。[双头诊断](B_HEAD_DIAGNOSTIC.json)

TAIL20 改善了强雨条件物理 Pinball，但 q32 在非强雨像元时的越线多了 833，固定 A 仍为零命中。网页总控 High 选定 `A20-BISIDE-V1`，直接对现有 A 点值施加双侧监督，检验模型能否拉开真强雨与非强雨的点值分数。[TAIL20 冻结结果](TAIL20_RECOVERY_RESULTS.json)

## 单变量对照

使用 B7/seed2029、REAL、COSINE9 固定 E9。沿用现有 U-Net 双输出头、物理输入、样本人口和顺序。保留 E0 发生损失和 32 节点条件 log Pinball。在有效且位于云南掩膜内的像元时中，用严格 FP32 的 \(R_i>20\) 定义正类，\(R_i\leq20\) 定义负类。

训练时使用模型实际输出的发生概率 \(p_i\)，并在新增辅项中停止它的梯度。计算 \(\tilde A_i=\operatorname{stopgrad}(p_i)\operatorname{mean}_{j=1}^{32}[\operatorname{expm1}(q^{\log}_{ij})]\) 和 \(m_i=(\tilde A_i-20)/20\)。物理转换和损失均使用 FP64。

\[
L = L_{\mathrm{E0}} + 0.1 \left[
  \frac{\sum_{i:R_i>20}\operatorname{softplus}(-m_i)}{n_{+}}
  + \frac{\sum_{i:R_i\leq 20}\operatorname{softplus}(m_i)}{n_{-}}
\right].
\]

两类分别取均值。当前批次没有正类时返回精确的 E0。有正类且没有负类时仅使用正项。新增辅项对发生 logit 的直接梯度为零，共享骨干仍可影响评价时的发生概率。Dev 使用原固定 A 和原 FP32 严格越线规则。

## 预先冻结的判定

在匹配的 2024 Dev 全人口上，主终点要求固定 A 的强雨 TP **大于 0**、FP **等于 0**。同时强雨物理 Pinball/20 严格低于 0.5068646309277546，q32 支持 TP ≥ 160、FP ≤ 5,769，弱雨与三个发生头护栏通过。现有冻结评价器可同时判定 `PASS_DEV_TAIL_GATE` 与 `point_a_detection_restored`。任一条件失败即封存本次候选。单 seed 的 Dev 筛查之后仍需独立事件和最终泛化证据。[冻结门槛和比较器](CONDITIONAL_TAIL_V1.md)

## 已完成

Codex Sol High 完成独立损失函数及 8 项 CPU 合成检查，覆盖正负梯度方向、精确分母、空类、FP32 阈值、掩膜、停止梯度、实际 BF16 概率对应的 FP64 读出、有限性和 E0 分量。当前阶段为 **SYNTHETIC_VALIDATED**。正式入口及预算待绑定，科学状态 `NOT_VERIFIED`。下一步工程用 Sol High，形成准确执行包后由 Harness High 只审核新增执行边界。[准备收据](A20_BISIDE_V1.json)
