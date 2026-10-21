# seed2027 B1/E0 epoch7 恢复 v2：独立系统任务 Owner

研究者本次直接回复：**授权修复集成、恢复及额外548次额度**。问题与回复逐字绑定于 `authority.py`；这不是从配置或测试自行取得授权。

保留旧任务全部证据及累计 **165,383** 次已预留（165,382 次核验，历史 1 次不确定尝试继续计费）。新增恢复运行最多 **198,664** 次，累计硬上限 **364,047**；比上一授权增加 548 次。原资源上限、D1/Q1/N0/I3/B9/S0/V0、M-C 及科学参数完全不变。

* 已完成 B0/E0 epoch9 保留，最终 SHA `34022dd6970a95a1fc8ef7a910d5b4a80a1f029ad3617dee577d6dff2b1f4673`。
* B1/E0 从指定 epoch7 LAST `bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a` 完整恢复 model/AdamW/scheduler/RNG，重放 epoch8，完成 epoch9。
* 再固定执行 B0/E1、B1/E1、B0/E2、B1/E2，各九轮。不含 seed2028、FinalFit、2025；历史 B1 恢复未追认。
* 旧进程已不存在、旧账本 ACTIVE 原样封存；没有补造历史终止收据。新账本和所有新产物使用独立 v2 命名空间。

## 启动寿命修复

正式 Owner 由当前用户的按需 Windows 系统任务创建，固定脚本、解释器、源码 SHA、会话和 nonce；零触发器、零自动重试、Limited 权限。PowerShell 引导在创建 Python 前设置 PYTHONHASHSEED=2026。Worker 仍归属原资源受限的 KILL_ON_JOB_CLOSE Job，未绕过 watchdog。

原机制的 8 项人工进程测试已通过；本次接入另有 10 项纯人工元数据/SQL/静态差异测试。训练与评价主循环、梯度裁剪、S0、模型和损失未改写。实际恢复状态与第一笔优化器核验以 `STARTUP_VERIFICATION.json` 为准，不能以测试代替。

## 本版本操作命令

在项目根目录的独立 Windows PowerShell 中：

```powershell
# 只读状态
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v2\Operator.ps1 -Action status
# 请求完成当前 epoch、开发验证和 LAST 事务后暂停
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v2\Pause-Training.ps1
# 仅 READY 或已核验 PAUSED 可以启动；FAILED 不自动恢复
& .\scripts\phase_b_v2_seed2027_b1_epoch7_recovery_v2\Start-Training.ps1
# 新只读看板，10 秒刷新，端口 53083
& .\scripts\phase_b_v2_live_monitor_b1_epoch7_v2\Open-Monitor.ps1
```

运行期间再执行启动命令应拒绝重复会话。若出现错误、资源超限、不确定更新或 Checkpoint 异常，停止且不重试、不退款；新的失败恢复需要研究者另行决定。系统任务没有自动登录/重启触发器，不会在重启电脑后自动重新训练。

关闭 Codex 的人工复现不是原事故的内核追踪；本次不声称已唯一证明原始终止调用者，也不声称 GPU 驱动与长程稳定性已经解决。2025 历史路径属性查询仍为 NOT_INSTRUMENTED。
