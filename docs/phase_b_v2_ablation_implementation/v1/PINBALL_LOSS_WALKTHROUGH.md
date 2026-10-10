# Conditional Pinball 逐段解读

pinball.py 的 frozen_taus(device=None) 永远返回 FP64 的32个值：(i-.5)/32，i=1..32，最后为 .984375。torch.arange(1,33) 的右端不包含33；先减.5再除32，不是从0到1的等间距端点集合。device 参数仅决定 CPU/CUDA位置，不改变 tau 或科学定义。

conditional_pinball_numerator(qlog, log_target, rainy_valid) 是公开入口。

qlog=[B,32,H,W]，log_target=[B,1,H,W]，rainy_valid=[B,1,H,W] bool；全为同设备，浮点路径必须FP64。qlog单位是 log1p(mm/h)，不是 mm/h。公开入口复用冻结 qlog finite、最低支撑和严格序检查，不允许 sort、clamp、nan_to_num 或 expm1。

log_target 必须有限非负；被 rainy_valid 选中的 log_target 必须严格高于 log1p(float32(.1)提升至FP64)。该检查防止调用者错误地把干像元标成条件有雨。完整接口先在原 float32 构造雨标签，再提升 clean_rate.double() 做 log1p；不允许先提升再与十进制 .1 比较。rainy_valid=false 的高参考值可能只是被独立有效性或云南掩膜排除，不要求反向等价。

error=log_target-qlog 的广播仅沿明确的32tau轴；不是允许 mask、batch 或空间维随意广播。e>0 表示模型分位数低于参考，惩罚 tau*e；e<0 使用(tau-1)*e，两者均非负。rho=max(tau*e,(tau-1)*e)，每个有雨像元先 mean32，再把像元损失 sum，得到未加权 S_qr。

_pinball_from_errors 是私有内核。error.movedim(1,-1) 把 [B,32,H,W] 变为 [B,H,W,32]；rainy_valid.squeeze(1) 去掉单例通道，然后 bool 索引取出 [N_rain,32]。tau=[32] 的乘法对应最后一轴；mean(dim=-1) 只平均tau，不平均雨像元。最后的 .sum() 不含任何 N_valid/N_rain 分母。

P1–P4 的常数 e=+1/-1/0 和空mask只测试内核算术：前两者 mean(tau)=mean(1-tau)=.5，第三0，第四返回连接计算图的0。这些常数 signed errors 不是常数 qlog。常数 qlog 会在公开入口被严格序守卫拒绝，不通过“关闭守卫”来运行手算测试。

无雨返回 error.reshape(-1)[:0].sum()。[:0] 是空切片，sum得到0且仍连接输入图；backward产生实际零梯度，而不是None。与 qlog.sum()*0 的数学零相同，但避免很大有限 qlog 先求和溢出后形成Inf*0。该路径属于工程实现保护，没有新增科学损失。

对e>0，dS_qr/dq_i=-tau_i/32；e<0则为(1-tau_i)/32。e=0是折点，不能用中央差分要求唯一经典导数。torch.maximum给出可用的子梯度，但确认性梯度测试刻意远离折点。[PyTorch autograd说明](https://docs.pytorch.org/docs/2.7/notes/autograd.html) 可辅助理解反向图；本项目分段梯度来自实际 Pinball 定义。

本轮测试包括全部32tau解析梯度、合法严格序q、非有限输出、FP32q拒绝、干目标误选、shape/device错误、超出物理 FP64 expm1 边界的有限qlog。后者只证明 log域算术没有偷偷 materialize物理值；不证明巨大条件雨强物理可信。

小练习：对tau=.984375分别手算e=1/-1的惩罚；解释为何高tau更惩罚低估；将mean32误改sum32会使哪个量变32倍；解释覆盖率可因过宽分布提高，却不能单独证明质量改善。
