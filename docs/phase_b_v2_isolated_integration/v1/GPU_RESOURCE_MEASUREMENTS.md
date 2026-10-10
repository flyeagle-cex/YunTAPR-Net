# GPU 实测与限制

RTX5060 Laptop GPU，PyTorch2.11.0+cu128、CUDA build12.8。完整case构造前要求主机可用≥8GiB、工作盘剩余≥1GiB、CUDA BF16可用、CUDA API free≥5GiB；单独初始化要求主机≥2GiB。门槛是预设工程准入，不是用量预测。实际快照附各evidence JSON。本轮没有OOM或资源降级。

固定batch2、501×501、原结构和BF16/FP32/FP64。cuda synchronize与perf_counter计时；reset_peak_memory_stats后记录PyTorch峰值。

|候选|模型|forward+loss ms|主backward ms|allocated MiB|reserved MiB|
|---|---|---|---|---|---|
|E0|B0_MATCHED_V2|440.77|218.68|2839.51|3258.00|
|E0|B1_V2|90.94|138.66|2862.76|3274.00|
|E1|B0_MATCHED_V2|89.09|138.07|2702.83|3254.00|
|E1|B1_V2|90.65|137.68|2726.53|3270.00|
|E2|B0_MATCHED_V2|87.22|138.19|2702.83|3254.00|
|E2|B1_V2|88.41|137.89|2726.53|3270.00|

每项只有一批。首项含冷启动，后续可能复用库缓存，不能据此排名模型速度。forward+loss含适配检查和同步；峰值包含同输出三臂梯度检查，E0为原loss对照保留图。JSON还记录完整case额外对照峰值。

allocated/reserved不含完整驱动或其他应用显存。没有AdamW状态、真实I/O、DataLoader staging、batch8验证、checkpoint或长时运行。不能把本表直接乘846936估计正式总时长，也不能批准验证batch8的显存。

正式前另需获准测量：真实数据防火墙；两worker各734003200字节staging上限；训练batch2/验证batch8峰值；AdamW状态与checkpoint临时空间；设备共用、电源温度、驱动和余量；真实吞吐及恢复时间。

FP32模型加两份FP32 AdamW矩的张量存储下界为12×参数数：B0 51952920字节，B1 51981720字节。若保留18run各9epoch共162份，下界约8.42GB（十进制），不含容器、step/RNG、元数据、日志、原子临时副本。这不是实测checkpoint大小或已批准保留策略；正式runner必须另定磁盘预算并在不足时停止。
