# 资源与耗时

GPU `NVIDIA GeForce RTX 5060 Laptop GPU`，PyTorch 2.11.0+cu128 / CUDA 12.8。
执行前 CUDA free=6.783 GiB，满足 ≥5 GiB；分模型准入也通过。
allocator 设置 6 GiB fraction cap，并逐阶段检查 max_memory_reserved；没有改模型、batch、精度或转 CPU。

| 模型 | CUDA peak allocated GiB | CUDA peak reserved GiB | forward+loss 秒 | backward 秒 | step 秒 | checkpoint 秒 |
|---|---:|---:|---:|---:|---:|---:|
| B0_MATCHED_V2 | 2.639 | 3.182 | 0.4316 | 0.3033 | 0.0401 | 0.3902 |
| B1_V2 | 2.663 | 3.199 | 0.0998 | 0.1406 | 0.0294 | 0.3309 |

实际工作进程 Win32 **peak working set=2,453,544,960 bytes (2.285 GiB)**，低于 4 GiB。
peak pagefile/commit=7,416,758,272 bytes (6.907 GiB)；它不同于物理工作集，本轮未将 commit 上限伪写为 4 GiB。
自身 Win32 计数器包含进程此前峰值，输出即使已清理对象也保留峰值。
worker 有限执行 14.953 秒，含启动器端到端 17.875 秒，低于 1800 秒。
两场景解码与固定预处理共 10.3337 秒；逐文件 read/SHA 时间和 UTC 见收据。

**外部 watchdog 限制：**实际首次运行监控的是 venv 启动包装进程，得到 5,005,312 bytes，不是工作进程峰值，不能用来声称外部保护已经验证。
本轮自身 peak 工作集证明实际未越界；外部 PID 绑定已在执行后改为工作进程写入原子身份、OpenProcess 读取。
新增 PID 句柄测试通过，但完整 kill/超限联动仍 **NOT_VERIFIED**，且没有重跑真实 smoke。
计时是单次工程事务，不含多 epoch I/O 和全验证，也未消除缓存/首个 kernel 开销；不能据此估算科研吞吐或业务实时能力。
