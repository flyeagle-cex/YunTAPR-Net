# seed2027：四次失败后单次 fresh 重启

本次依据研究者真实答复“我已经关闭，重启吧”（关闭内存占用应用后授权重启），沿用其先前选定的额度模式，由独立命名空间执行固定六组。授权问题与答复原文绑定于 authority.py 和 release.json。前四次尝试虽有 13 份已提交 LAST（B0/E0 全部 9 轮 + B1/E0 第 1–4 轮），但按本次决定**不采用任何历史 LAST**，采用同一 seed2027 的 fresh 初始化。

前四次占用合计 70,099 次（核验 70,098、未核验 1）均保留且不可退款、不提升为核验成功。新任务最多 282,312 次，累计上限 352,411。只允许这一次失败后重启，异常不自动重试、不自动恢复。

固定顺序：B0/E0 → B1/E0 → B0/E1 → B1/E1 → B0/E2 → B1/E2。每组 9 轮、47,052 次更新，batch、精度、科学参数和资源硬上限均不改变。config.json 与原 seed2027 配置字节一致；M-C 仍仅作 2024 开发集探索性解释。不含 seed2028、2025 或 FinalFit，历史 B1 恢复不追认。

四次旧账本与日志通过只读句柄及 SHA 绑定并形成四层祖先链。第三次账本原 FAILED_NO_RETRY（WATCHDOG_TERMINATED）保持原样，原生 PID/创建时间/映像/nonce 和 Job 检查确认已退出；其终止收据如实保留（original_termination_receipt=true）。第三次两个 session（1 PAUSED、2 ACTIVE）的事件日志按闭合读取规则链式结转，末尾未闭合读取预留按保守口径记录为 abandoned 且不计入结转字节。结转资源（墙钟 143,581.0 秒、2,618,752,660,485 字节，含停机时间）继续占用原七日/32TiB 上限。

第四次失败根因为主机可用提交内存低于 10GiB 硬门槛（AVAILABLE_COMMIT_LIMIT，与第一次同因）。研究者已关闭高内存桌面应用；驱动、分页文件、TDR 及科学配置未修改；管理员级修复清单由操作员另附。原 6GiB CUDA reserved、5GiB CUDA admission、6GiB 工作集、12GiB 进程 commit、16GiB Job commit、10GiB 可用 commit 和 12GiB 磁盘门槛继续执行。Windows Job 与自动监督保留，故障后停止。

## 使用（仓库根目录 PowerShell）

```powershell
& .\scripts\phase_b_v2_seed2027_restart_v4\Operator.ps1 -Action check
& .\scripts\phase_b_v2_seed2027_restart_v4\Start-Training.ps1
& .\scripts\phase_b_v2_seed2027_restart_v4\Status-Training.ps1
& .\scripts\phase_b_v2_seed2027_restart_v4\Pause-Training.ps1
```

启动后不要重复执行 Start；ACTIVE 拒绝重复启动。Pause 等待完整训练、开发验证及 LAST 提交；只有已核验 PAUSED 可按原剩余额度继续。紧急终止使用同目录 Emergency-Stop-Training.ps1，失败后不自动恢复。新账本为 .git/phase_b_v2_seed2027_fresh_restart_v4.sqlite，权重和完整日志仅保存在本目录忽略的 .local 中。

本轮 19 项差异测试全部通过，不重跑模型测试。检查了累计额度、旧不确定更新、科学配置同字节、训练/验证/监控算法不变、checkpoint 额度元数据、四层严格祖先状态（含双 session 现场）、进程消失证据、读取账闭合（含末尾废弃预留）及来源篡改拒绝。完整真实预检和启动是否通过，以后续 STARTUP_VERIFICATION.json 及实际账本为准，不能以本 README 替代。
