# seed2027 epoch7 恢复 v3：脱离 Codex 的系统任务

研究者本次直接指令：“给我恢复然后继续进程，需要退出codex也能继续”；并确认仅脱离 Codex，电脑保持开机、不休眠，重启后不自动恢复。

沿用指定 B1/E0 第七轮 LAST `bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a`。B0/E0 完成结果保留；重跑 B1/E0 第八轮并完成第九轮，然后固定执行 B0/E1、B1/E1、B0/E2、B1/E2。科学设计、随机种子、数据与全部资源上限不变。

旧 v2 启动消耗为零、Job 已清空；旧任务、launch.once、SQLite 和错误收据全部封存。累计历史预留仍为 **165,383**（核验 165,382，历史一笔不确定尝试继续计费）；剩余额度 **198,664**，总上限 **364,047**，本次不增加额度。

## 修复与证据边界

训练 Supervisor 由独立的按需 Windows 系统任务创建，不依赖 Codex 的进程寿命。固定脚本、源码、解释器、会话和 nonce；Limited 权限、无计划触发器、无自动重试。Worker 保持原 Windows Job 资源限额及 KILL_ON_JOB_CLOSE。监控网页也使用独立的只读系统任务，10 秒刷新。

上次 WinError 5 的具体调用没有被旧收据记录，人工复现未触发该错误，**不能宣称根因已唯一定位**。新版把监控 API 分阶段记录，并在失败时仅向本地私有文件写完整调用栈；任何权限错误依然停止，不忽略、不提权、不放宽资源限制。15 项差异/负面测试及一项原生人工监控联调通过，没有新模型或优化器测试。

真实恢复是否成功，以 `STARTUP_VERIFICATION.json` 的实际 model/AdamW/scheduler/RNG 校验与首笔更新为准。通过人工测试不等于真实训练成功。

## 操作

在项目根目录的独立 Windows PowerShell 中：

```powershell
# 状态
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v3\Status-Training.ps1
# 完整 epoch、开发验证及 LAST 提交后安全暂停
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v3\Pause-Training.ps1
# 仅初次 READY 或已经核验的 PAUSED 可启动；运行中不必重复执行
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v3\Start-Training.ps1
# 打开本次实时网页 http://127.0.0.1:53084/
& .\scripts\phase_b_v2_live_monitor_b1_epoch7_v3\Open-Monitor.ps1
```

旧端口 53082/53083 展示旧任务，不用于判断本次进度。关闭 Codex 不会主动请求暂停；电脑休眠、关机、重启和 GPU/磁盘故障并未因此解决。本轮未修改系统休眠、电源、驱动或自动登录设置。

若本次出现异常，停止且不自动重试或恢复；额外种子、2025、FinalFit 不在范围内。历史 B1 恢复未追认；历史 2025 路径属性访问仍为 NOT_INSTRUMENTED。
