# 损失数学、真实代码与研究者练习

本轮只写规格、映射和测试设计；正式Focal/Pinball/total_loss文件不变，没有研究者新实现、模型forward或autograd调用。以下数学值是手算合成期望，不是运行PyTorch所得结果。公式的排版版见本报告数学附录。

## 真实Focal代码

src/yuntapr/losses/focal.py 的 focal_bce_sum(logit,rainy,valid,alpha,gamma) 要求显式alpha/gamma，使用 BCEWithLogits(reduction=none)，再算pt=exp(−BCE)、按标签选择alpha_t，返回sum(alpha_t(1−pt)^gamma BCE valid)。其中pt在二元硬标签下等于真实类别概率。输入logit不是已sigmoid概率；总损失模块决定标签与最终分母。

alpha=0.5使两类权重均0.5；gamma=0时每个有效位置就是0.5BCE，不能除掉0.5或改alpha来制造另一对照。gamma影响focusing与梯度，并可能通过共享骨干影响q头。现函数检查alpha范围/gamma非负，但没有完整的finite、bool排除、shape、valid.dtype或同device前置校验；NaN gamma会穿过gamma<0判断。真实输出守卫承担部分安全责任，未来研究者接口应明确拒绝这些输入，不能把旧函数“支持参数”理解为已满足全部审核规格。

## 真实Pinball代码

src/yuntapr/losses/pinball.py 的 frozen_taus给出32个(i−.5)/32。pinball_sum要求qlog=[B,32,H,W]，log_rain=[B,1,H,W]且与qlog同dtype，quantile_axis_reduction必须显式为mean。误差e=log1p(y)−qlog；rho=max(tau*e,(tau−1)*e)，先沿32tau取mean，再乘rainy_valid，最后sum，不对雨强做expm1。

它本身不决定0.1阈值、不除以有雨数或有效数；支持/单调/finite检查由v2头及总损失链负责。裸函数未完整检查mask dtype/device/finite。任何新接口必须显式注明调用者与被调用者责任，不能静默广播mask、sort q或把非法值乘0后当安全。mask乘法不能一般消除NaN：NaN×0仍是NaN。总损失仅在valid之外清理y的临时计算张量，不改原数据；输出有限性仍需独立守卫。

## 真实总损失与新权重的最小规格

src/yuntapr/losses/total_loss.py 的 b0_core_loss构建valid=IMERG_valid & Yunnan_mask，N_valid=sum(valid)。有效目标必须有限非负；clean_y仅在invalid处临时置0，rainy=clean_y>0.1，在原float32上比较。occ=S_occ/N_valid；qr=S_qr/N_valid，有效但无雨时qr=qlog.sum()*0以保留图连接；现total=occ+qr。N_valid=0返回batch_skipped，正式runner随后拒绝，不能自动跳过。formal_mode形参并未作为科学授权门槛；LossResult.execution_scope默认ENGINEERING_ONLY也不是审批证明。

候选E2的唯一改变是 L_train=(S_occ+lambda_q*S_qr)/N_valid，lambda_q=2；E0/E1=1。科学审查CPB=S_qr/N_rain，始终不带lambda_q。三臂共同core采用gamma2、alpha.5、lambda1，在FP64累计全数据分子后除N_valid；与新的训练目标分开登记。未来工程最好返回unweighted S_qr、qr_unweighted、qr_weighted、N_valid/N_rain和skip状态，杜绝把权重重复乘进科学指标。

研究者最小接口规格（签名不是实现）：

- researcher_occurrence_numerator(logit,rainy,valid,*,alpha,gamma) -> scalar S_occ；保持输入device，明示dtype与finite前提，检查硬标签及bool mask，sum而非mean。
- researcher_pinball_numerator(qlog,log_target,rainy_valid,*,quantile_axis_reduction) -> FP64 scalar S_qr；32tau固定、axis mean、sum雨valid，不生成物理值。
- researcher_combine_numerators(S_occ,S_qr,N_valid,*,lambda_q) -> scalar L_train；显式正有限lambda与正整数N_valid，lambda只乘S_qr一次。空valid由上层拒绝；不要隐藏fallback。

研究者需独立写最小PyTorch版本，先说明自身shape/dtype/mask/非有限/空雨约定。可把Focal和Pinball理解练习放在个人scratch，不改正式文件。研究者提交代码后Codex只审阅数学和接口；只有随后明确允许集成与完整测试，才工程化。这个顺序不能由本协议、Git提交、自动测试或“已理解”代替。

## 手算合成输入与预期输出

表中qlog常数用于裸Pinball接口算术测试，不是合资格v2模型输出（严格单调头不允许所有q相同）；绝不以这些fixture执行模型。log_target与qlog的差直接指定，避免把对数域单位误读为mm/h。

|用例|合成设置|预期标量/语义|目的|
|---|---|---|---|
|F1|1 valid，logit0、rainy=true、alpha.5、gamma2|ln2/8=0.08664339756999316|focusing与sum|
|F2|同F1、gamma0|ln2/2=0.34657359027997265|.5BCE，非BCE|
|F3|logit0、rainy=false，其他同F1|ln2/8|alpha对两类一致|
|F4|2个相同valid元素、gamma0|ln2=0.6931471805599453|不提前mean|
|P1|1 rainy_valid；所有32个e=+1|mean(tau)=0.5|axis mean与误差符号|
|P2|1 rainy_valid；所有32个e=−1|mean(1−tau)=0.5|过预测惩罚|
|P3|e=0，各tau|0；不可在kink强制唯一梯度|零误差与subgradient|
|P4|同P1，rainy_valid=false且所有数值有限|0|雨mask语义|
|T1|S_occ=2，S_qr=3，N_valid=10，lambda1/2|E0=0.5；E2=0.8|权重与共同分母|
|T2|S_qr=3，N_rain=2|科学CPB=1.5，与lambda无关|指标分母分离|
|B1|float32恰等于float32(.1)，及相邻可表示上下值|等于及下邻为干、上邻为雨|提升前判断；不打印伪“精确0.1”|
|Z1|N_valid>0，N_rain=0|occ保留，qr为graph-connected零；CPB/coverage不可估计|无雨非整batch跳过|
|Z2|N_valid=0或有效y负/NaN|正式拒绝；无更新|异常停止|

未来边界测试：gamma0在极端有限logit下仍是.5BCE；缺参数、bool/NaN/inf参数、shape/dtype/device错配应拒绝；非有效目标的处理必须与现临时clean策略一致；无雨q梯度为零但不缺失；雨处e>0梯度对q为−tau/32、e<0为(1−tau)/32，再乘lambda/N_valid；gamma0单元素logit梯度为.5(p−z)/N_valid。这些是预期性质，本轮未运行梯度检查。

研究者必须能解释：为何裸sum、axis mean及两个不同分母不可混用；为什么float32阈值在提升前判断；为何coverage改善可能由宽尾造成；为何masked NaN不自动安全；为何训练中不expm1；为何新lambda只影响优化目标而不改报告CPB。数学映射及源码短定位在source_identity，未来实现审查需绑定研究者真实代码SHA与独立集成许可。
