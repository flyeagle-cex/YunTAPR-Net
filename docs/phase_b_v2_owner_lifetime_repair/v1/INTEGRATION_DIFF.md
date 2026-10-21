# 后续正式恢复版本的最小接入差异（未应用）

本轮仅交付人工进程验证通过的启动机制。`task_bridge.start_artificial_owner()` 固定调用人工 fixture，不能接受正式 Supervisor、真实数据或任意命令。不要把它改成“传入布尔值即可训练”的通用入口。

| 位置 / 接口 | 现有行为及问题 | 后续最小修改 | 本轮状态 |
|---|---|---|---|
| `training/phase_b_v2_seed2027_b1_epoch7_recovery_v1/control.py::start` | 通过 Popen + CREATE_NO_WINDOW 启动 Supervisor，继承宿主 Job 寿命 | 在新的独立恢复命名空间中，以真实新指令、源码/依赖、数据身份、额度和会话 nonce 绑定固定任务；由 OS 按需启动固定 Supervisor | 未修改旧入口 |
| 新版本任务启动桥 | 现有人工桥只接受 fixture | 固定项目/解释器/模块/发布身份，不接受任意程序；当前用户 Limited、无触发器、RestartCount=0、IgnoreNew；一次会话只发起一次任务启动，失败留证、不重试 | 正式桥未实现 |
| 新版本 Supervisor 身份登记 | 包装 Python PID 不等于原生 Worker PID | 持久化任务实例、原生 PID、创建时间、executable 摘要和一次性 nonce；核对其不属于启动客户端的 Job；系统调度器自己的 Job 不应被误判为错误 | 人工 venv 测试通过 |
| Supervisor → Worker Job | Worker 必须受资源 watchdog 管理 | 继续使用已有 KILL_ON_JOB_CLOSE 和原资源上限；不得把 Worker 脱离其监督 Job | 人工正常与异常清理通过 |
| `quota.py` / LAST 祖先 | 失效 ACTIVE 不允许再次启动，旧消费不得退款 | 新独立恢复账本绑定旧账本 SHA、累计消耗、指定 LAST SHA 和真实新授权；保留旧账本与全部失败证据 | 未建立新正式账本 |
| `control.py::status` | 历史状态可仅报告 SQLite ACTIVE | 在新版本复用只读 native 身份判定；确实缺失则报告 STOPPED_UNCLEAN；UNKNOWN 保留 NOT_VERIFIED；绝不自动把 ACTIVE 改成 PAUSED | 独立审计器通过 4 项测试 |
| 安全暂停与恢复 | 完整 epoch、开发验证、LAST 事务是安全边界 | 保持原逻辑；系统任务只能延长 Owner 寿命，不能使 epoch 中断变成可无损继续 | 正式任务路径未验证 |

注册任务不能自行批准科学协议或恢复。实际恢复仍需绑定研究者的新决定：B1/E0 第 7 轮 LAST `bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a`、548 次补充额度、累计上限 364,047；其余科学配置和资源上限不变，B0/E0 完成结果保留，不包含 seed2028。

新正式版本在首次 optimizer.step 前仍须完成原有的数据同字节 SHA、LAST 全状态验证、数据盘身份、资源和源码固定检查。本轮没有执行这些真实读取或更新，不能把人工任务测试替代它们。

当前三项系统任务测试证明的是人工 Owner 不属于模拟 Codex Job，并且模拟客户端关闭后仍存活。没有再次实际关闭 Codex，也没有运行正式任务来宣称长程稳定性、断电持久性或 GPU 驱动稳定性通过。
