# 2026-10-13 启动失败：冻结 B13 源盘不可用

北京时间 07:46:12 启动一次独立恢复 Supervisor，07:46:36 worker 报错并停止，Job 已清空。**新预留 0、新执行 0；旧 162,068 不变。** 原始数据文件内容读取、真实 forward/backward、LAST 反序列化和新模型恢复均尚未发生。

具体阻塞：`src/yuntapr/training/phase_b_v2_seed2026_resume_v1/worker.py:36` 调用原数据适配器 `Reader.lock_parents()`；`src/yuntapr/training/phase_b_v2_seed2026_v2/data.py:132` 创建冻结目录只读句柄时返回 `FileNotFoundError / WinError 3`。对冻结 H_ROOT 推导的 H: 根祖先进行一次只读检查，确认 H: 当前不可用，未搜索替代数据或访问 2025 子目录。

最小解决办法：恢复冻结卫星数据所在 H: 盘及其原始路径。不能擅自替换盘符、改 manifest 或选择其他数据副本。重新发布与启动须由研究者另行决定，失败版本的 launch.once、SQLite、release、完整错误日志和资源收据保持原样。

已通过的检查：源码与旧证据 SHA、真实软件依赖 SHA、主机/CUDA admission、20,956 场景的公开冻结元数据和完整清单资格。未完成：518 目录句柄检查、真实 payload 消费核验、实际模型/AdamW/scheduler/RNG 恢复、第一步真实更新。本次八项新增工程检查通过不能代替这些未完成项。

异常关闭时进程峰值工作集 880,586,752 bytes，private commit 2,099,130,368 bytes；CUDA allocated/reserved 为 0。新实际运行约 25.031 秒，仍计入原七日资源上限。软件身份校验与公开清单元数据的读取不属于原始观测/IMERG 像元读取。

`root_availability_failure.json` 和 `failure_receipt.json` 是脱敏证据。私有完整 traceback 及运行日志保存在忽略的 `.local/`。无自动重试、无退款、无额外实验组。
