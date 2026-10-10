# 测试范围与后续损失测试规格

本轮实际可执行的只有静态检查和纯合成元数据/整数预算测试，不import torch，不调用任何真实损失、模型、backward、optimizer或raw reader。tests/README与XML/JSON记录真实数量及失败，不把历史测试算入本轮。

## 本轮审查工具测试

完整合法proposed结构应candidate_valid=true但can_launch=false；缺审批理由仍列出。测试未知/自报批准状态、phaseB true、2025年份、错误阈值/epsilon/tau、整数bool、batch/accumulation、LR/epoch/factor混入、source身份缺失/变动、未知schema关键字、路径绝对/..逃逸、重复/缺臂或seed及错预算。用内存合成metadata，不写伪人类批准记录，不读取真实样本内容。

整数预算覆盖单run/单seed/全18，train尾1/validation尾5，B0/B1形状字节、参数moment payload下界、9validation循环与1endpoint下界区别。对数学算例表只检查文件存在和声明“手算期望”；不通过另写一个新loss算法来替研究者做实现。

静态审查：旧关键源码AST parse和明确函数/行号定位、旧配置及历史交付SHA、schema/机器矩阵一致、Markdown链接、LaTeX内容绑定、PDF编译诊断/文本/逐页图像、Git允许清单及 staged bytes。外部mask、GPU、raw/checkpoint和正式执行入口不检查/实例化；限定README列出的源码/metadata文件。

## 研究者实现后、得到新许可才可执行的测试

|类|计划用例|批准前状态|
|---|---|---|
|Focal数值|数学表F1–F4、gamma0=.5BCE、正负极端有限logit、不sigmoid两次|NOT_EXECUTED|
|Pinball数值|P1–P4、32tau mean、e符号/等值、FP64、不expm1|NOT_EXECUTED|
|权重组合|T1/T2、lambda仅一次、N_valid/N_rain分离、E0兼容|NOT_EXECUTED|
|边界与拒绝|float32 .1及nextafter、空valid/空雨、shape/dtype/device/mask、NaN/inf/负目标|NOT_EXECUTED|
|autograd|手算gamma0及pinball分段梯度、有限差分离kink、空雨graph连接|需明确梯度测试许可|
|集成|三臂输出结构不变、同seed初态/排列一致、共同core固定gamma2、epoch9终点|需研究者集成与synthetic model许可|
|恢复|同LAST/epoch/代码/预算批准验证、原始状态不先应用、事务与失败日志|需专门恢复fixture许可；正式恢复另批|
|实际preflight|权限、2023/24读取/源SHA/QC、真实fresh及GPU资源测量|需数据与执行准备授权|

未来回归比较不仅“新代码与自己输出相同”：用手算独立oracle、E0冻结数学、梯度符号及边界拒绝作证据。不要使用2025或新结果调接口参数。测试失败保留首轮日志，修复后append新attempt，注明当前通过与历史失败。测试PASS只能说明检查范围内实现行为，不替代人类科学决定或执行批准。
