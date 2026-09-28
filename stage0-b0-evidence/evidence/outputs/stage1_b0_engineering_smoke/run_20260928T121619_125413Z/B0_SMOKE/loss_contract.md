# Smoke loss contract

masked MSE = mean((prediction[valid] − target[valid])²)，valid=target_valid_mask。

先以 mask 索引，再减法/平方；不能用 NaN residual 乘 0 代替排除。valid subset 必须有限且非空。0 rain 为有效 target，明确进入 loss 和 metric；不按降水阈值筛像元。单位为 (mm hr-1)²；target 无 log1p 或其他变换。

仅用于 backward/optimizer 工程检查，不是论文正式 loss 冻结。单元测试包含 masked NaN、不参与梯度的 invalid 像元、0 rain 有效与全 invalid 拒绝。
