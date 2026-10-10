# 尚待研究者独立决定的字段

PROPOSED_FOR_RESEARCHER_APPROVAL。A路线及给定配方已收敛为提案，但本消息没有批准实验，所有下列事项仍RESEARCHER_DECISION_REQUIRED。

|ID|字段/依赖|当前值|
|---|---|---|
|A01|Phase-A接受范围与B1恢复偏差独立处置|UNDECIDED / NOT_GRANTED|
|A02|H-O/H-Q、四个主比较及18臂参数批准|建议矩阵已写入；NOT_APPROVED|
|A03|I3种子、fresh匹配及seed+epoch排列推广|提案2026/2027/2028；实物SHA尚不存在|
|A04|V0固定9与逐epoch验证/checkpoint；不按性能earlystop|明确提案；NOT_APPROVED|
|A05|最小Brier改善、abs q32误差改善|NOT_YET_ESTABLISHED；比例/无量纲|
|A06|CPB/强雨层/Brier/AUC/AP及尾分布副作用容忍|NOT_YET_ESTABLISHED；需单位/联合判据|
|A07|M-A/M-B/M-C、有效块/replicate门槛、p构造/同时区间|NOT_YET_ESTABLISHED|
|A08|事件有效样本量与功效|NOT_YET_ESTABLISHED，不捏造保证|
|A09|q27–q32/span/宽度Type7诊断定义及临时排序方案|候选定义已列；需批准并工程化|
|A10|研究者最小PyTorch实现、数学审查、集成与测试许可|尚未发生，相关身份字段null|
|A11|GPU/版本/roots/数据权限、时长与空间测量/上限|NOT_YET_ESTABLISHED，无实际preflight|
|A12|阶段1 seed2026六run与阶段2其余十二run执行范围|均NOT_AUTHORIZED，另行独立批准|
|A13|异常停止、重试/恢复及具体LAST批准/重放资源|auto retry0；任何人工恢复未批准|
|A14|公开解释、失败/偏离披露和论文使用|仅2024开发探索提案，真实新Results尚无|

先完成A01/A02等科学审阅，研究者亲自实现A10核心代码，再审集成、工程准备与资源；最后另批A12具体执行。可要求改版/拒绝部分选项，不能用本清单“自动补空”。每个独立人类决定应在新的版本/记录中保留原文、身份、时间和批准scope，研究者自身发生的事件才可核验。

科学资料、计算资源、真实代码均是不同依赖。效果数值与guardrail无合理依据时保持未定，报告提案完整但approval incomplete；不因为工期或Git推送成功而设置任意值。只完成一个seed时不获得完整三seed证据。任何扩展损失、温度缩放、FinalFit、2025、GFS/DEM模块需另案。

本轮已授权工程交付不依赖这些决定，可完成文档、schema、元数据测试、静态来源核对和公开归档；正式训练仍不能启动。继续保持RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true，V2_PHASE_B_AUTHORIZED=false，2025_RAW_ACCESS=2025_PIXELS_READ=0，HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；交付后自动下一阶段关闭。
