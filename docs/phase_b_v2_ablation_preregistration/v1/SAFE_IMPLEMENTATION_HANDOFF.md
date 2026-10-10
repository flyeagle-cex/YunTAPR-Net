# 安全工程交接与执行门槛

本轮只实现审查工具，无训练launcher、runner、模型实例、新loss实现或正式入口变更。检查器始终can_launch_formal_training=false；valid proposal与execution readiness是两个概念，缺任何批准都BLOCKED。

## 必须遵守的实施次序

1. 研究者阅读真实Focal、Pinball、total_loss及本数学映射，亲自独立写最小PyTorch实现，解释sum/mean/共同分母、float32标签、FP64与空雨约定。本轮没有替研究者编写答案代码。
2. 研究者提供其实现，Codex做数学/shape/dtype/mask/异常审查，绑定真实文件与SHA，指出差异；无集成或训练。
3. 研究者明确允许工程集成与完整测试之后，在新的隔离版本内集成lambda与seed接口，保留E0兼容证明。单独获得对应forward/backward/optimizer fixture范围许可；这次批准不自动授权真实数据或正式运行。
4. 完成正式协议独立批准、数据/资源权限、身份审计和后续工程preflight授权。不要调用旧Contract.load/initialize来做本轮“检查”，它们会加载真实manifest/模型或外部文件。
5. 再取得覆盖seed2026完整6run的阶段1执行批准。批准scope/代码SHA/矩阵/预算/roots都一致才执行；阶段2另批，不因阶段1PASS启动。

## 后续需要工程化的差异清单（本轮非执行提案）

|入口/模块|真实现状|未来变更规格|
|---|---|---|
|losses/focal.py|已有显式gamma，训练调用仍hardcode2；参数finite/bool校验不全|研究者写/审最小接口；参数从批准臂传入，不改E0语义|
|losses/pinball.py|32tau mean/sum，FP64由qlog决定|保留数学；研究者练习不引入新tau或分母|
|losses/total_loss.py|无lambda接口，返回occ+qr|研究者实现后仅lambda乘qr；保留unweighted报告与空雨graph零|
|formal_phase_a_v2.py|gamma2硬编码、旧训练授权、BEST/early-stop及旧roots|不得复用作本矩阵launcher；未来新隔离runner审查|
|phase_a_protocol.py|seed、startup env及epoch_permutation均固定2026|未来显式seed参数，同seed跨臂一致；LR前缀保持原值|
|phase_a_validation_v2.py|固定gamma2共同core、log域无物理转换|可复用数学；不能把训练gamma/lambda带入共同指标|
|checkpoint_v2.py|完成train+validation边界，selection含BEST/earlystop、旧schema/roots|新run namespace、固定endpoint与独立恢复gate；不覆盖旧payload|
|科学observer|既有32coverage/分箱/上尾aggregate可引用，但有硬编码scope/模型身份|批准后适配18臂来源；新增Type7/span摘要单独审查，不能直接执行旧observer|

本轮工具仅校验封闭schema、18组合、整数预算和静态来源SHA，使用标准库；不会import torch/yuntapr，不反序列化checkpoint、不调用Contract.load。schema仅支持本包列明的简单JSON Schema关键字，遇到未支持关键字也拒绝；不是通用解释器或授权签发器。

## Fail-closed与身份

缺schema/字段、未知状态、bool冒充int、arm参数不符、缺seed、重复run、source SHA不符、路径逃逸、年份2025、任何自报APPROVED/AUTHORIZED标志、缺approval或实现/审查/集成许可，一律不能启动。完整合法提案仍BLOCKED，因为审查工具不具备启动功能。工具输出审查理由与candidate_valid，不生成授权文件；人工批准真实性将来由独立验证流程处理，本JSON永远不是它。

静态来源核验只读取白名单仓库源码、配置、已发表metadata与manifest字节SHA，不解析真实样本记录、不触碰raw、weights或外部mask。外部mask只登记协议声明SHA，NOT_REOPENED；不能把静态PASS称为真实数据preflight完成。旧源码AST审查也是静态，不import其模块。

## 恢复与异常

任何数据/数值/身份/资源异常先安全停止，保留异常栈、run/seed/arm/update、访问计数、已完成checkpoint和未完成前缀。本轮不实现会写实际训练状态的脚本。拟议恢复流程：验证不可变LAST字节SHA及逻辑model/optimizer/RNG/scheduler SHA、完成train+validation marker、原执行批准祖先、同code/protocol/data/init/seed、下一epoch和剩余预算；研究者独立明确批准此LAST及额外重放资源后才应用状态。

原始文件锁/事务失败不先删checkpoint；半epoch不变成合法LAST；重放计入尝试更新并披露，不能声称没有新增计算。fresh重试、改batch/LR/精度、换seed或跳样本须新科学/执行决定，automatic_retry/resume=false。历史B1 LAST14治理缺口继续NOT_GRANTED；BEST9早于恢复只是技术chronology，不代替独立处置。

未来接续先核对Git/进程和本版manifest，再收集研究者真实实现/决定；在独立新版本追加，不覆盖本v1及任何历史证据。2025解封、FinalFit、独立物理资料获取、新架构都不在本交接范围。当前所有formal training/forward/backward/optimizer/data preflight计数为0。
