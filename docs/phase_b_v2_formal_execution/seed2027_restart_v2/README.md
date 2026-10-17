# seed2027：两次失败后单次 fresh 重启

本次依据研究者真实答复“授权重启及额外 741 次额度”，由独立命名空间执行固定六组。授权问题和答复原文绑定于 authority.py 和 release.json。没有 LAST，故采用同一 seed2027 的 fresh 初始化，不是 checkpoint 恢复。

旧任务386次占用（385次核验）及第二次741次占用（741次全部核验）均保留，合计1127次占用、1126次核验。新任务最多282312次，累计上限283439；历史1次未核验不退款、不提升为核验成功。只允许这一次失败后重启，异常不自动重试。

固定顺序：B0/E0 → B1/E0 → B0/E1 → B1/E1 → B0/E2 → B1/E2。每组9轮、47052次更新，batch、精度、科学参数和资源硬上限均不改变。config.json与原seed2027配置字节一致；M-C仍仅作2024开发集探索性解释。不含seed2028、2025或FinalFit，历史B1恢复不追认。

两次旧账本和日志通过只读句柄及SHA绑定。第二次账本原ACTIVE保持原样，独立原生PID/创建时间/映像/nonce和Job检查确认已退出；没有补造历史终止收据。第二次全部已登记读取事务闭合，累计读取11043114409字节。缺少退出时刻，因此保守计入从其启动至本次封存的墙钟时间（含停机），加前次时间共40596.84523秒，继续占用原七日上限；此数不是GPU训练时间。

GPU驱动事件根因尚未确定，本次没有修改驱动、TDR、分页文件、模型或资源门槛。原6GiB CUDA reserved、5GiB CUDA admission、6GiB工作集、12GiB进程commit、16GiB Job commit、10GiB可用commit和12GiB磁盘门槛继续执行。Windows Job与自动监督保留，故障后停止。

## 使用（仓库根目录 PowerShell）

```powershell
& .\scripts\phase_b_v2_seed2027_restart_v2\Operator.ps1 -Action check
& .\scripts\phase_b_v2_seed2027_restart_v2\Start-Training.ps1
& .\scripts\phase_b_v2_seed2027_restart_v2\Status-Training.ps1
& .\scripts\phase_b_v2_seed2027_restart_v2\Pause-Training.ps1
```

启动后不要重复执行Start；ACTIVE拒绝重复启动。Pause等待完整训练、开发验证及LAST提交；只有已核验PAUSED可按原剩余额度继续。紧急终止使用同目录Emergency-Stop-Training.ps1，失败后不自动恢复。新账本为.git/phase_b_v2_seed2027_fresh_restart_v2.sqlite，权重和完整日志仅保存在本目录忽略的.local中。

本轮19项差异测试全部通过，不重跑模型测试。检查了累计额度、旧不确定更新、科学配置同字节、训练/验证/监控算法不变、checkpoint额度元数据、严格祖先状态、进程消失证据、读取账闭合及来源篡改拒绝。完整真实预检和启动是否通过，以后续STARTUP_VERIFICATION.json及实际账本为准，不能以本README替代。
