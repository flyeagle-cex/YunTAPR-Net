# 隔离真实适配器

`plan.FrozenPlan` 校验公开 frozen manifest、原取样清单和 scaler 的 SHA，按原索引取 24+24 场景；仅登记所选 294 个不同 B13/IMERG 引用。读取之前按原冻结根、年份、扩展名、精确注册身份进行词法拒绝，不调用旧 loader 的 resolve/staging 路径。

`adapter.VerifiedReader` 复用已修复的 Windows 只读句柄：不共享写入/删除，拒绝 reparse point，保留选中父目录句柄，绑定实际目标与句柄元数据。逐块 SHA 对同次读取的 bytearray 计算，匹配后转 immutable bytes；冻结 netCDF 读函数只能通过精确内存别名消费这些字节，不重新打开原路径。

`RealAdapter.initialize_geometry` 使用真实冻结云南 mask 和 SP04，不用人工排列。冻结 shared scaler 不再拟合，保持 FP64 预处理算术至 FP32 输入。有效参考掩膜和云南地理掩膜独立；3430 个中心入界格点不变。`scene` 校验六帧 −60/−50/−40/−30/−20/−10 分钟及实际观测截止；文件生成晚于分析并不改变已冻结的回顾性资格。

`RealBatch.validate` 检查精确形状、dtype、设备、来源 owner、输入 SHA 和参考/地理 SHA。B0 输入必须是 B1 最后一帧，双方共用同一参考和地理身份。`pair` 保持原顺序，不依据参考雨量或输出取样。

`pilot.forward_real` 只接受精确冻结模型类和适配器来源，eval、参数 FP32 且 requires_grad=False。CUDA BF16 主干/发生头及 FP64 条件分位数保持已审查的正式精度语义。所有模型 forward 均在 inference_mode 内。

`resources.Budget` 固定 48 场景、48 batch 调用、4 GiB 内容、30 分钟和 3 GiB 工作集；父进程每 0.2 秒审计工作集并在期限前停止。无 CPU 降级、精度降级、自动重试或扩额。`formal_entry` 永久拒绝；未改动正式 Runner 的 always-deny 审批边界。
