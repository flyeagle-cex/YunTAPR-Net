# 梯度与优化器

fresh 配对初始化使用 seed2026，同名同形状状态一致；保留 B1 原生输入初始化及零 skip，未加载历史权重。
每模型 74 个实际参数张量（骨干 70、发生头 2、分位数头 2）均有有限梯度，无断图。
本批有 45 个真实有雨有效像元，两输出头均有非零梯度；若无雨，候选损失保留连接的零分位数梯度，不重新选样。

冻结 AdamW：Conv2d kernel decay=1e-4；Conv2d bias 和 GroupNorm affine 无 decay；betas=(0.9,0.999)、eps=1e-8、foreach/fused=False。
每模型 optimizer 全新且初始 state 为空；更新后 74 份 state 的 step 均为 1、moments 为 FP32、有限且二阶矩非负。
S0 使用原 50-epoch/5228-step warmup 轨迹第一更新，LR=`1.9127773527161438e-08`；scheduler.completed=1，没有完成 epoch。
裁剪阈值 5，实测前后范数见训练审计及 `final_status.json`。

| 模型 | 更新前完整状态 SHA | 更新后完整状态 SHA |
|---|---|---|
| B0 | `a8381729fc22077dd33d632ff2f8c293a04c160dd0c5425fc9a46b93b4885719` | `ec816c49b860662b5924bf5da265503d890db9929b9438a2649dd6d1d0d71115` |
| B1 | `f02fda62c40e6a103bae61d0572685ef3aafa2c73efef7bd0ca57f08e058c331` | `8aa903bca9b73f17d5eeb59662ee71e0a24b346b9050e2f851a3e9fd71afdac9` |

两模型均有 60/74 个参数张量的字节发生变化：骨干 56、发生头 2、分位数头 2。
所有梯度、参数和 optimizer 数值检查通过；冻结 buffers 不变。
极小第一步 LR 下部分 FP32 参数字节不变可正常出现；未用变化幅度判断科学质量，也没有二次更新验证。
