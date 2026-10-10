# 闭合消融配置与运行身份合同

config.py定义私有_PARAMETERS字典：E0=(.5,2,1)，E1=(.5,0,1)，E2=(.5,2,2)。get_config(experiment_id)只接收精确字符串E0/E1/E2；大小写错误、未知ID、E3/E4/FinalFit、None或dict全部拒绝。它不读取外部配置文件、不选择最优条件。

AblationConfig是@dataclass(frozen=True)：自动生成构造、比较等方法，字段是experiment_id、alpha、gamma、lambda_q。__post_init__在构造后检查类型、finite和ID对应精确数值，禁止E0名下悄悄使用gamma0。frozen禁止普通属性赋值；候选调用前仍重验，不能把Python级防篡改当人类授权。

finite_number(name,value)返回Python float但不盲目把字符串或bool转数；判断type不是isinstance用于排除bool。无默认alpha/gamma，裸loss显式传参；科学臂只使用get_config返回值。科学状态PROPOSED_FOR_RESEARCHER_APPROVAL是常量说明，不存在升级APPROVED的setter。

RunSpec(experiment_id,model,seed)要求模型精确B0_MATCHED_V2/B1_V2，seed为真正int且属于2026/2027/2028。run_id property动态构造条件、模型与seed身份；stage property将2026归阶段1、另两seed归阶段2，只是划分，不是执行批准。proposed_runs依seed→arm→model顺序生成tuple18项，tuple不可追加；同一seed内条件必须共享样本、初始化和排列。

workload()只做整数ceil预算：10455/physicalbatch2→5228更新每epoch，尾batch1；9epoch47052；全18→846936。10501/valbatch8→1313，尾batch5；每epoch验证，共212706。阶段1六run282312，阶段2十二run564624。没有运行这些更新。新预算测试与旧budget_summary核对，不重跑旧科学验收。

learning_rate_prefix(update)只接收1..47052的真正int；W5228、U261400，不把9epoch压缩成cosine全周期。前W步线性warmup低于1e-6可以合法；minLR只作用于后续cosine段。测试逐一核对全部47052位置与原lr_for_update(steps_per_epoch=5228)的相同返回值，原函数通过AST提取纯数学节点调用，未加载其数据/授权模块。

候选配置仍依赖D1/Q1/N0/I3/B9/S0/V0的独立正式批准。数据产品、M1配对、原float32>.1标签、32tau、epsilon1e-4、FP64守卫、batch2/accum1/no_drop、AdamW与clip、逐epoch验证及epoch9终点不能因为代码PASS而改变。未来runner须验证机读提案、代码SHA及真实授权，而不是只检查实验ID存在。
