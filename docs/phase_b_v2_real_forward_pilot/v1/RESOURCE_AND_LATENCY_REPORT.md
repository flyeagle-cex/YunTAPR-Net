# 实测资源与耗时

实际成功执行的父进程计时 23.859 秒；包括首败与访问前修复等待的原始预算计时 226.678 秒，未重置 30 分钟额度。worker 工作集峰值 1,668,018,176 字节（1.553 GiB）。CUDA 峰值 allocated 907,440,640 字节，reserved 1,218,445,312 字节。设备与启动前可用显存见 final_status.cuda_admission；没有假定或外推正式九轮训练耗时。

Win32 private commit 最终值 4,220,235,776 字节、peak pagefile/commit 4,266,172,416 字节；这些指标与物理驻留工作集不同。本轮 3 GiB 约束按研究者指定的进程工作集实施，不以 commit 值冒充工作集。公开元数据准备核验不读取原始内容；本表 I/O 计数以实际 pilot 的受限句柄为范围。

`SCENE_PROVENANCE_RECEIPTS.json` 提供逐场景 SHA+解码+固定预处理耗时；`FORWARD_RECEIPTS.json` 提供逐 batch transfer/sync、forward+结构检查耗时及显存。GPU 数值是 PyTorch allocator 统计，不等于设备全部进程占用；CPU 是 Win32 进程工作集。父进程监督间隔 0.2 秒，系统采样和硬停止有调度延迟，未声称无穷精度的瞬时零超调保证。

所选场景中共有 62 个文件生成晚于分析时刻的时相引用；实际卫星观测因果性与业务可获取时间是不同证据。此测量含读取和审计开销，不构成业务近实时传输、入库、可用延迟验证。IMERG Final 仅为回顾性参考。
