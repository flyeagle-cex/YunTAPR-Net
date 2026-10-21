# seed2027：零更新接口修复后单次重新发布

直接研究者决定：**授权零更新修复后重新发布并启动一次**。原问答由本版本 `authority.py` 固定。保留 v4/v5 失败、旧账本和全部 166,305 次已消耗尝试；累计上限仍为 364,969，本次不增加额度。

恢复源：B1/E0 第七轮 LAST，SHA `bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a`。B0/E0 第九轮结果保持完成；从 B1/E0 第八轮开始，随后按固定顺序执行 B0/E1、B1/E1、B0/E2、B1/E2。剩余额度 198,664，不包含 seed2028、FinalFit 或 2025。

三项祖先路径常量显式取自原 v4 提供者，避免 v5 的遗漏。Checkpoint 使用既有同字节 SHA reader；模型、AdamW、RNG、scheduler 全部验证后恢复。训练、验证和数值定义保持不变。

Windows 系统任务通过固定 GUI bootstrap 启动，实际 Owner/Worker 在科学导入前脱离控制台，Job 保留 kill-on-close 和原资源限制。关闭 Codex 不作为停止命令；电脑须开机、不休眠，原 H: 数据盘须持续连接。系统重启后不自动恢复。

## 操作命令

在项目根目录的 PowerShell 中执行：

```powershell
# 查看状态
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v6\Operator.ps1 -Action status

# 首次启动，或已完整安全暂停后的继续
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v6\Start-Training.ps1

# 等当前完整 epoch、开发验证和 LAST 提交后退出
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v6\Pause-Training.ps1

# 打开当前版本的实时页面（每 10 秒只读刷新）
& .\scripts\phase_b_v2_live_monitor_b1_epoch7_v6\Open-Monitor.ps1
```

监控地址：`http://127.0.0.1:53087/`。旧的 53082/53084/53085/53086 页面不代表本版本。

不要在 RUNNING 时重复 Start。FAILED、异常中断或不完整事务仍不能用 Start 自动恢复。紧急终止使用本版本 `Operator.ps1 -Action emergency-stop`，只停止绑定的所属 Job，不按 PID 批量结束 Python；紧急终止后恢复须另行决定。

## 发布前检查

13 项差异测试、5 项实际消费函数/接口测试、5 项监控异常测试；均不执行真实模型或 optimizer 更新。封存祖先逐字节核验 261 个登记证据对象，指定 LAST SHA 匹配；旧账本、模型与证据不改写。源码与协议由 release.json 绑定到实际 Git commit 和完整 source pins。

发布前封存曾因新输出目录仍引用 v5 而拒绝覆盖；该失败保存在 `.local/PREPARE_ANCESTOR.log`，已修正并增加命名空间测试，未创建正式账本、未消费更新额度。

资源继承全部既有计费并保持原上限：7 日累计时间、32 TiB 内容读取、6 GiB 工作集、12 GiB 进程提交、16 GiB Job 提交、CUDA reserved 6 GiB；准入要求 CUDA free 至少 5 GiB、可用 RAM 6 GiB、可用 commit 10 GiB、磁盘空闲 12 GiB。资源不足、数据 SHA 不符、非有限值或事务异常均停止，不自动调整或重试。

最终启动事实以 STARTUP_VERIFICATION.json、SQLite 账本及实时 execution_status.json 为准；本 README 不是运行完成证据。M-C 探索性解释不变，2024 仍为开发集，历史 B1 恢复偏差未追认，历史 2025 路径属性审计仍为 NOT_INSTRUMENTED。
