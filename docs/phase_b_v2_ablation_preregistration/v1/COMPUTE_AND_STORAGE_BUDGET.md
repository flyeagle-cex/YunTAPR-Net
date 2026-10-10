# 更新、验证、输入与存储预算

纯数学估计，NOT_EXECUTED；GPU型号、可用显存、并发、耗时、功率和费用均NOT_YET_ESTABLISHED，未创建/测量训练作业。本轮没有为了估时运行smoke forward。机器预算在run_budget.csv及budget_summary.json。

## 固定更新及验证

训练N=10455、physical batch2、accumulation1、drop_last=false：每epoch ceil(N/2)=5228 updates，最后batch1；9epoch=47052，场景呈现94095。验证N=10501、batch8：每次1313 batches，最后batch5；9次共11817，验证场景呈现94509。一个batch的forward不是一次独立天气过程。

|范围|runs|训练updates|训练场景呈现|验证batch（每epoch）|epoch9终点batch下界|
|---|---|---|---|---|---|
|单模型/条件/seed|1|47052|94095|11817|1313|
|一个seed完整三条件两模型|6|282312|564570|70902|7878|
|单条件跨两模型三seed|6|282312|564570|70902|7878|
|阶段2两seed|12|564624|1129140|141804|15756|
|全矩阵|18|846936|1693710|212706|23634|

23634仅终点评价算术数，当前提案保留逐epoch验证；不能以低数申请资源后隐含执行9倍验证。epoch9完整科学observer应复用最后一次forward，若以后实现产生额外模型推理必须独立登记批准。B9不会走到50epoch的min LR；warmup第一步为1e-4/5228，不因“min1e-6”而clamp线性warmup。

## 输入数据规模的口径

每场景原生输入为float32的[1或6,501,501]：B0=1,004,004 bytes，B1=6,024,024 bytes；原生bool mask另计每元素1 byte。训练batch2原生输入分别约1.92/11.49 MiB，未含mask、目标、特征、autograd激活、缓存或CUDA工作区。单场景100×100 float32标签40,000 bytes，两张目标bool mask合计20,000 bytes；不要把3430评价格点当原始卷积输入大小。

run_budget逐行列出9epoch输入tensor呈现字节、验证呈现字节；这只是内存表示的逻辑呈现量，不是唯一卫星文件大小或实际磁盘I/O。六帧有跨场景重叠，staging又可能重复复制/校验整文件，压缩NetCDF的I/O和唯一文件规模本轮不读取、不估伪数。模型主体共享，因此输入6倍不等于GPU耗时6倍。

## 检查点与诊断存储

冻结参数P_B0=4,329,410，P_B1=4,331,810。FP32参数及AdamW两个FP32moment仅tensor payload=12P，约49.55/49.57 MiB；fresh模型参数=4P，约16.52 MiB。这里未含buffer、optimizer step标量、RNG、scheduler、pickle/zip及日志，是下界而非实测checkpoint字节。未来须用获批代码量测实物，正式disk gate不能只用此下界。

拟保留每run9个不可变完成epoch checkpoint：全矩阵162个，12P合计在budget_summary中给出；初态每seed两模型共6份4P锚点本地只读，跨E0/E1/E2使用同一身份而不跨臂迁移训练后状态。LAST/endpoint可引用不可变文件，不再复制BEST二进制；是否去重/hardlink需审查文件系统和保存事务。本轮没有创建这些文件。

假设单run串行，checkpoint事务需额外临时写入及验证空间，旧完整文件不得先删；至少记录2个实测checkpoint事务余量。每worker staging上限734,003,200 bytes，两worker合计1,468,006,400；沿旧loader不改变worker数，以实际磁盘/权限核实。日志总量、聚合统计、文件数量和source access日志另列未定值，资源管理员批准前不得声称空间足够。

不要保存所有验证dense qlog：10501×32×100×100×8=26,882,560,000 bytes/run，仅18个终点就483,886,080,000 bytes，不含p/label或副本。优先保留分子/分母、score counts、32coverage、预定义异常计数与审计摘要。新增Type7分布需要获批私有临时排序：单变量36,018,430×8=288,147,440 bytes；并行6高tau加宽度会放大，建议串行变量与有界外排序，工作区系数/算法/实际峰值仍待量测，不能假称已有可用精确实现。临时预测不公开上传。

## 正式执行前的资源量测方案

只有研究者代码审查和新的执行范围批准后，才能记录GPU型号/数量/UUID、driver/CUDA/cuDNN/PyTorch、CPU/RAM、磁盘free bytes、BF16支持、TF32/确定性、worker/缓存方案、协议/代码/SHA。提议在阶段1获批运行内记录冷启动、训练与验证各阶段wall time、每epoch及完整run耗时、峰值显存、staging/日志/checkpoint字节，不额外增加优化更新或改变样本顺序。外推其余runs须给时间范围/负载条件与不确定性，不宣称无偏GPU性能比较。

若需单独smoke、真实数据preflight、初始化证明、loss梯度测试或校准量测，必须在之后另有明确批准的工程范围；本轮这些均未执行。预计总耗时字段留NOT_YET_ESTABLISHED，不用历史最佳耗时伪装为本矩阵测量。

## 失败与恢复的拟定预算规则

非有限值、M1缺失、SHA/样本顺序/分母漂移、OOM、磁盘不足、文件锁、环境变化、checkpoint事务不完整即停止，不skip、降精度、减batch或补长epoch。OOM通过更小batch“继续”会改变控制变量，须新版本批准。

候选max_retries=0（自动重试为零）；人工重试/恢复数量及额外资源尚未批准。已完成更新保留，未完成epoch的尝试更新与重放分别审计；原47052是保留轨迹预算，重放会增加总尝试数，必须审批额外资源上限。恢复保持同一seed/arm/code/LR及下一完整epoch，不根据坏指标fresh重跑挑好seed。阶段1失败只提供失败与资源证据，不给阶段2自动授权。
