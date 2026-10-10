# E0/E1/E2 合成数学一致性

来源：phase_b_v2_ablations/config.py、focal.py、pinball.py、total.py；正式共同评价来自 training/phase_a_validation_v2.py:LogDomainValidation.add/report。来源 SHA 见 source_identity.json。

|臂|alpha|gamma|lambda_q|
|---|---|---|---|
|E0|0.5|2|1|
|E1|0.5|0|1|
|E2|0.5|2|2|

有雨标签先在原 FP32 参考域严格比较 0.1 mm/h，不先转 FP64。固定 tau_i=(i-0.5)/32；Pinball 在 log1p(mm/h) 的 FP64 分位数路径中先对 32 tau 平均，再对有雨有效像元求和。不进行 expm1。

$$
L_{train}=rac{S_{occ,gamma}^{FP32}+lambda_q S_{qr}^{FP64}}{N_{valid}},qquad
L_{common}=rac{S_{occ,gamma=2}^{FP64}+S_{qr}^{FP64}}{N_{valid}},qquad
L_{CPB}=rac{S_{qr}^{FP64}}{N_{rain}}.
$$

共同评价重新用 FP64 logit 计算 gamma=2 的发生分子，不能直接复用训练 E0 的 FP32 分子。E1/E2 的训练 objective 不等于共同科学 Core；lambda_q 仅乘训练分子一次。

6 个模型×臂事务均检查 N_valid=6860、未加权分子、固定目标组合、参数有限性和双头/骨干参与更新；重放得到逐值相同的训练记录和共同评价。每模型三臂的 fresh 初始化 SHA 相同。数据仅为内部人工张量，未观察任何新的真实 Brier、AUROC、AP 或降水性能。

E0 兼容范围：复用已验证候选数学实现、冻结真实 v2 模型和冻结 FP64 共同评价；加入 AdamW 后合成路径可更新并恢复。历史 Phase-A loss/模型/训练入口未修改。本轮没有重新执行先前完整 loss 数值/二阶梯度对照，也未证明真实实验结果改善。
