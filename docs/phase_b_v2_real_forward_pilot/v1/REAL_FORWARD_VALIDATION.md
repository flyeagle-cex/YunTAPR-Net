# 真实输出结构验证

实际状态 `BOUNDED_REAL_FORWARD_PILOT_PASS`；完成 48/48 场景。B0/B1 成功 batch：{'B0_MATCHED_V2': 24, 'B1_V2': 24}；场景前向：{'B0_MATCHED_V2': 48, 'B1_V2': 48}。

要求输入 [2,1,501,501]/[2,6,501,501] FP32；参考 [2,1,100,100] FP32；有效和真实云南掩膜 bool。输出发生 logit/probability [2,1,100,100] BF16，分位数 [2,32,100,100] FP64，log1p(mm/h)。验证有限性、sigmoid 一致、严格单调、首分位数 > log1p(0.1)、SP04 全支撑、无梯度图、模型 state SHA 不变。

逐批实测证据见 `FORWARD_RECEIPTS.json`。未进行 expm1、loss、Brier、AUROC、AP、Pinball 或降水性能评价。E0/E1/E2 不参与本轮随机初始化输出比较。FP32/FP64 物理转换风险只比较浮点界限，不作物理可信性结论。

24+24 场景均可被 batch=2 整除，最后一批为 2；没有额外构造 batch=1 真实尾批。训练、backward、optimizer、私有权重读写均受阻断。PASS 不等于正式训练就绪。
