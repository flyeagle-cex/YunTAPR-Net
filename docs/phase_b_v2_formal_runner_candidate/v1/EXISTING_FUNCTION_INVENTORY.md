# 复用清单与新增结构

|功能|已存在并复用|本轮新增|
|---|---|---|
|E0/E1/E2与损失|phase_b_v2_ablations/config、focal、pinball、total|无数学改写；adapter接收批次2/1及验证5|
|真实v2双模型、SP04、32tau|models/quantile_v2；spatial投影|无模型/投影改写|
|配对fresh|integration/initialization:fresh_paired_models|protocol临时替换来源校验依赖，仅避免读取被本轮禁止的scaler；原seed/参数拷贝算法原样执行|
|AdamW、clip=5、S0|runner_candidate/optimizer:new_adamw、clip_and_check、PrefixSchedule.prepare/commit|EpochSchedule只将合成恢复计数上限由2扩为6，不改LR数学|
|FP64共同评价|training/phase_a_validation_v2:LogDomainValidation|StreamingValidation加入完整场景覆盖，先求全局分子/分母再相除|
|原子文件事务|runner_candidate/checkpoint:SyntheticStore.save/read|EpochStore只替换临时根和I/O上下文；新增完整epoch LAST schema校验|
|RNG与状态摘要|runner_candidate/rng；phase_a_protocol:state_digest|无重写；绑定LAST恢复|
|旧短程Runner|仅支持内部batch2、2次更新|新EpochEngine支持Loader、batch2/2/1、完整验证、LAST、跨epoch恢复续跑|

新模块：protocol（固定协议与身份）、data（Scene/Registry/Loader/Coverage）、adapter（模型/损失接口）、metrics（流式共同评价）、engine（训练和验证事务）、checkpoint（epoch完成身份）、safety（独立30次额度与I/O守卫）、authorization（未来接口及当前无条件阻断）、__init__（人工用途声明）。

真实scaler的SHA只继承公开inventory引用，未打开其文件。402个公开文件本轮实际核验SHA；1个scaler只保留引用。真实云南mask未访问。Git只新增本轮文件，冻结源和历史证据未改。
