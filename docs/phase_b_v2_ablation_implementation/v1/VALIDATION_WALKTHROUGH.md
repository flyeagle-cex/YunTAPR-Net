# 张量契约与工程保护解读

validation.py集中拒绝错误输入，不负责改变tau、epsilon或数学损失。ZeroValidPixelsError继承ValueError：调用者可精确捕获无监督异常，但正式runner应停止，不能catch后静默继续。Supervision为frozen dataclass，字段valid/rainy/rainy_valid/clean_rate都是张量，n_valid/n_rain是Python整数；frozen防止字段重新赋值，不会把内部Tensor变成真正只读。

image_tensor(name,value,channels)检查torch.Tensor、torch.strided、四维[B,C,H,W]及全部维度>0。channels只接受调用方固定1或32。strided是普通dense张量布局，区别于sparse；不要求contiguous，因此合法非连续切片仍可运算。该函数不检查浮点dtype，具体入口随后检查，职责不要混淆。

same_shape_device(name,value,reference)要求精确同shape和device，返回None代表通过，失败抛ValueError。boolean_mask再要求bool/dense。mask不能用float0/1替代，也不能把[H,W]悄悄扩成[B,1,H,W]；未来调用者若需构造batch掩膜必须明确产生合合同形张量。

finite_tensor(name,value)调用torch.isfinite(value).all()再转Python bool；CUDA会同步。NaN和±Inf都拒绝。occurrence_logits要求实浮点FP16/BF16/32/64、CPU或CUDA、单通道及全域finite；quantiles要求32通道CPU/CUDA，并复用原validate_log_quantiles的FP64/支撑/严格序，不自己发明epsilon或clamp。

graph_zero(value,dtype=None)的reshape(-1)把元素拉平，[:0]取零元素切片，sum(dtype=...)产生零维0。它不先把所有值加起来，所以即使总和会溢出也能生成连接原图的0；梯度是全零。这里的零不是把非法输入修好，前置守卫仍先拒绝NaN/Inf。

supervision(logit,qlog,rate,imerg_valid,yunnan_mask)先检查两头与空间/device，再检查原float32非梯度rate和独立bool masks，构造交集并计数。计数0停止；有效参考负/非有限停止；invalid参考临时where成0。rainy在原精度与torch.tensor(.1,float32)比较，再与valid相交。返回的clean_rate稍后才double()/log1p。

具体边界：float32(.1)提升后数值略高于十进制.1，所以先double再比较会错误地把边界值标有雨；测试B1保存三个nextafter相邻值。invalid参考NaN允许进入临时clean副本，但原值不改；invalid模型qlog的NaN仍拒绝，因为模型输出守卫覆盖全域。零batch、32→31通道、非boolmask、meta/CPU设备不一致都不靠广播或fallback继续。

本模块的shape/dtype/finite/异常类属于工程保护；监督交集、严格float32雨标签、q支撑/单调是冻结科学语义。未来正式网格[100,100]、3430格点及样本资格必须由另外获授权的runner检查，本loss保护不单独证明地理配准正确。
