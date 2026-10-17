# seed2027 正式激活与启动

研究者本次真实答复为“授权激活并启动 seed2027”，撤销此前“只发布、暂不启动”。实际问题全文及问题身份绑定在 release.json；它记录真实指令的来源，不是自签授权服务。旧发布包和旧决定不改写。

仅限固定顺序 B0/E0、B1/E0、B0/E1、B1/E1、B0/E2、B1/E2；seed2027，每组9轮、47,052次更新尝试，合计282,312次。D1/Q1/N0/I3/B9/S0/V0、M-C、数据与资源上限均不变。config.json 与原候选字节相同，里面的 preparation 标识不充当授权；执行范围来自本次独立人类指令与固定源码。

继续使用唯一 .git/phase_b_v2_seed2027_fresh_v1.sqlite 和 .once，失败不重试、不退款、不自动恢复。未增加第二套额度。旧 seed2026 权重、备份和账本不修改；不含seed2028、2025、FinalFit或历史B1恢复追认。历史2025路径属性审计仍为 NOT_INSTRUMENTED。

## 操作命令（仓库根目录 PowerShell）

```powershell
& .\scripts\phase_b_v2_seed2027\Operator.ps1 -Action check
& .\scripts\phase_b_v2_seed2027\Start-Training.ps1
& .\scripts\phase_b_v2_seed2027\Status-Training.ps1
& .\scripts\phase_b_v2_seed2027\Pause-Training.ps1
```

启动只能调用一次；异常后不能通过再次调用恢复。暂停等待完整训练轮、开发验证及同字节LAST提交后退出；紧急终止命令同目录 Emergency-Stop-Training.ps1，终止后的恢复需新决定。

启动后自动Windows Job监督进程树、内存、时间、磁盘和GPU上限。工作进程在首次更新前复核冻结依赖、518目录句柄、67,006文件引用元数据、scaler/mask/SP04；每次实际消费原始数据执行同字节SHA。不会重复全量274GiB扫描。源与协议版本在 release.json 固定。

权重、原始数据、完整路径和私有session日志位于忽略的 .local，不能上传。公开结果限安全汇总。执行状态以实际SQLite账本、session收据和 execution_status.json 为准；激活记录本身不代表训练已成功。

GPU驱动崩溃及异常慢轮的原因仍未确定；一次短程通过不证明长程稳定或业务近实时能力。不用2024结果临时选择或修改预算。其他两个种子的启动范围均未批准。
