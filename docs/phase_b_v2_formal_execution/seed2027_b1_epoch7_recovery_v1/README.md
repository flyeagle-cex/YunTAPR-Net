# seed2027：B1/E0 第七轮 LAST 授权恢复

本版本绑定真实人类回复“已接回原 H: 盘，授权恢复及额外 5,228 次额度”。旧账本、故障日志和 LAST 均保持原样。

- 保留 B0/E0 九轮完成结果与最终 SHA：`34022dd6970a95a1fc8ef7a910d5b4a80a1f029ad3617dee577d6dff2b1f4673`。不重训 B0/E0，不反序列化其权重。
- 从 B1/E0 epoch 7 / update 36,596 的 LAST 恢复，SHA：`bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a`。完整恢复模型、AdamW、scheduler、RNG，第八轮首个更新为 36,597。
- 旧消耗预留 164,835，核验返回 164,834，历史 1 次不确定调用继续计费。有效继承 83,648 次，废弃消耗 81,187 次不退款。
- 新额度 198,664；累计上限 363,499，比旧上限增加 5,228，仅补偿本次未提交第八轮的重放。
- B1/E0 第八、九轮完成后，继续原定 B0/E1、B1/E1、B0/E2、B1/E2。保持 D1/Q1/N0/I3/B9/S0/V0、E0/E1/E2、M-C 及原资源上限；不包含 seed2028、2025、FinalFit。

## 已确认的失败原因

前任务在 B1/E0 第八轮完整训练结束、开发验证尚未完成时，B13 读取报 `WinError 433`（设备不存在）；随后 Worker / Supervisor / Job 均退出。该轮未提交 LAST，不能伪装为安全暂停后直接继续。Windows 同时出现相关 USB 设备移除警告；具体断连的硬件原因尚未确定。

本版本继续使用状态文件读写互斥、同字节 SHA 数据读取、P1 checkpoint 读取和 Windows Job 监控。新任务只启动一次；失败不得通过旧启动命令、重置账本或重试继续。

## 当前版本操作命令

在项目根目录 PowerShell 中执行：

```powershell
# 仅用于本版本未启动时，或已完成安全暂停且确认 PAUSED 后继续；运行中不要重复执行。
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v1\Start-Training.ps1

# 请求当前完整 epoch（训练 + 全部开发验证 + LAST 提交）后退出。
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v1\Pause-Training.ps1

& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v1\Status-Training.ps1

& .\scripts\phase_b_v2_live_monitor_b1_epoch7\Open-Monitor.ps1
```

新监控地址：<http://127.0.0.1:53082/>，每十秒只读刷新。旧 53079 / 53080 / 53081 页面属于历史任务，不代表本版本。关闭浏览器不停止训练。

**不要在暂停请求刚提交时拔盘或关机。必须等状态显示 PAUSED、终止收据确认 Job 清空后再断开 H:。** 任务异常停止时，需要另外决定具体 LAST 和重放额度。

实际源码身份见 `release.json`；恢复差异测试见 `TEST_RESULTS.json`；启动事实见 `STARTUP_VERIFICATION.json`。权重、原始数据、完整运行日志和本机路径留在忽略的本地目录。2024 仍为探索性开发集，历史 B1 恢复不追认，历史 2025 属性访问继续标为 `NOT_INSTRUMENTED`。
