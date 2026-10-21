# 尚未应用的最小正式集成差异

当前旧版本仍是 `phase_b_v2_seed2027_b1_epoch7_recovery_v3`。本轮只添加人工候选，不修改其 source pins、release、任务注册、会话状态或 SQLite。

| 位置 | 新恢复版本中的必要变化 | 本轮状态 |
|---|---|---|
| `task_owner.fixed_spec/start_owner` | 系统任务 action 使用经 SHA 登记的 GUI bootstrap；固定目标、nonce、一次启动、Limited、无触发器/自动重试。不能仅加 `-WindowStyle Hidden`。 | 人工候选已验证，正式集成未应用 |
| GUI bootstrap | 开始前核验已发布来源；设置原有环境后启动固定正式 Owner，持有原生句柄与所属 Job 至 Owner 退出；无任意命令/模块参数。 | 仅固定人工 fixture 可执行 |
| `task_entry.main` | 最终原生 Owner 在导入科学模块前调用 `detach_current_console`，记录前后控制台身份，失败立即停止；日志不依赖控制台。 | 尚未应用 |
| `worker.main` | 在加载数据/模型及首个额度预留之前，对最终原生 Worker 执行同样核验。登记 nonce、原生 PID/创建时间/image identity。 | 尚未应用 |
| 资源/Job | 原 CPU/GPU/时间/存储上限不变；GUI 测试 Job 的 256 MiB 仅供人工测试，绝不能直接套用正式训练。保留已审计 FormalJob 限额和 kill-on-close。 | 正式资源测试未执行 |
| 祖先与额度 | 保留旧会话 ACTIVE、922 新增已用及全部失败材料；独立新账本继承累计 166305 次消耗，额外 922 次重放需真实研究者决定。 | 未批准、未创建 |
| 同字节 LAST/模型/数据/损失/评价 | 继续复用既有安全读取和原科学实现，不改 E0/E1/E2、seed、顺序、B9/S0/V0。 | 本轮无变更 |

待绑定的恢复源是既有 B1/E0 第七轮 LAST，SHA 见 README。本轮没有打开该权重；仅只读旧账本和已有身份收据。不允许把人工 fixture、测试 JSON 或这份文件当作新恢复授权。

实际 Codex 退出、Windows 用户注销/重启、驱动稳定性、长期训练稳定性均未由本轮人工测试证明。安全暂停仍须等待训练、完整开发验证和 LAST 提交后退出；不能将此次未完成事务伪装为 PAUSED。
