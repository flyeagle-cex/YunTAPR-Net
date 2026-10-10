# 候选实现架构与责任边界

科学定义来自冻结 Focal、Pinball、total_loss、v2 quantile 输出守卫及上轮 E0/E1/E2 提案；工程保护在隔离目录内补齐。当前委托允许候选代码和合成 autograd，未批准冻结合同修改、数据 preflight、真实模型推理或 optimizer 更新。

|模块|输入/输出|责任|
|---|---|---|
|config.py|E0/E1/E2 → 不可变参数；model/seed → RunSpec|闭合集合、18 身份、纯数学预算与 LR 前缀|
|validation.py|logit/qlog/rate/独立 bool masks → Supervision|形状、设备、dtype、finite、支撑/严格序、float32 标签与计数|
|focal.py|logit、硬标签、valid、显式 alpha/gamma → S_occ|稳定 BCE、类别权重、focusing、有效位置 sum|
|pinball.py|FP64 qlog/log_target/rainy_valid → S_qr|固定 32 tau、mean 后 sum，不转换物理域|
|total.py|两头合成张量与固定 config → CandidateLossResult|唯一权重、N_valid 分母、零监督停止|
|metrics.py|候选 result / 同输入张量 → ReportingSums|unweighted CPB、全局 pool、固定 E0 FP64 common core|
|readiness.py|合成或声明的 SHA 元数据 → 审查结果|fresh/恢复绑定保护；BlockedRunner 永远抛错|
|__init__.py|公开接口导入|没有数据或训练启动行为；导入损失 API 会加载 torch|

调用顺序：candidate_loss → supervision → occurrence_numerator 与 conditional_pinball_numerator → combine_numerators → result。Pinball 的 _pinball_from_errors 是私有算术内核，专供已经定义的 signed errors；不是绕过 qlog 资格的正式入口。P1–P4 用内核核对手算，不把常数 qlog 伪装成 v2 单调输出。

模型输出仍为 occurrence logit 与 FP64 32 条件分位数，本轮没有实现或修改 head、allocation/span 参数化、tau、epsilon、SP04 和 causal slots。validate_log_quantiles 是唯一正式输出守卫复用；没有调用模型构造器、Contract.load、torch.load、数据模块或旧训练入口。该复用保持冻结的 finite、q1>log1p(.1)、严格递增定义。

supervision 拒绝零有效像元而非返回 batch_skipped；这与旧正式 runner 对 skipped batch 的最终拒绝一致，但错误提前到候选 loss 入口。有效但全无雨仍保留 occurrence 与 q 的零梯度连接。输入 rate 必须是原 float32 参考，拒绝 requires_grad；输出全域 finite，即使像元无效也不能掩盖坏模型输出。仅 invalid reference 的临时计算副本置零，源张量不改写。

FP16/BF16 logits 显式提升为 FP32 做 BCE；FP64 logits 保持 FP64用于梯度差分。qlog/log_target/tau 固定 FP64。autocast(enabled=False) 防止外层混合精度改写关键路径，转换的反向链仍会将梯度送回原 logits。该输入张量层测试不宣称真实 BF16 模型已通过。

静态工具不 import 候选模块，仅读源码 AST、提案和发表的元数据 SHA。readiness.py 自身只用标准库，但通过公开包导入时 __init__ 会加载 torch；这仍没有实例化模型。真正只需标准库的入口为 scripts/.../static_review.py。
