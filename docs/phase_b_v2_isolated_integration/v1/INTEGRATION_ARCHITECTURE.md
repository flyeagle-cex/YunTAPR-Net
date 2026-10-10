# 隔离集成架构与边界

范围为 SYNTHETIC_ENGINEERING_ONLY。独立命名空间没有优化器、epoch训练循环、数据集加载器、checkpoint应用器或正式启动能力。模型构造会读取原公开科学合同和SP04静态资料，全部SHA已绑定。

|模块|职责|边界|
|---|---|---|
|pins.py|核验66个已有源码/协议/公开元数据SHA|外部mask仅声明，不打开|
|resources.py|构造前资源准入|不足停止，不改batch/精度/结构|
|synthetic.py|两场景、六槽及末槽、人工参考与mask|无路径和真实年份|
|initialization.py|真实fresh模型、同形复制和字节摘要|不读/存权重|
|adapter.py|原v2模型接到已有候选loss|固定B2、501到100网格|
|controls.py|候选规则、排列、终点、恢复拒绝|不能授权执行|
|safety.py|文件和操作进程守卫|禁止raw/checkpoint/2025、step和expm1|
|__init__.py|scope常量|包本身不构造模型|

调用顺序：资源准入→来源SHA→fresh B0/B1→人工张量→原backbone/SP04/双头→既有candidate_loss→合成backward→参数SHA复核。仅测试代码引用原b0_core_loss作E0对照；未调用正式forward_loss/update。

train()只设置模块模式，backward只计算梯度，没有optimizer实例或step。fresh构造及B0到B1的同形初值复制属于本轮授权范围，不读取历史状态。

scope字符串、frozen dataclass、JSON和SHA都不是认证机制。隔离依据内部人工fixture、调用图、进程守卫和无训练能力的BlockedRunner；这不是操作系统安全沙箱。工程PASS始终不能转成独立人类授权。
