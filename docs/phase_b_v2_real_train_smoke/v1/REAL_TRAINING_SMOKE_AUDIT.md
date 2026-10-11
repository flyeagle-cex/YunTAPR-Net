# 真实训练工程审计

直接研究者任务指令只授权本次 smoke；无科学协议批准事件生成，无正式 Runner 启动。
冻结 2023 Train 原排序第 0、1 行：`2023-03-01T00:30:00+00:00`、`2023-03-01T01:00:00+00:00`。
没有读取标签后选样、补帧或跳样。两个模型共享相同监督 SHA `f33d8ab8eaedb1f66c20f08d084d183d8dd0dbab5200285a0c4280ec6f8e9b54`。

| 模型 | 初态训练目标，仅工程数值 | N_valid | N_rain | 裁剪前 L2 | 裁剪后 L2 | 更新调用 |
|---|---:|---:|---:|---:|---:|---:|
| B0_MATCHED_V2 | 0.101619122034 | 6860 | 45 | 6.367124081 | 4.999999200 | 1 |
| B1_V2 | 0.112793514889 | 6860 | 45 | 8.006965637 | 4.999999810 | 1 |

45 是两个场景上的有雨有效像元暴露数，不能解释为独立事件。两个场景全部合资格，N_valid=2×3430。
E0 固定 alpha=0.5、gamma=2、lambda_q=1：`L=(S_occ+S_qr)/N_valid`。
发生项在全部有效云南监督像元上求和；32 个固定 tau 的 log1p Pinball 先求均值，再只对真实有雨有效像元求和。
阈值是原始 FP32 雨强严格大于 FP32(0.1 mm/h)，计算图中的 q 路径为 FP64。
科学 Conditional Pinball 的定义仍是未加权 S_qr/N_rain；本轮未计算开发验证指标或给出科学改善判断。
公式源：`phase_b_v2_ablations/total.py:candidate_loss`、`focal.py:occurrence_numerator`、`pinball.py:conditional_pinball_numerator`，来源 SHA 见 `source_identity.json`。

B0 输入 `[2,1,501,501]`、B1 `[2,6,501,501]`，均为 FP32；监督 `[2,1,100,100]` FP32；独立有效/云南 mask 为 bool。
输出概率 `[2,1,100,100]` BF16，条件分位数 `[2,32,100,100]` FP64。
输出有限、严格单调、支撑下界通过；检测使用同次训练输出的 detach 视图，无额外 forward。
每模型训练 forward/backward/step 各一次，额外无梯度前向 **0**。没有完整 epoch、验证或 BEST/LAST 选择。
