# 正式集成差异与缺口

本轮只新增独立候选源码/测试/文档，没有应用正式路径补丁。后续应另建v2消融runner，旧v1 FinalFit不能冒充本入口。

|正式源码参考|当前隔离对应|获准集成还需实现|
|---|---|---|
|Contract.load|公开SHA检查|真实样本、年份/路径防火墙、scaler/mask/data身份|
|paired_initialization|三seed真实fresh摘要|正式run初态与源码/环境/RNG绑定、保留策略|
|forward_loss|合成适配器+既有candidate_loss|正式Batch接口与资格；不能用人工mask|
|update|仅backward诊断|另审optimizer、clip、scheduler、事务计数|
|epoch loop|纯endpoint_boundary|9epoch及逐epoch验证，无BEST替代终点|
|checkpoint_v2|声明身份负面检查|独立schema、完整epoch事务、immutable LAST和孤儿文件处置|
|authorization|永远阻断的BlockedRunner|独立批准验真及具体阶段绑定|

SyntheticBatch固定两个人工ID、人工mask和归一化数值，不能直接成为正式数据入口。真实尾batch1、验证batch8/尾batch5尚未验证；本轮未通过改batch制造完整矩阵通过。

另获授权的真实preflight：2023/2024读取、冻结真实mask/SP04配准、scaler应用、完整ID与时间因果性、staging及异常停止。2025继续封存。checkpoint耐久性、原子写入、中断故障注入、独立LAST恢复及长时资源需另审；非有限、缺监督、丢样本、源码/SHA漂移必须停止，不自动跳batch或历史恢复。

已有：闭合loss接口、双模型合成路径、真实fresh跨臂身份、数学预算和边界、负面证据。未有：正式runner、真实preflight、optimizer事务、checkpoint耐久性、长时稳定性、批准验真。缺口需要独立数据/资源和执行授权，不能填入合成结果。

科学待决：H-O/H-Q及E0/E1/E2最终接受、效应界限/副作用容忍、多重比较、2024开发验证解释范围、Phase-A接受及B1历史恢复独立处置。均为RESEARCHER_DECISION_REQUIRED。
