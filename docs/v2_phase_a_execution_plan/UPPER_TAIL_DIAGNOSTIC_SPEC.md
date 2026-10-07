# 每 epoch 只读上尾诊断

研究者确认 Train/Validation 分开、云南内外分开，两个模型口径相同。输入是已有 forward 的 FP64 qlog[B,32,100,100]；使用冻结 mask 的已有精确坐标裁切，inside3430、outside6570，不重新构造 bbox/坐标或 flip/transpose，不按实际是否降雨筛选。

每 forward 保存 sample_ids、batch大小、阶段及序号；两区域分别保存 max qlog、q32 max、最大值 sample_id/batch index/tau/row/column、FP64边界风险及计数。

每 epoch 对本阶段完整 per-forward q32 maxima 序列计算 p99/p99.9：CPU FP64、numpy.quantile(method=linear)，每 forward 等权，不做采样或像元合并分布替代。不跨阶段、模型或 epoch 混合。

阈值固定10/50/100/500/1000 mm/h，比较 `qlog > log1p(t)`，严格大于，int64计数。分别报告 scene-pixel-tau exposure 和 scene-pixel any-tau exposure，以及各自分母。FP64物理风险边界为 `log1p(float64_max)`，严格超过才标记。只描述已观察 trajectory，不保证未来。

observer 使用 detach/no-grad，不原地写 tensor、不接 loss、不消耗 RNG、不额外 forward、不执行 expm1/materialize_physical。不能影响 BEST、early stop、LR、参数、batch、样本选择或终止。有限高尾风险仍正常更新；真正违反冻结浮点合同由独立数值保护报错。

计算标量序列的统计分位数不是对模型 qlog 排序修复。测试证明 observer on/off 的 qlog/loss/gradient/optimizer/model/RNG 逐位相同。诊断收集或保存错误属于审计基础设施故障，不能忽略后宣称完整。

完整 tensor 不保存；逐 forward aggregate+argmax 保留本地 JSONL，epoch摘要保存 JSON及CSV，正式报告登记文件SHA。所有阈值均为描述性诊断，不构成训练规则或新的QC。
