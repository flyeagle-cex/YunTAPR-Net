# seed2027：第 2 轮 LAST 恢复与第 3 轮重放

研究者本次明确回复“授权从第2轮 LAST 恢复及额外5228次额度”。只启动一次；任何异常停止，不自动重试或再次恢复。

- 指定源：B0/E0 epoch 2 LAST，SHA `b6062fe5b747924cc7cdf6cfce38f43f9f71fa9a1ad8ee10065cc987e875c3ce`。
- 保留全部 85,783 次既有预留（85,782 次已核验，历史 1 次不确定调用仍计费）。
- 原任务第 3 轮已更新但验证未完成，无第 3 轮 LAST。重放 5,228 次已获明确授权，总上限从 352,411 调整为 357,639。
- 继承有效前两轮 10,456 次更新；剩余运行范围 271,856 次。旧废弃消耗为 75,327 次，不退款。
- 先从第 3 轮继续 B0/E0，再按 B1/E0、B0/E1、B1/E1、B0/E2、B1/E2 的既定顺序完成 seed2027；其他 seed 不授权。

## 本次检查

旧 Worker、Supervisor 和 Job 均不存在。原账本仍为 ACTIVE，只记录为系统开机后的失效会话观察，不改写为 PAUSED/FAILED，也不伪造旧终止收据。旧 release、源码、SQLite、launch.once、权重与日志完整保留。新 DB 仅复制前两轮 LAST_COMMITTED 边界；旧第 3 轮 WAIT_VALIDATION 留在旧账本。

129 份祖先文件共 965,341,273 字节采用流式 SHA 固定，约 4.45 秒。只对指定第 2 轮 payload 做 `weights_only=True` 反序列化预检，完整训练/验证报告规范化 SHA 与验证收据通过；未创建模型、应用状态或调用 optimizer。实际模型、AdamW、scheduler、RNG 恢复在正式 Worker 中使用已验证的旧 Contract 和同字节 reader，再核验状态摘要。

10 项本次差异检查通过：累计额度、源失效会话、复制前两轮边界、首个更新 10,457、禁止重复消费、暂停边界、科学配置、未变训练与监控算法、规范化报告和新 checkpoint 额度。只做人工 SQLite 与静态检查，未重新跑旧合成训练套件。

准备期间发生一个 Windows GBK 默认编码的辅助编辑错误，以及测试隔离命名空间漏提供 `re` 的夹具错误；均已修复并保留本地首次记录，未发生正式更新。没有通过改动科学参数或放宽校验来通过测试。

资源上限全部沿用。保留已计费内容 2,923,758,463,579 字节；时间按祖先消耗加源启动至观察时刻保守计费（包括停机时间），不是 GPU 运行时长。不会重置 7 日 / 32 TiB 等硬上限。

## 操作命令

在仓库根目录 PowerShell 中：

```powershell
# 启动，或从本版本已核验的安全 PAUSED 状态继续
& .\scripts\phase_b_v2_seed2027_epoch2_recovery_v1\Start-Training.ps1

# 请求当前完整训练、开发验证、LAST 提交结束后暂停
& .\scripts\phase_b_v2_seed2027_epoch2_recovery_v1\Pause-Training.ps1

# 查询状态；关机前必须确认 PAUSED，不能只看“暂停请求已发送”
& .\scripts\phase_b_v2_seed2027_epoch2_recovery_v1\Status-Training.ps1

# 打开本版本实时监控，每 10 秒刷新
& .\scripts\phase_b_v2_live_monitor_epoch2\Open-Monitor.ps1
```

新地址：http://127.0.0.1:53080/。53079 对应旧失效任务。关闭页面不会暂停训练；ACTIVE 拒绝重复启动，未正常退出的任务也不会由 start 自动重置或重放。

E0/E1/E2、D1/Q1/N0/I3/B9/S0/V0、精度、LR、AdamW、clip、M-C / 2024 开发探索性解释均不改变。2025 与 FinalFit 不授权；历史 B1 恢复未追认，历史 2025 路径属性查询仍为 NOT_INSTRUMENTED。
