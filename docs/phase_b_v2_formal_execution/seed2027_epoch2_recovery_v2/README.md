# seed2027：状态文件互斥修复后的第 2 轮 LAST 恢复

独立命名空间：`YUNTAPR_PHASE_B_V2_SEED2027_EPOCH2_RECOVERY_V2`。

本版本绑定研究者本对话中的真实回复“授权修复集成、恢复及额外632次额度”。仅执行既定 seed2027 六组剩余范围，不包含 seed2028、2025 或 FinalFit，不追认历史 B1 恢复。

- 恢复来源：B0/E0 epoch 2，update 10,456；payload SHA256 `b6062fe5b747924cc7cdf6cfce38f43f9f71fa9a1ad8ee10065cc987e875c3ce`。
- 历史预留 86,415、已核验返回 86,414，历史 1 次不确定调用仍计费；旧账本不改写。
- 保留有效更新 10,456；废弃运行消耗 75,959 不退款；新额度 271,856，累计上限 358,271。
- 从第 3 轮 update 10,457 开始重放；模型、AdamW、scheduler、RNG 必须完整核验后才允许首个更新。
- 科学配置与资源上限沿用冻结版本；失败停止，不自动重试、退款、换样本或重置随机数。

## 本次修复

`heartbeat.json`、`progress.json`、`execution_status.json` 的新版本写入使用已测试的 Windows 命名互斥锁；本版本状态查询和新看板读取使用同一协议。锁等待上限 2 秒，单次替换失败保留 `.part` 并停止。数据与 checkpoint 的严格句柄和同字节 SHA 读取保持原实现。

人工实验已复现 Windows 普通只读句柄阻止 `os.replace`。真实故障当时的占用句柄未被记录，不能确认唯一占用者；不参与互斥协议的外部工具仍可能导致拒绝，系统继续 fail-closed。

旧 epoch2 recovery v1 的 632 次更新、`heartbeat.json.part`、原始异常、release、SQLite 与终止收据均纳入只读祖先身份。已确认其 Worker / Supervisor 不存在、Job 不存在。

## 操作命令

在项目根目录 PowerShell 执行：

```powershell
# 当前已运行时不要重复启动；只有安全暂停完成并核验 PAUSED 后才用此命令继续。
& .\scripts\phase_b_v2_seed2027_epoch2_recovery_v2\Start-Training.ps1

# 当前完整训练、开发验证及 LAST 提交后退出。
& .\scripts\phase_b_v2_seed2027_epoch2_recovery_v2\Pause-Training.ps1

& .\scripts\phase_b_v2_seed2027_epoch2_recovery_v2\Status-Training.ps1

& .\scripts\phase_b_v2_live_monitor_epoch2_v2\Open-Monitor.ps1
```

新看板：<http://127.0.0.1:53081/>，10 秒自动刷新，仅查看当前新账本。旧 53079 / 53080 页面保留历史任务，不能代表本版本进度。关闭浏览器不会暂停训练；关机前应等待 PAUSED 和 Job 清空。

源代码与发布身份见 `release.json`；人工检查见 `TEST_RESULTS.json`；实际启动状态以 `STARTUP_VERIFICATION.json`、本地账本及实时看板为准，不把发布成功当作训练成功。

2024 结果仍为 M-C 探索性开发验证；历史 2025 路径属性访问保留 `NOT_INSTRUMENTED`，不追溯宣称系统级零访问。
