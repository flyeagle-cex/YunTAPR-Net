# seed2026 异盘备份及 seeds2027/2028 批次准备

本轮完成真实备份和两个可检查的隔离批次配置。**没有启动任何新种子，没有新优化器更新、原始观测读取、2025 访问或历史权重反序列化。** 不重绘、不重算此前科研结果。

## 备份结果

六份 epoch9 LAST 的完整 payload 及其 reference、原生注册收据、identity、最终开发报告、发布结果和 source release，共 **42 个源文件，383,597,262 字节**。其中权重 payload 为 **315,858,678 字节**。目标逐份读回 SHA 全部匹配，原件未删除或覆盖。

原件所在 C: 与 D:/E:/F: 同属物理 Disk 0；目标 H: 为物理 Disk 1 的 USB 盘（exFAT）。新建版本目录标识为 `seed2026_final_20261017_v1`；真实完整路径仅保留于受控本地 `.local/backup_location.json`，不公开私有绝对路径。每个文件附独立收据，最终以 `backup_manifest.json` 宣告完成；最初的 `backup_started.json` 按审计原则保留，不被改写。

详见 [逐文件备份核验](BACKUP_VERIFICATION.json)。源和备份的卷/文件对象不同，保留源原生登记作为来源，目标另记新对象身份。**原注册对象不能直接用于从副本恢复。** 此次没有加载模型/AdamW/RNG，只完整保留此前已验证 checkpoint 的相同字节。未来从备份恢复仍要验证新对象并绑定具体 LAST 和新的恢复决定。

这是在线独立 USB 副本，不是离线/异地副本；H: 同时承载原 B13 来源，不能称为完整 3-2-1 灾备。exFAT、断电与拔盘后的持久性未做破坏性试验，不据 `fsync` 宣称已证明掉电安全。

## 两个固定批次

配置为 [seed2027](../../phase_b_v2_formal_execution/seed2027_v1/config.json) 和 [seed2028](../../phase_b_v2_formal_execution/seed2028_v1/config.json)。每批固定顺序：B0/E0 → B1/E0 → B0/E1 → B1/E1 → B0/E2 → B1/E2。

每批 6×9×5,228 = **282,312 次更新尝试上限**，每组 47,052；两批合计 564,624。没有创建真实额度 SQLite、once、训练进程或模型。各批未来使用独立 `.git/phase_b_v2_seed{seed}_fresh_v1.sqlite`、namespace、session、LAST schema 和输出，不能借旧 seed2026 额度，也不能跨批退款或叠加。

设计维持 D1/Q1/N0/I3/B9/S0/V0、E0/E1/E2、2023 Train 10,455 / 2024 Development 10,501、冻结 mask/scaler/SP04。每模型每臂使用相应 seed 的 fresh 配对初始化；训练排列种子为 `seed+epoch-1`。**PYTHONHASHSEED 仍固定 2026，Bootstrap 抽样 seed 也仍为 2026**，它们与模型初始化 seed 的含义不同，不擅自一起替换。

`prepared_release.json` 绑定实际代码 commit、全代码/启动器 SHA、配置 SHA 和既有软件依赖清单 SHA；它不是授权记录。未来启动时仍须核对依赖实际字节、同字节真实数据身份、GPU/内存/存储及新 release。

## 命令

在仓库根目录 PowerShell 执行。以下 `check` 只核对配置与源码，不读取原始数据，也不启动训练：

```powershell
& .\scripts\phase_b_v2_replication\Operator.ps1 -Seed 2027 -Action check
& .\scripts\phase_b_v2_replication\Operator.ps1 -Seed 2028 -Action check
```

未来获得对应批次的独立执行授权、绑定正式 release 后，启动入口为：

```powershell
& .\scripts\phase_b_v2_replication\Start-Training.ps1 -Seed 2027
# 等 seed2027 六组全部完成，才可启动下一批：
& .\scripts\phase_b_v2_replication\Start-Training.ps1 -Seed 2028
```

**本轮这两条启动命令会明确拒绝，且在真实数据、GPU、Job 或账本初始化之前拒绝。** `authority.py:require_execution_authority` 保持拒绝，没有 `--approved`、JSON 或布尔值开关。这是准备状态的真实边界，不应把命令存在或 check 通过理解成已经取得执行许可。

正常安全暂停、只读状态及紧急终止分别为：

```powershell
& .\scripts\phase_b_v2_replication\Pause-Training.ps1 -Seed 2027
& .\scripts\phase_b_v2_replication\Status-Training.ps1 -Seed 2027
& .\scripts\phase_b_v2_replication\Emergency-Stop-Training.ps1 -Seed 2027
```

2028 将参数改为 2028。正常暂停等待完整 epoch、完整开发验证及已核验 LAST，复用原 Job 退出收据；FAILED/不确定更新不自动恢复、不退款。2028 必须看到 2027 的六组/54 轮完整提交和 282,312 次核验返回账本，避免两个批次并发争抢 GPU。

## 耗时、空间与实际启动阻塞

每批实测比例估计：核心训练+验证 **62.63 h**，按历史全部活动开销 **66.25 h**；后者增加 25% 规划余量为 **82.81 h（约 3.45 天连续占用）**。这不是保证、统计区间或预算放宽；既有 GPU 驱动崩溃和 B1/E2 验证极慢轮均保留，根因未确立。

每批本地 54 份 LAST payload 约 **2.65 GiB**、日志约 **3.79 GiB**、按实测比例的分数 DB 约 **0.019 GiB**。加 12 GiB 磁盘余量，约需 **18.46 GiB 本地可用空间**；按全部分数 DB 达到 256 MiB 上限则需约 **31.94 GiB**。这不含未知临时开销。若未来每轮在 H: 再保留一份独立副本，另需约 **2.65 GiB/批**。本轮只完成旧六份最终备份，没有自动向未来训练循环增加新的异盘复制 hook。

原硬限不变：7 天、32 TiB 内容读取、CUDA reserved 6 GiB/启动空闲 5 GiB、进程 WS 6 GiB/private commit 12 GiB、Job commit 16 GiB、系统可用 RAM 6 GiB/commit 10 GiB、磁盘空闲 12 GiB。实际每次未来启动都要重新检查。

具体阻塞只有以下事实，不生成新的科学方案：

1. 本轮没有新种子执行授权；`authority.py` 拒绝，正式 `release.json` 未签发。未来明确委托执行时，需发布绑定该真实指令的版本，不能只改配置布尔值。
2. 新 seed 作用域已静态/元数据核验，但没有做新的真实数据 preflight 或模型更新；实际设备、H: 路径、软件字节及资源准入必须在获准启动时核对。
3. 当前 C: 空间够单批名义需求；两批长期保留若分数 DB 均接近硬上限，需要更多空间或另行审查存储部署，不能假装磁盘保证充足。不得因此自动删除原件。
4. 从新副本恢复未测试；失败恢复仍需具体 LAST 和额度决定。长程热/驱动/掉电风险未由本轮静态检查消除。

新增候选仅适配 seed/独立额度/新命名空间/无历史恢复分支；训练、验证、P1 同字节 checkpoint、安全暂停及 Job 核心方法均按 AST/字节与旧已验证实现核对，详见 [测试与复用审计](TEST_RESULTS.json)。没有重跑旧模型、绘图或统计套件。
