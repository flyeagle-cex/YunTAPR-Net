# seed2027 执行版本：已发布，启动由研究者暂缓

本次真实人类决定为：**“只发布执行版本，暂不启动”**。本目录记录代码发布，不生成训练授权，不代表正式训练已开始。

运行源码：`src/yuntapr/training/phase_b_v2_seed2027/`。科学配置与 `seed2027_v1/config.json` 字节相同：固定六组顺序、D1/Q1/N0/I3/B9/S0/V0、seed2027、9 轮/组、47,052 更新/组，计划上限 282,312。模型/损失/数据冻结定义没有改变。

沿用唯一 `.git/phase_b_v2_seed2027_fresh_v1.sqlite` 和 once 名称，没有另建额外额度。本轮没有创建这两个文件、session、Job、模型、优化器或 LAST，也没有读取原始数据或权重。

## 本版本命令

仓库根目录 PowerShell：

```powershell
& .\scripts\phase_b_v2_seed2027\Operator.ps1 -Action check
& .\scripts\phase_b_v2_seed2027\Status-Training.ps1
```

`check` 验证发布记录、配置 SHA、全部执行代码与启动器 SHA、Git 源码祖先及仓库身份，报告 `publication=PASS` 和 `SEED2027_LAUNCH_WITHHELD_BY_RESEARCHER`。它不是主机/CUDA/真实数据 preflight，不读取原始观测，不写额度账本。

保留的启动入口为：

```powershell
& .\scripts\phase_b_v2_seed2027\Start-Training.ps1
```

**本轮不调用该入口；当前调用仍会在 host/CUDA/Job/数据/账本操作前拒绝。** `authority.py` 按研究者决定暂缓启动，JSON、环境变量或命令行不能改为批准。以后明确要求启动时，需要绑定该新执行指令的激活版本及来源身份；本发布记录本身不能提供它。

暂停、状态和紧急停止保留同目录 `Pause-Training.ps1`、`Status-Training.ps1`、`Emergency-Stop-Training.ps1`；目前无运行进程可暂停。完整 epoch+验证+同字节 LAST、安全暂停、非退款额度、Windows Job 机制的核心算法复用原实现，不重跑模型/训练测试。

## 来源和范围

- `release.json` 固定实际源 commit、源码 pins、配置 SHA、依赖清单 SHA、资源上限，以及真实的“仅发布、暂不启动”决定；不是自签的执行批准。
- `REUSED_SOURCE_PINS.json` 核对候选代码来源；`TEST_RESULTS.json` 记录本轮新增发布/暂缓检查。
- 原准备版入口、seed2028 配置和历史记录保持原样。新增全局源码使旧准备版的完整源码快照成为历史快照；后续发布 seed2028 时须重新固定源码，不自动更新或授权。
- 六份 seed2026 权重、异盘备份、历史账本不修改。2025 不访问，历史路径属性访问仍为 `NOT_INSTRUMENTED`；历史 B1 恢复不追认。
- 本轮不验证现场 GPU、内存、存储、H: 数据权限或全量软件二进制；启动仍需原门槛全部通过。GPU 驱动崩溃与异常慢轮风险记录继续有效。
