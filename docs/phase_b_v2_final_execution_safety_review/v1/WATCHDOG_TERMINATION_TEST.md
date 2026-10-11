# 受控终止测试

状态：**WATCHDOG_SYNTHETIC_TERMINATION_PASS**。使用 Windows venv 包装器及真实底层 CPython 进程，未加载模型或 GPU。Job 在 CreateProcess 时通过属性列表原子加入，未启用 breakaway。`TerminateJobObject` 停止 owned Job；保留句柄等待退出，查询 Job 活跃 PID 为零。外来 PID 不属于此 Job，拒绝后只终止自己的树。

| 用例 | 状态 | 实际结果/停止原因 | 秒 |
|---|---|---|---:|
| success | PASS | NORMAL_COMPLETION | 0.375 |
| wrapper_exit | PASS | NORMAL_COMPLETION | 0.547 |
| before_registration | PASS | EXIT_BEFORE_IDENTITY | 0.141 |
| unexpected_exit | PASS | WORKER_UNEXPECTED_EXIT | 0.312 |
| memory | PASS | CPU_WORKING_SET_LIMIT | 0.187 |
| tree_timeout | PASS | ELAPSED_TIME_LIMIT | 1.828 |
| foreign_pid | PASS | MONITOR_OR_IDENTITY_FAILURE | 0.281 |
| missing_pid | PASS | MONITOR_OR_IDENTITY_FAILURE | 0.250 |
| bad_creation | PASS | MONITOR_OR_IDENTITY_FAILURE | 0.218 |
| bad_image | PASS | MONITOR_OR_IDENTITY_FAILURE | 0.203 |
| bad_nonce | PASS | MONITOR_OR_IDENTITY_FAILURE | 0.172 |
| bad_campaign | PASS | MONITOR_OR_IDENTITY_FAILURE | 0.187 |
| no_registration | PASS | REGISTRATION_TIMEOUT | 2.031 |
| worker_exit_tree | PASS | WORKER_UNEXPECTED_EXIT | 0.484 |
| invalid_handle | PASS | MONITOR_OR_IDENTITY_FAILURE | 0.203 |
| close_job | PASS | SIMULATED_MONITOR_LOSS_KILL_ON_CLOSE | 0.391 |
| driver_crash | PASS | WORKER_UNEXPECTED_EXIT | 0.547 |

`wrapper_exit` 的 root PID 与 worker PID 不同，root 已退出时 worker 继续受监控，正常结束收据才允许成功。`tree_timeout` 有子孙进程，时间超限后清空。`close_job` 关闭最后 Job 句柄，保留的进程句柄全部变为 signaled；关闭后无法查询已销毁 Job，因此该例 job_empty 字段为 null，不伪称查询成功。`driver_crash` 人工监控子进程调用 os._exit(17)，其内层 Job 工作进程在外层 watchdog 终止 Job **之前**已经退出，证明异常退出联动。

内存例分配并触碰32 MiB，模拟工作进程上限24 MiB，未占满系统内存；Job 另有256 MiB合计提交上限与16进程上限。该256 MiB只用于人工测试，不可套到模型训练。轮询20 ms，采样峰值不是连续时间的精确峰值。

最终 19 项主套件 + 8 项新保护检查 + 1 项 JSON/SQL 回归 + 3 项路径词法保护 = 31 PASS。最后三项用mock证明非所属目录/禁止年份/非法类型在mkdir等路径操作前拒绝，没有主动查询2025属性。16个主进程用例加1个异常监控退出，共17个不同进程场景。首轮19项自动PASS，但 unexpected_exit/worker_exit_tree 只得到笼统 MONITOR_OR_IDENTITY_FAILURE；人工审查判其退出分类 NOT_VERIFIED，修复后两例必须得到 WORKER_UNEXPECTED_EXIT。首轮原始收据 `tests/run_d07768eed92a.json` 未改写；修复套件为 `tests/run_6a6862278869.json`。

真正首次失败：保护审计 SQL返回tuple、保存JSON返回list，导致行比较误报。`tests/initial_protected_validation_failure.json` 保留 FAIL；文件SHA始终不变。修复只规范行表示，独立回归通过，未改变数据库。最终保护验证通过。

限制：当时用例收据没有同时记录执行源码SHA，明确 NOT_RECORDED_CONTEMPORANEOUSLY；当前交付 manifest 绑定最终代码，不能追溯声称首轮代码字节已被同时登记。异常内核API、系统死机、掉电、长时间驱动阻塞及真实训练树未验证。没有自动重启/退款路径；cleanup无法证明时失败、关闭Job、停止套件。
