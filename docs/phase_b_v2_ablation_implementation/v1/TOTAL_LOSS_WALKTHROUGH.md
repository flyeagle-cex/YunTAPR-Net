# 总损失、监督张量与指标分母

candidate_loss(logit,qlog,rate,imerg_valid,yunnan_mask,*,config) 是候选聚合入口；config必须为闭合 AblationConfig，不能用未验证dict或临时gamma/lambda代替实验ID。再次 __post_init__ 校验防止外部代码绕过 frozen赋值保护后传入不匹配参数。该验证不是人类审批。

第一段 supervision：输出两头先通过形状、设备及finite/qlog守卫；参考rate必须原 float32、不参与autograd；两个mask必须独立bool且精确同形。valid=imerg_valid & yunnan_mask，N_valid=int(valid.sum().item())，rainy=clean_rate>float32(.1)，N_rain=sum(rainy&valid)。.item()把零维张量转为Python计数，也会在CUDA同步，属于安全检查成本而非正式性能测量。

clean_rate=torch.where(valid,rate,zeros_like(rate))仅创建计算副本。有效参考NaN/Inf/负值拒绝；invalid参考允许NaN并临时置0，与原总损失一致，测试检查输入未修改。模型输出全域的NaN/Inf都拒绝，不能因invalidmask而修补。N_valid=0抛 ZeroValidPixelsError；正常batch不静默skip，也不假称发生了更新。

第二段调用Focal得到S_occ，再将clean_rate提升FP64并log1p，调用Pinball得到S_qr。发生分子已包含alpha/gamma，但“unweighted”表示没有lambda_q；条件分子始终无lambda。第三段 combine_numerators(S_occ,S_qr,N_valid,*,lambda_q)要求有限非负FP32/64标量、同设备、正整数N_valid及正有限lambda，计算(S_occ+lambda*S_qr)/N_valid。

示例T1：S_occ=2,S_qr=3,N_valid=10，lambda1得到.5，lambda2得到.8。不是把所有loss乘2，也不是两处都乘lambda导致平方权重。T2科学CPB=3/2=1.5；N_rain只用于科学条件评价，不用于训练分母。这些都是纯合成手算与单元测试值。

CandidateLossResult保留experiment_id、s_occ、s_qr、training_objective、weighted_quantile_per_valid、n_valid、n_rain、conditional_skipped、status及execution_authorization=false。科学CPB属性只返回s_qr/n_rain；无雨返回None，表示不可估计，不是模型完美。weighted_quantile_per_valid是辅助训练分解，不可拿它冒充unweighted CPB。

metrics.py 的 ReportingSums.from_candidate 用detach再float生成只读汇总，停止构建梯度图但不修改训练张量。conditional_pinball按有雨数除；pooled(other)累加分子和计数，再计算比值，不能把不等batch的CPB直接平均。common_validation_sums在no_grad上下文显式使用FP64 logits及E0，固定gamma2/lambda1；训练臂的gamma或lambda不会改变共同core口径。

发生梯度和分位数梯度都通过total标量相连。gamma0时logit梯度=.5*(p-z)/N_valid；q梯度为分段Pinball梯度再乘lambda/N_valid。E2的q梯度为E0的2倍，而同一输入的发生梯度保持不变。这个合成张量性质不保证共享骨干真实训练后的发生输出不变。

当前candidate_loss可以被Python调用，但没有数据读取或执行授权能力；真正runner必须在外层验证科学审批、身份、资源及执行范围。学习时只使用测试文件里的小型合成输入。本轮不生成新的真实Brier、AUROC、AP、Pinball或上尾验证结果。
