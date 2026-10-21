# 关闭 Codex 后训练中断：进程寿命隔离修复

状态：`OWNER_LIFETIME_SYNTHETIC_REPAIR_PASS`；正式训练没有重新启动。

## 实际停机状态

2026-10-21 08:23:09（UTC+08）只读快照确认：原 Supervisor、Worker、命名 Job 均不存在；旧 SQLite 仍为 `ACTIVE`。这是失效会话记录，不能解释成计算仍在进行，也不能直接重置为可启动。

最后一笔已核验更新发生于 07:58:09。本次失败会话的 548 次更新全部已核验、继续计费；累计预留 165,383、核验 165,382，差额为此前已保留的一笔不确定尝试。B0/E0 已完成第 9 轮；B1/E0 第 8 轮中断，第 7 轮仍是最后登记的完整 LAST。

旧账本只读 SHA：`fa24d74bb16433a525afdf59836c691c4aceabc32d7105ff3ef96fd1d9951363`。修复前后相同，没有修改或补造历史终止收据。本轮没有再次读取 LAST 的权重字节，状态检查因此保留 `LAST_NOT_VERIFIED`，不能据此冒充新一轮恢复核验。

## 原因与证据强度

研究者确认当时关闭了 Codex。旧启动器仅设置 `CREATE_NO_WINDOW`：它隐藏窗口，却不解除父进程 Job 继承。若外层 Job 随宿主结束，Supervisor 会被终止；它持有的 Worker Job 设置了 `KILL_ON_JOB_CLOSE`，随后也会清空 Worker。被直接终止时，Python `finally` 来不及写失败收据，账本可能停留于 `ACTIVE`。

人工进程复现了这条链路，并验证了修复机制。原事故没有留下内核终止追踪，不能把该复现说成已唯一证明原进程的实际终止调用者。Windows 的 [Job 继承规则](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[嵌套 Job](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs)及[创建标志](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)是机制依据。

## 已实现并执行的修复候选

* `task_bridge.py`：固定人工 Owner 通过 Windows 任务计划程序按需启动，当前用户、Limited 权限、零触发器、零自动重试。它不属于模拟 Codex Job，允许属于系统自己的 Job。没有创建正式训练任务。
* `fixture.py`：Owner 继续持有已审计的 Worker Job；Owner 正常停止或异常消失，Worker 都必须退出。覆盖实际训练 venv 的包装进程/原生工作进程身份差异。
* `audit.py`：使用 PID、创建时间、原生 executable 摘要和 Job 存在性只读判定；`ACTIVE` 不再被当成进程存活证明，未知探测结果仍然拒绝推断。
* 正式启动器、历史账本、模型、科学定义、旧 LAST 均未改动；没有注册能够启动真实训练的任务。

最终统一命令已由 Codex 实际执行：8 项通过、0 失败、0 跳过。三项任务寿命测试分别约 2.52、2.27、2.34 秒（不含测试框架及任务服务开销）。全部人工进程和临时任务已清理。见 [TEST_RESULTS.json](TEST_RESULTS.json)、[FAILURES_AND_REPAIRS.md](FAILURES_AND_REPAIRS.md)。

```powershell
# 只读状态；不会启动、重置或恢复训练。
& .\scripts\phase_b_v2_owner_lifetime_candidate\Status-Training.ps1

# 仅人工进程：4 项只读审计 + 1 项旧行为复现 + 3 项系统任务寿命测试。
& .\scripts\phase_b_v2_owner_lifetime_candidate\Test-Owner-Lifetime.ps1
```

## 尚未执行

正式接入差异列于 [INTEGRATION_DIFF.md](INTEGRATION_DIFF.md)。真实训练仍处于停止状态；不能用原 `Start-Training.ps1` 绕过失效会话。

若研究者决定从 B1/E0 第 7 轮 LAST 恢复，需要保留本次 548 次已消耗额度并单独增加 548 次重放额度：累计上限 363,499 → 364,047。对应 LAST SHA 为 `bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a`。这项恢复及额度尚未授权；本交付不是授权事件。

本轮原始数据读取、权重读取、模型/GPU 操作、optimizer 更新均为 0。2025 像元读取为 0；历史 2025 路径属性查询维持 `NOT_INSTRUMENTED`，不作追溯性系统级零访问声明。
