# Phase-A training protocol（开发训练协议）v2 候选

本文件及 `config/science_v2/phase_a_protocol_candidate_v1.json` 为 candidate reuse（候选复用），不宣称参数对 v2 最优。

AdamW（带解耦权重衰减的自适应矩估计优化器）：betas（矩估计衰减系数）0.9/0.999，eps（优化器数值稳定常数）1e-8，Conv2d kernel（二维卷积权重）weight decay（权重衰减）1e-4，bias（偏置）与 GroupNorm affine（组归一化仿射参数）不衰减。foreach/fused（批量张量/融合实现）均 false，沿用旧明确实现。

base LR（基础学习率）1e-4；min LR（cosine 阶段最小学习率）1e-6。physical batch（实际每次更新批次）2，drop_last（丢弃尾批次）false，单样本尾批次真实分母 3430，普通批次 6860。10,455 scenes（样本时次）对应 5,228 steps（更新）/epoch（轮次）。

1 epoch linear warmup（线性预热）W=5,228，50 epoch fixed horizon（固定余弦调度跨度）U=261,400；保留既有精确公式，min LR 下界仅用于 cosine（余弦衰减）阶段。validation batch（验证批次）8，固定顺序，完整全局原始损失累积；early stopping（提前停止）patience（等待轮数）8、min_delta（最小改进量）1e-4。

BF16 forward（bfloat16 主干前向计算），FP32 parameters/raw head（32 位参数与头原始输出），FP64 normalized transform/pinball（64 位归一化变换与分位数损失），GradScaler（梯度缩放器）关闭，TF32（张量浮点加速近似）关闭，global gradient clip norm（整体梯度裁剪范数）5。

L_occ（发生事件焦点损失）focal alpha（类别权重）0.5、gamma（难例强调指数）2；L_qr（条件分位数损失）32 tau 取平均，按实际云南有效目标数归一化。只使用 log-domain（对数域）结果；physical conversion（物理转换）必须显式请求。

seed（随机种子）2026 和旧 fresh same-name/same-shape pairing（全新同名同形配对参数复制）仅作为工程候选，尚非正式约定。没有指定新的正式 checkpoint（训练状态文件）目录或实现训练 runner（正式训练入口）。

CANDIDATE_REUSE_OF_V1_PROTOCOL=true
RESEARCHER_APPROVAL_REQUIRED=true
FORMAL_TRAINING_AUTHORIZED=false
V2_PHASE_A_STARTED=false
V2_PHASE_B_AUTHORIZED=false
2025_RAW_ACCESS=0
