# seed2027 稳定性排查与失效会话审查修复

本轮只做只读排查、独立诊断代码和人工进程测试。没有真实数据读取、模型实例化、优化器更新、驱动/系统设置修改，也没有训练重启或额外额度。

实际结果：新审查入口将遗留 ACTIVE 正确显示为 **STOPPED_UNCLEAN_NO_LAST**。原账本不改写，新目录单独追加事后观察收据，明确不是当时成功执行的 termination.json、不是PAUSED、不是恢复许可。停止的训练没有第1轮LAST，不能断点续跑。

## 使用（仓库根目录 PowerShell）

```powershell
& .\scripts\phase_b_v2_stability_review\Inspect-Training.ps1
& .\scripts\phase_b_v2_stability_review\Inspect-Training.ps1 -Record
```

第一条只读输出真实进程/Job状态、保留的账本状态和有效审查状态；第二条在新 .local/receipts 中创建不可覆盖的事后收据。两条均没有启动、恢复、修改账本或发放权限的能力。旧正式入口及其冻结源码未改变，旧Status直接显示的ACTIVE仍只是历史账本值；新的独立检查入口提供现场核验后的视图。

- STABILITY_FINDINGS.md：GPU、内存、关机和根因证据边界。
- REPAIR_AND_TESTS.md：源码映射、测试、首次失败及修复。
- STOPPED_SESSION_OBSERVATION.json：真实只读核验，累计预留1127/核验1126，新运行741全部核验。
- WINDOWS_DIAGNOSTIC_SUMMARY.json：脱敏系统事件与现状；不包含内存转储、设备序列号或私人绝对路径。
- TEST_RESULTS.json：最终17项通过及人工进程收据；首次16项中1项失败的完整原记录另行保留于私有测试目录。
- manifest.json / final_status.json：源码、证据哈希与实际边界。

不能据本轮人工进程通过宣称GPU故障已解决、真实长程训练已验证或正式恢复已批准。未启动seed2028、2025或FinalFit；历史B1恢复未追认；历史2025路径属性访问仍为NOT_INSTRUMENTED。
