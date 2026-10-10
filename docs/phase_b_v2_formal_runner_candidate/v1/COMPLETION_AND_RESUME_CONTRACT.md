# 完成边界与恢复契约

状态：READY → TRAINING → WAIT_VALIDATION → VALIDATING → 原子LAST提交 → READY。任何训练/验证/应用异常均使该实例poisoned，无自动重试、换seed或改参。

Loader固定训练batch=2、accumulation=1、drop_last=false；5个人工scene每epoch顺序为torch.Generator(seed+epoch_index)的确定性排列。Coverage拒绝重复、未知和缺失ID。训练与development角色的ID完全分开。验证配置batch=8，实际5场景为尾批5；StreamingValidation只用冻结FP64 gamma=2发生分子和未加权Pinball，global Core分母N_valid，Conditional Pinball分母N_rain，无雨时后者None。

每step：原S0全局update的LR先赋值 → BF16/FP64损失 → backward → 全参数梯度有限与clip=5 → 额度预留落盘 → AdamW.step → 额度完成落盘 → scheduler计数提交 → 参数与optimizer状态有限。无雨条件头梯度必须连接且为0；AdamW历史动量/衰减可能仍改变其参数，这不等于有雨损失。

本轮微型profile的科学协议身份仍B9/S0/V0，但实际人工终点为epoch2、每epoch3步；这不宣称运行了正式epoch。E1/E2只测试一个epoch；E0每模型连续两个epoch，再从epoch1 LAST恢复重放epoch2，总计9步。总预算30，新命名空间独立于上轮12次预算；台账不进入checkpoint、不允许恢复回滚。执行过程没有扩大额度。

LAST字段绑定：模型、AdamW所有moments、S0、Python/NumPy/CPU/CUDA RNG、seed/arm、协议/公开来源/当前源码/人工registry SHA、fresh祖先、训练/验证覆盖、逐步LR与clip、完成epoch及update、父LAST SHA。只有验证完整并原子提交后才推进completed_epoch。保存中断不产生可恢复receipt；SHA检查先于weights_only反序列化；全部身份和结构验证先于live状态应用。恢复只进入fresh引擎，并绑定具体synthetic LAST SHA；恢复实例保存到新的临时session，父SHA保留。应用异常停止，不保证部分应用自动回滚。

B9/V0终点采用冻结epoch9的逻辑判据，BEST不改变预算。纯逻辑测试验证10455个明确人工ID×9epoch的唯一覆盖、每epoch5228步、每run47052步，以及10501验证场景的1313 batch（末批5）；没有伪造真实样本合格目录。

正式执行祖先与研究者新的恢复事件，仅在FutureResumeBinding接口中定义，当前无验证器或执行能力。原历史BEST/LAST未打开、未修改、未追认。
