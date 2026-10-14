# seed2026：GPU 崩溃后获准恢复（operator v3）

研究者回复“从 B1/E1 第 7 轮 LAST 205839…（update 36596）恢复并重放第 8 轮；本次已记账未落盘的 1,795 次更新不退款；累计上限 296,679 → 298,474；种子 2026、固定顺序与全部资源上限不变。”本版本从同一 epoch-7 LAST `2058390159ecc9195acf9812078ac56f7e63756bf3f176228e3c1ed6c1cf0ec2` 恢复，重放第八轮，然后完成第九轮和两个 E2 组。固定科学配置、顺序和全部资源上限保持原值。

旧 operator v2 在 2026-10-14 08:26:59（北京时间）训练中被 GPU 驱动错误无痕杀死（系统日志 `nvlddmkm` 事件 153 + `LiveKernelEvent`）：第 8 轮重放完成 1,795/5,228 次更新且全部验证记账，没有第 8 轮 LAST，没有终止收据，supervisor 与 worker 同时消失。该 1,795 次不退款；旧 193,914 次全部保留。新命名空间最多 104,560 次，累计上限 298,474。旧 SQLite、once、权重、心跳与审计日志均保留。

在仓库根目录的 PowerShell 中，启动或从本版本安全暂停后继续：

```powershell
& .\scripts\phase_b_v2_operator\Start-Training.ps1
```

请求完整 epoch（训练＋完整开发验证＋已核验 LAST）后安全暂停：

```powershell
& .\scripts\phase_b_v2_operator\Pause-Training.ps1
```

查看只读状态：

```powershell
& .\scripts\phase_b_v2_operator\Status-Training.ps1
```

紧急终止本次所属 Job（之后恢复仍需另行决定 LAST 和重放额度）：

```powershell
& .\scripts\phase_b_v2_operator\Emergency-Stop-Training.ps1
```

可视化监控（浏览器打开 `scripts\phase_b_v2_operator\monitor.html` 自动刷新；含总进度、每 run 进度条、配额、心跳新鲜度告警、GPU 与 ETA）：

```powershell
& .\scripts\phase_b_v2_operator\Monitor-Training.ps1
& .\scripts\phase_b_v2_operator\Start-Training-Monitored.ps1   # 启动并进入监控
```

四条按需要分别使用，不是连续运行的流程。重复启动被拒绝；FAILED 不自动重启。启停共用固定 `.git/phase_b_v2_seed2026_epoch7_operator_v3.sqlite` 和对应 once，不能删除、重置或换目录增加额度。

本次新增祖先和范围测试 10 项通过，0 失败，无真实数据/模型/optimizer 操作；复用原 24 项启停/人工 Job/checkpoint 检查，不重跑旧套件。训练、验证、完整状态恢复和同字节读取方法通过 AST 对照，与 v2 一致。

权重和私有运行文件仅保存于本地 `.local/`，不上传 GitHub。2024 仍为开发集；M-C 探索解释、2025 封存、其他种子与 FinalFit 未授权、历史 B1 恢复未追认。源码固定后不修改运行中的 src/科学配置。
