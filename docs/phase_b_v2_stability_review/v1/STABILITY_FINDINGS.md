# 稳定性排查：证据与限制

## 已确认的时间线（北京时间 UTC+08）

|时间|真实证据|能支持的判断|
|---|---|---|
|2026-10-14 08:26:59.224|System / nvlddmkm / 153|此前也出现同类GPU驱动事件，根因仍未确定|
|2026-10-17 20:51:02.650|STEP_RETURNED / update741|本次重启741次全部核验完成|
|2026-10-17 20:51:02.732–.754|末次心跳与下一批BATCH_DECODED|第742次优化器调用尚无持久化预留，不增加一次在途额度|
|2026-10-17 20:51:02.993|System / nvlddmkm / 153|与日志停止同秒，构成GPU相关故障的时间关联证据|
|2026-10-17 22:57:42 / 22:57:59|User32/1074、Kernel-General/13|之后发生关机；不能把当前无进程全部归因于20:51的GPU事件|
|2026-10-18 07:24:30–31|OS LastBoot、Kernel-General/12|机器已重新启动，原会话不能视为仍运行|

旧Supervisor stdout/stderr均为空，没有原生退出码、异常收据或完整LAST。GPU事件153的确切原因、监督进程从何时起未能收尾、关机前是否仍有挂起进程均为 **NOT_VERIFIED**。本次没有打开任何dmp、原始气象数据或模型权重。

应用日志里的部分LiveKernelEvent为15e，附带NDIS目录及20260314旧转储日期。它们在开机后再次报告，不能当作本次GPU 141/TDR诊断证据；未读取这些转储。Windows的TDR机制会尝试恢复图形栈，但事件153本身不足以确定具体TDR类型或硬件故障。[Microsoft TDR说明](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/timeout-detection-and-recovery)

## 资源证据

- 驱动现场为573.24（Windows版本32.0.15.7324，驱动元数据日期2025-05-12）；未更新、回滚或重新安装。
- 最后心跳：CUDA peak allocated约2.67GiB、reserved约3.19GiB，低于原6GiB reserved门槛。该采样不能证明最终异常瞬间没有其他资源或驱动问题。
- 最后进程working set约2.60GiB、private commit约7.20GiB；两者不同，不能用工作集替代提交量。
- 前次AVAILABLE_COMMIT_LIMIT证明调用方可提交量触发门槛；失败前没有保存完整系统提交量和所有外部进程的连续序列，不能确定是哪个软件或机制导致压力。
- 当前分页文件由系统自动管理、已分配15360MiB；当前低使用量和开机后的充足内存不能证明故障时状态。当前温度约47°C为闲置时快照，历史温度、功率、热降频未记录。

原字段available_page来自MEMORYSTATUSEX.ullAvailPageFile，表示**当前进程**还能提交的字节，可能小于全系统可提交量。新memory.sample同时记录该值和GetPerformanceInfo推导的系统CommitLimit−CommitTotal，再乘PageSize换算字节。原正式资源门槛和执行代码未改。[Microsoft调用方字段定义](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex)、[系统提交量及页单位](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-performance_information)

## 已修复与未修复

已修复独立审查入口的失效会话识别、只读现场核验及追加事后收据。真正的GPU故障修复、真实CUDA异常注入、长程稳定性、断电持久性、驱动变更后的复现性均 **NOT_VERIFIED**。本轮没有声称重装驱动、调高TDR时间或增加分页文件即可解决问题；这些系统操作均未执行。

现在没有可恢复的LAST。任何将来重启都需要先决定稳定性处置和新的明确运行范围；本轮不新增执行权限或额度，不据随机初态失败记录产生科研结论。
