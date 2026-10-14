# seed2026：紧急停止后获准恢复（operator v2）

研究者独立回复“授权此恢复及 5,228 次额外额度”。本版本从 B1/E1 第七轮 LAST `2058390159ecc9195acf9812078ac56f7e63756bf3f176228e3c1ed6c1cf0ec2` 恢复，重放第八轮，然后完成第九轮和两个 E2 组。固定科学配置、顺序和全部资源上限保持原值。

旧 operator v1 在 2026-10-14 00:09（北京时间）被紧急终止：第八轮 5,228 次更新全部返回，停在 `WAIT_VALIDATION`，没有第八轮 LAST。旧 192,119 次不退款；新命名空间最多 104,560 次，累计上限 296,679（282,312 科学计划更新＋14,367 次历史重放）。旧 SQLite、once、权重、停止收据均保留。

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

四条按需要分别使用，不是连续运行的流程。重复启动被拒绝；FAILED 不自动重启。启停共用固定 `.git/phase_b_v2_seed2026_epoch7_operator_v2.sqlite` 和对应 once，不能删除、重置或换目录增加额度。

本次新增祖先和范围测试 10 项通过，0 失败，无真实数据/模型/optimizer 操作；复用原 24 项启停/人工 Job/checkpoint 检查，不重跑旧套件。训练、验证、完整状态恢复和同字节读取方法通过 AST 对照。

首次启动前检查因原 H: 盘未挂载失败；新 SQLite/once 均未建立，优化器预留和调用为零。研究者确认重新连接后再次检查。首次失败证据保留 `.local/prelaunch_failure_01.json`，失败检查耗时和保守元数据读取额度也计入原资源上限。

权重和私有运行文件仅保存于本地 `.local/`，不上传 GitHub。2024 仍为开发集；M-C 探索解释、2025 封存、其他种子与 FinalFit 未授权、历史 B1 恢复未追认。源码固定后不修改运行中的 src/科学配置。
