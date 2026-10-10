# E0 冻结数学兼容性：实际合成验证

证据：tests/synthetic_attempt_008.json与XML、tests/phase_b_v2_ablation_implementation/test_losses.py及test_gradients.py。最终项目环境CPU177/0、CUDA3/0；数字是检查数量，不是模型评价样本或天气事件。没有真实数据或模型推理。

|核验|实际范围|预先固定判据|结果|
|---|---|---|---|
|Focal手算F1–F4|单/双元素，正负标签，gamma0/2|FP64 rel1e-12、abs1e-14|PASS|
|原focal函数|FP32/FP64/BF16/FP16输入，gamma0/2|FP32路径rtol8e-7、atol1e-8；FP64 1e-12/1e-14|PASS|
|冻结autocast语义|CPU BF16 logits，BCE FP32，gamma0/2|8e-7/1e-8|PASS|
|原total函数与两头梯度|B=1/2/3/5，H2/W3，独立invalid与云南mask|8e-7/1e-8，不调宽容差|PASS|
|未加权原Pinball|合法严格序FP64q，雨valid交集|1e-12/1e-14|PASS|
|共同validation core|原FP64 E0分子/共同分母|rel1e-12|PASS|
|GPU loss与两头梯度|三臂，同一小型FP64合成输入|CPU/CUDA 1e-10/1e-12|PASS|
|标签边界|float32(.1)及两侧nextafter|只上邻有雨|PASS|

相容表示合法受测输入下的数学值和梯度达到这些容差，不声明所有硬件、输入或逐位bitwise一致。候选先收集valid再sum，原函数乘mask后sum，归约顺序可能造成正常舍入差异。裸FP16/BF16在没有autocast时，原函数可能保持低精度；候选显式FP32 BCE，比较的是冻结正式autocast预期算术，而不是宣称裸低精度逐位一致。

原b0_core_loss没有lambda参数，E0只对应gamma2/lambda1。E1唯一改变gamma，E2唯一改变lambda；同输入科学CPB在三臂完全相同，因为q与标签不变、S_qr无权重。未来真实训练改变共享参数后，科学结果仍未知。

有意加强的工程拒绝行为：参数NaN/Inf/bool、mask/dtype/device/shape错误、非单调或失去支撑的qlog明确拒绝；零有效监督提前抛错，旧loss先返回batch_skipped再被正式runner拒绝。无雨仍连接q的零梯度；用空切片sum避免sum*q0的中间溢出。invalid参考沿用临时clean副本；invalid输出仍严格finite。

引用原文件字节SHA与重要函数行号见source_identity.json；原loss、quantile参数化、正式Phase-A入口和冻结合同未修改。E0工程兼容不等于Phase-A科学验收，不追认B1历史恢复，也不能证明Brier、q32欠覆盖或极端上尾已解决。

最终边界复核的CPU007为176通过/1失败：标量设备错配应在finite算术前拒绝。代码将device检查前移并保留同形dtype合同，容差未改；CPU008=177通过/0失败，CUDA004=3通过/0失败。详见tests/scalar_device_repair.json与原失败日志。
