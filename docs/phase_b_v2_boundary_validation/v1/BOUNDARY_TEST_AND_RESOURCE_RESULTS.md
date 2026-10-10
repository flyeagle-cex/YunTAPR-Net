# 合成边界测试与资源实测

全部数据为人工有限张量；人工mask每场3430格点、M1全部原生像元有效、Q1参考完整。场景ID显式SYNTHETIC_ENGINEERING_ONLY，没有真实年份或路径。B0末帧取自B1六帧；模型、SP04公开映射、tau与epsilon保持原样。

最终CPU49、CUDA12、静态16通过，0失败/错误/跳过/warning。唯一pytest覆盖61；初次与复测共122个实例，不能相加作独立证据。旧91/6未重跑。两次各12完整forward/12backward，累计24/24；最终4个train1案例各3臂backward，8个validation8/5案例仅inference_mode。

|batch|语义|N_valid|allocated MiB|reserved MiB|forward+三臂loss ms|
|---|---|---|---|---|---|
|1|train forward/backward|3430|1435.02–1451.44|1820.00–1832.00|55.45–432.72|
|8|validation inference|27440|3280.71–3329.14|4254.00–4628.00|309.63–317.92|
|5|validation inference|17150|2057.67–2087.23|2900.00–2916.00|197.74–211.05|

GPU为RTX5060 Laptop、PyTorch2.11.0+cu128、CUDA12.8。每例先要求主机可用≥8GiB、CUDA API free≥5GiB、工作盘≥1GiB、BF16可用，再构造原模型；验证也保守复用此门槛，snapshot的full_backward=true表示资源门槛选择，不表示验证做了backward。没有OOM、超时、降batch/精度/结构、换seed或自动重试。

每值仅一批，首例冷启动；cuda synchronize+perf_counter计时。allocator峰值包括已有合成输入、三臂loss/梯度及共同FP64评价检查，不含其他进程、AdamW状态、真实I/O、checkpoint事务或長时循环。显存准入不是容量预测，旁路进程仍会影响可用资源。

E0数值与原b0_core_loss在冻结BF16环境比较，12例通过既有rtol=8e-7/atol=1e-8；最大绝对差为 1.8359273240564633e-08。本轮没有重复旧batch2全参数梯度差异检查；新batch1三臂全部74参数梯度存在、形状/dtype/有限性正确。混合有雨两头有信号；空雨分位数头梯度精确为0且不缺失，科学CPB=None。无参数改变，各例初始SHA与原seed2026证据一致。

训练N_valid分别3430/27440/17150；混合雨N_rain分别2450/19600/12250，仅为人工计数。CPU检查掩膜外NaN参考只在低层loss合成夹具中排除，不能视为M1/Q1合格模型场景。完整模型遇到缺原生帧、缺监督、非有限或身份/精度异常必须停止。

所有分子/目标数值保存在 [SYNTHETIC_BOUNDARY_RESULTS.json](SYNTHETIC_BOUNDARY_RESULTS.json)；这是工程算术而非新增降水性能指标。原始case/资源/源码快照见tests/cuda_attempt_002_evidence/。共同科学评价按冻结FP64验证器，训练objective仍各臂独立，不用于共同Core。

初次CPU49/CUDA12通过后，静态发现共同评价接口误用E0 FP32训练发生分子；已改为复用冻结FP64 LogDomainValidation，增加精确source对照，复测49/12/16通过，容差未放宽。初次测试、source index、static16之前的static15与修复说明均保留，不伪造数值失败。详见 [修复记录](tests/validation_precision_review_finding.json)。
