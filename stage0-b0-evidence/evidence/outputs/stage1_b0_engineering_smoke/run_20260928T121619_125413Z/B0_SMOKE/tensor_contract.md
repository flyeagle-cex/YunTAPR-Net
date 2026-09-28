# Tensor contract b0-offline-engineering-smoke-v1

- Dataset item x/y: [1,32,32]，float32；显式第 0 维 channel=1。
- DataLoader x/y: [B,1,32,32]，float32，B=1 或 4；axes=batch/channel/height(latitude)/width(longitude)。
- input_valid_mask/target_valid_mask 与对应 tensor 同 shape，torch.bool。
- x 在 Dataset 中保留 K；y 保留 mm hr-1。missing 保留 NaN，不转换为有效 0。真实模型输入要求全部有效且有限；目标 loss 使用 bool mask。
- 模型内部固定 x/300 仅是 ENGINEERING_SMOKE_ONLY 数值 conditioning；没有从数据拟合 mean/std、log1p 或其他归一化统计；不是正式 normalization 规范。
- channel axis 通过显式 x[None]/y[None] 添加；batch 通过 stack 添加。没有无记录 squeeze/unsqueeze，没有七通道或六时相合并。
- metadata 为每样本 dict，包含 source paths、source times、candidate analysis、causality_pass、mapping_status；DataLoader 使用自定义 collate 保持 metadata list。

所有输出 target coordinate 对应 frozen actual IMERG 数组的上述 slice。scope=ENGINEERING_SMOKE_CROP_ONLY。
