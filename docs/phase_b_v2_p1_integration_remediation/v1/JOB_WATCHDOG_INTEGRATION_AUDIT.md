# Windows Job 启动联动审计

结论：**WINDOWS_JOB_ARTIFICIAL_INTEGRATION_PASS**；新 launcher 未改旧 smoke，未向模型开放启动。

launcher.run 只接受固定人工 case，不接受路径、任意 argv、模型或批准字段。跨进程 SQLite FULL 账本在创建前预留，上限24，实际15（14外层+1内层），无退款。单例最多15秒，受控分配32 MiB，成员上限16，人工 Job commit cap256 MiB；不能用于真实模型。

复用未改 winjob.py:Job.spawn，以 PROC_THREAD_ATTRIBUTE_JOB_LIST 在创建时加入 Job，挂起验证归属后恢复。Job 句柄不继承、无 breakaway、KILL_ON_JOB_CLOSE。venv root stub 与实际 worker 分别记录，worker 根据 PID、创建 FILETIME、原生 executable 路径哈希、一次性 nonce 与 key 绑定；原生身份取自持有句柄，JSON 自报不足。

启动前 launch.json、绑定后 bound.json、终止后 termination.json 保留源码 SHA。工作集、private commit 与累计树 CPU time 分开记录。内存/CPU time/elapsed/身份/句柄异常通过 TerminateJobObject 停止拥有的树，无 taskkill/PID-only kill、重启/退款。

成功也关闭空 Job，封闭迟到后代竞争；清理证明同时要求成员为空与保留句柄 signaled。worker import guard 拒绝 Torch、NumPy、netCDF4、h5py、CuPy。

| 验证 | 状态 | 实际结果 |
|---|---|---|
| 正常 + venv stub/worker 区分 | PASS | root 与 worker PID 不同 |
| 包装进程提前退出 | PASS | root 已退出，worker 仍正确绑定/结束 |
| 登记前退出、意外退出 | PASS | 明确失败分类并清空 Job |
| 模拟内存24 MiB | PASS | 采样 WS最大53,350,400 bytes；分配32 MiB |
| 模拟累计 CPU time0.12秒 | PASS | CPU_TIME_LIMIT |
| 模拟树超时1.8秒 | PASS | 多级人工子进程全树清空 |
| 外部 monitor PID、不存在 PID | PASS | 拒绝，外部 monitor 未被终止 |
| creation/image/nonce 伪报 | PASS | 原生绑定拒绝 |
| 监控句柄失效 | PASS | 整树停止，不退回 PID kill |
| monitor os._exit(17) | PASS | 内层子进程在外层停止前已死亡，非 Python finally |
| 返回后残留 | PASS | 所有 Job 清空；末次 Get-Process 无 Python |
| GPU 树终止/驱动卡死 | NOT_VERIFIED | 禁止本轮模型/GPU |

15 个 unittest 方法首次通过，其中14个外层实际启动，1项拒绝任意 runner/APPROVED。51个观察原生身份含多层包装/leaf，不等于启动额度。最长1.828秒；外层监控合计约5.750秒，非项目总耗时。private commit 采样峰值44,195,840 bytes。证据：tests/job_initial.json、tests/job_durable_receipts.json。

崩溃 monitor 有内层 launch/bound/monitor_crash 记录，无能力自行写终止收据；外层独立观察证明清理。正式命令、资源配置、权限/预算/日志绑定仍待批准。

[Job objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[原子 Job 属性](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812)。
