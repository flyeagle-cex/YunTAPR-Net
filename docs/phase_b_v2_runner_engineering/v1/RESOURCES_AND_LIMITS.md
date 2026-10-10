# 实际资源与未测量项

RTX 5060 Laptop，8 GiB；BF16/FP32/FP64 冻结路径，batch=2，完整 501×501 架构。数值来自 tests/*_synthetic.json。

|模型 / 臂|峰值 allocated MiB|峰值 reserved MiB|一次更新+评价秒|整项秒|
|---|---|---|---|---|
|B0_MATCHED_V2 / E0|2702.91|3262|0.453|4.366|
|B0_MATCHED_V2 / E1|2702.91|3262|0.434|2.634|
|B0_MATCHED_V2 / E2|2702.91|3262|0.416|2.521|
|B1_V2 / E0|2726.53|3280|0.407|2.543|
|B1_V2 / E1|2726.53|3280|0.413|2.500|
|B1_V2 / E2|2726.53|3280|0.420|2.565|

峰值统计包含 fresh 初始化、无雨 backward、两次混合更新、合成验证、checkpoint 和恢复。单次更新+评价计时以 CUDA synchronize 包围。整项时间包含首次库启动等开销；共用 GPU 的其他应用不计入 PyTorch allocated/reserved。

FRESH blob约 16.56 MiB，含模型但无 AdamW moments；LAST blob约 49.65 MiB，含 AdamW/RNG。本轮实际最大值和全部 byte 数见每项 JSON。

构造前资源门槛为主机可用≥8 GiB、CUDA free≥5 GiB、工作磁盘≥1 GiB。step 前释放未使用 allocator cache 再测 free，不改 batch、结构或精度。没有资源不足跳过项。

这些是人工固定输入的短程测试，未测真实 I/O、数据解码、多个 epoch、验证 batch=8 全流程、缓存、长期显存碎片、磁盘容量增长、热降频或完整正式耗时。正式执行前仍需独立授权的资源/preflight 测量；不得用本轮秒数直接预测 846936 次正式更新的耗时。
