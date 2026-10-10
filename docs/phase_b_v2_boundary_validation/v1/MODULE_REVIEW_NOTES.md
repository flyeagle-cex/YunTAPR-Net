# 新增模块审查笔记

本轮仅3个候选Python文件与3个新测试文件；不重写旧损失或旧适配器。完整旧损失学习见 [上一轮学习材料](../../phase_b_v2_ablation_implementation/v1/RESEARCHER_CODE_STUDY_GUIDE.md)。

## boundary.py

verify_inherited_identity只核对226个既有公开文件字节；SHA说明身份，不能证明独立科学批准。BoundaryBatch是frozen dataclass，字段名固定但Tensor内容仍可变，所以每次validate。x为FP32[B,1或6,501,501]；参考FP32[B,1,100,100]；三个bool mask独立且同设备。只接受B=1/8/5和相应phase，data_years必须为空。

make_boundary_pair用arange/reshape/sin生成有限值，expand后clone使人工mask可独立检查。nextafter生成float32(0.1)上下相邻值；这是阈值教学，不是读真实降雨。B0使用最后一帧clone，明确避免输入别名。to用dataclasses.replace返回转设备副本，不能把frozen解释为深度不可变。

losses_from_output校验BF16发生与FP64 qlog、sigmoid一致、shape/有限性；沿用get_config/candidate_loss，返回三臂而非搜索参数。forward_boundary要求原模型精确类型和train/eval状态；with inference_mode(mode=not training)控制计算图；with autocast只控制冻结BF16路径，内部raw33与qlog升精度仍由原头负责。函数不做backward或step。

evaluation_components使用原LogDomainValidation重新算FP64发生分子；不是detach训练FP32分子后冒称FP64。aggregate_evaluation先fsum未加权分子与分母，再求比值；不能平均batch均值或把空雨CPB填0。lambda与gamma变化只影响训练报告。

## gradients.py与包入口

checked_gradients逐一检查parameter.grad；backward累加梯度，所以测试每臂前zero_grad(set_to_none=True)。这只是清梯度，不更新参数。train1同一输出图供三臂使用，前两次retain_graph=True，最后释放；这样只改变loss，不能声称模拟三个正式训练run。空雨graph_zero沿计算图传播0，允许梯度全0，但不允许grad缺失或NaN。包入口仅scope常量，没有runner。

## 测试与工具

test_cpu_boundaries用完整目标网格核对两个分母、float32阈值、掩膜、异常与不等批次汇总；不是CPU完整模型训练。test_cuda_boundaries每例先资源准入、再fresh原模型，再forward，train1才backward；原始权重、全参数梯度和buffer身份只存SHA/范数，不保存模型。conftest复用旧step/load/save/expm1保护；Python守卫可被进程外代码改写，不能成为正式授权认证。

run_checks调用新测试子进程，保存原始私有log及脱敏公开XML、执行时源码SHA，不自动重试。static_review只AST/文件哈希/已发表记录，不import模型。build_review/export/close只处理文档与身份；doc自身成功不构成批准。

研究者小练习：解释为何float32(0.1)先double再比较Python0.1可能错标有雨；手算batch1的3430分母；解释空雨q头zero与缺失梯度的区别；用8+5批次证明先累加分子、再相除；找出Phase-A checkpoint的50epoch/BEST字段为何不能直接替代B9/V0。
