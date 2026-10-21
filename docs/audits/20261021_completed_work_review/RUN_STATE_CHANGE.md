# RUN-01：v7资源保护退出的只读观察

**最终状态：此前核实的worker/Owner已退出。没有执行恢复。**

- 审查初期Get-Process可见worker PID29388及Owner PID48220，创建时间与v7身份JSON一致，CPU计数增加，心跳有更新。原本地HEAD为96a2a61。
- 退出前最后 `execution_status.json` 更新时间：2026-10-21 **19:13:47.842578（北京时间）**，仍写RUNNING，B0/E1 epoch2、已完成5172/5228批；仅epoch1已提交，run_updates10400。累计reserved/verified=187161/187160。
- 最后heartbeat：**19:15:09.915321**；不是退出时刻。没有由此推断epoch2完整提交或最后实际optimizer尝试数。
- **19:28:33**收尾观察：上述两个PID不存在；GUI终止收据记录`supervisor_exit_code=1`、`job_empty_and_handles_signaled=true`、`failure.type=MemoryError`、重试0/退款0。Owner traceback指向 `monitor → host_admission → AVAILABLE_COMMIT_LIMIT`，即系统available commit低于冻结10 GiB余量门槛。
- 原`termination.json`、`watchdog_failure.json`在定向读取时不存在；不生成或补造它们。原RUNNING JSON保留原样。退出确切时刻和总系统commit压力来源未建立。
- v7发布的667个源pin再次全部一致，原仓库HEAD未变；本轮没有修改训练代码/环境/权重/数据或发出stop/pause/restart。末次读取使用Windows只读、共享read/write/delete句柄，不持有训练状态写锁；没有查询SQLite或扫描270MB事件日志。

原文件SHA与只读观察内容见 [FINAL_LIVE_OBSERVATION.json](evidence/FINAL_LIVE_OBSERVATION.json)。身份nonce仅保留其hash，不复制到可提交报告。此前快照见 [runtime_snapshot.json](evidence/runtime_snapshot.json)。

**审查流程缺口与因果局限**：在建立副本前未核验共享系统commit余量，是本轮审查遗漏的安全检查。资源保护退出有直接证据，但不等于已经找出内存压力根因。本轮Git对象副本/checkout与标准库元数据解析仍使用共享CPU、内存、磁盘，没有逐进程连续峰值记录，不能证明它们完全没有叠加影响，也不能认定其中某项导致退出。完整帧/场景元数据解析发生在19:16之后；这不能消除此前副本建立等资源活动的潜在影响。报告不将“未发停止指令”扩写为“保证零干扰”。

处理：停止额外资源验证；仅收尾报告；不改任何原阈值、账本或失败记录，不自动重试、退款、恢复、启动seed2028/FinalFit。若拟继续，必须先由研究者决定资源审查与具体LAST/额度/恢复范围。这个运行事件不是本轮候选前序接口补丁造成训练代码变化的证据，因为补丁从未部署。
