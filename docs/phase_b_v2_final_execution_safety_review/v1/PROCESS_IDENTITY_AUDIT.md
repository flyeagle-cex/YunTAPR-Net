# 进程身份审计

| 项目 | 状态 | 证据与范围 |
|---|---|---|
| venv包装器 / 实际Python区分 | PASS | root与worker PID不同；从工作原子收据绑定成员，root提前退出仍监控 |
| PID + 创建时间 + 原生image绑定 | PASS | GetProcessId/GetProcessTimes/QueryFullProcessImageNameW；JSON的创建时间/image必须与内核身份一致 |
| image真实来源 | PASS | 精确本解释器/venv home的image路径哈希白名单，不信任worker自报路径；公开仅path key |
| 错PID/外来PID/错误nonce/创建时间/image | PASS | 负面拒绝；外来父进程存活并继续测试，未调用PID-only终止 |
| 登记前退出/超时未登记 | PASS | EXIT_BEFORE_IDENTITY / REGISTRATION_TIMEOUT，均有明确失败收据 |
| worker异常退出及监控句柄无效 | PASS | WORKER_UNEXPECTED_EXIT / MONITOR_OR_IDENTITY_FAILURE，Job全树清理 |
| PID复用保护 | PASS（结构审查） | 长持有内核句柄，对象不随PID复用重新绑定；没有强制诱发Windows实际PID复用 |
| 终止后无遗留测试树 | PASS | 活跃成员查询为0、保留句柄signaled；Job关闭和driver_crash例另有句柄证明 |
| 正式Runner中的身份/Job集成 | NOT_VERIFIED | 当前仅新人工候选，未修改或接入IntegratedEngine/真实入口 |

nonce仅关联本次人工消息，不代表研究者签署。启动进程先被内核封闭，工作登记后才接受资源监控；登记失败也能终止Job中所有成员。GetProcessMemoryInfo读的是实际worker持有句柄，不是5 MB启动包装器。

旧 `phase_b_v2_real_train_smoke/launch.py:25 launch` 仍有缺陷：while以包装器poll结束、OpenProcess只凭PID、taskkill未验证全树清空；`run.py` 的原子JSON只有PID和campaign。这里是 **FAIL（不得复用于正式运行）**，不抹去历史失败，也不重跑封存smoke。最小未来变更是另批启动器版本接入受审Job后端、登记身份/完成收据与独立额度，不重启历史任务。

实现依据：[Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[创建时加入Job的属性列表方法](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812)、[AssignProcessToJobObject / 子进程继承及nested jobs](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)。适用本机Windows；其他系统和不支持Job属性的环境拒绝运行，不作降级。
