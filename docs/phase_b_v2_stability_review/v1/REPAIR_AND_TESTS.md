# 代码修复与人工验证

|文件/函数|用途与保护|
|---|---|
|classification.py / scope, identity|在任何PID/Job查询前校验campaign、session、nonce、创建时间、可执行文件身份和精确Job名|
|native.py / process, job|仅QUERY/SYNCHRONIZE原生句柄，不调用终止/启动API；PID不等于身份；访问拒绝和查询异常返回UNKNOWN|
|classification.py / classify|活进程优先于旧心跳；仅在两个登记进程均不存在/已退出/身份不符且Job缺失或空时报告停止；缺少LAST不能变成PAUSED|
|review.py / inspect|只允许登记的seed2027审计文件；目录/只读句柄绑定、同次SHA与只读SQLite快照；不加载模型或权重|
|receipts.py / save, verify|新目录创建不可覆盖的事后观察；fsync、原子创建链接和SHA；不伪造原termination.json；断电目录持久性不作保证|
|memory.py / sample|分开记录调用方及系统提交量，不改资源阈值或系统设置|
|fixture.py / main|仅人工子进程，使用既有Job实现；owner os._exit绕过finally，验证关闭所有拥有句柄后的进程树清理|
|Inspect-Training.ps1|新的只读操作入口，可选追加审计；没有start/resume/额度重置选项|

## 测试结果

最终17项通过、0失败、0错误。覆盖旧心跳活进程、系统重启后的无进程、孤立Job、查询异常、模拟PID身份不符、无LAST/有声明但未验证的LAST、时钟偏差、nonce/Job身份拒绝、无登记信息、追加/损坏/部分收据和两个人工进程用例。人工用例每例上限15秒、主动内存分配0，无PyTorch、GPU或优化器。

首次16项中1项失败：测试在Job成员列表变空后立即断言进程已消失；原生进程可能尚未退出。首次原始结果、完整堆栈和测试目录保留。修复为等待Job空且全部保留句柄已signaled；新回归用例证明Job空但进程存活时不能判定收尾成功。未放宽断言或超时。已有Windows Job测试没有重跑。[Microsoft Job生命周期说明](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

真实核验结果为STOPPED_UNCLEAN_NO_LAST，原SQLite仍为ACTIVE，计数仍为旧386/核验385＋本次741/核验741＝累计1127/核验1126。历史1次未核验未退款、未晋升为成功。新事后观察证明检查时进程树为空，不证明20:51或22:57曾执行成功收尾；resume_allowed始终为false。

这是一套已运行的独立修复入口；没有把新工具接入旧冻结Runner、没有修改原ACTIVE、没有改原启动拒绝逻辑。将来若要让正式Operator自动使用此视图，需要在新执行版本中明确接入并重新固定源码。GPU内核挂起、整个系统关闭时程序无法保证自己写完finally，人工进程通过不能替代这些真实故障的长程验证。
