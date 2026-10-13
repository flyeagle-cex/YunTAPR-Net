# seed2026：第七轮 LAST 恢复与手动启停

本版本依据研究者“继续训练，然后把启动训练和暂停训练的命令给我”及“完整 epoch 后安全暂停”的回复，仅继续 B1/E1 第八、九轮与 B0/E2、B1/E2。原三个完成组不重跑。恢复源是第七轮完整 LAST：`2058390159ecc9195acf9812078ac56f7e63756bf3f176228e3c1ed6c1cf0ec2`。

历史 186,891 次更新不退款；本命名空间最多 104,560 次。包括第八轮 3,911 次重放，累计上限为 291,451。所有手动启停共用这一份 SQLite 账本，不能通过重启、改名或改目录增加预算。

在仓库根目录的 PowerShell 中使用：

```powershell
& .\scripts\phase_b_v2_operator\Start-Training.ps1
& .\scripts\phase_b_v2_operator\Pause-Training.ps1
& .\scripts\phase_b_v2_operator\Status-Training.ps1
& .\scripts\phase_b_v2_operator\Emergency-Stop-Training.ps1
```

- 启动：第一次运行本次已授权恢复；此后只能从本版本确认关闭 Job 的 `PAUSED` 边界接续。正在运行时重复启动被拒绝。`FAILED_NO_RETRY` 与 `COMPLETE` 不可重启。
- 暂停：立即登记持久化请求，阻止下一轮和下一组开始；当前轮训练、完整开发验证、同字节 checkpoint 核验、LAST 与进度提交成功后，释放模型和 Job。命令返回请求已登记，并不表示 GPU 已经停止；通过状态命令确认 `PAUSED`、`job_empty_and_handles_signaled=true`。
- 紧急停止：先绑定本次 Supervisor 的 PID、创建时间、原生 executable 身份及 nonce 命名的 Windows Job，再终止所属进程树。失败或不确定更新仍计为已消耗；后续恢复必须另行决定具体 LAST 与重放额度。

权重、原始访问记录、运行时私有配置与人工测试现场只留本地 `.local/`。禁止删改 `.git/phase_b_v2_seed2026_epoch7_operator_v1.sqlite` 或对应 `.once`。H: 冻结源盘、固定 CUDA 环境和所有原资源上限仍须可用；入口不自动重试或降低模型、batch、精度。

训练与评价方法沿用旧版本；新增检查证明 `train`/`validate` 的 AST 未改变。2024 是开发集，M-C 只作探索解释；2025、seeds 2027/2028、FinalFit 不在范围内，历史 B1 恢复未追认。

测试初次联合运行 23 通过、1 失败：测试只等待 Job 成员消失，未等待所有进程句柄退出信号。实际停止实现已等待两者；测试改正后 24 项通过，0 失败，无真实数据或 optimizer 调用。原失败日志保留本地，汇总见 `test_results.json`。

完整长程实际安全暂停/重启的实测状态以运行收据为准，不能由人工测试替代。源码固定后不得在训练期间更改 `src/` 或冻结科学配置。
