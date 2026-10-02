# B0 limitation inventory — partial history evidence

Review `run_20261002T000346_890906Z` 未完成完整再推理。以下区分已观察、设计事实和待核验。

| Item | Evidence class | Current evidence / limit |
|---|---|---|
| Epoch 11 后 Validation degradation | OBSERVED | OBSERVED：epoch 11→19，Train core 从 0.03892391586529146 降至 0.03534704007581559，Val core 从 0.04730775889882134 升至 0.048634870497155404，增加 0.001327111598（相对 epoch 11 约 2.8053%）。epoch 12–19 均未优于 epoch 11；epoch 19 的独立 early-stop counter 达到 8。该记录支持‘验证损失在 epoch 11 后未继续改善并总体上升’的描述，不据此定义‘严重过拟合’，也不确立气象物理原因。 |
| 最低 tau calibration deviation | OBSERVED_HISTORICAL_ONLY | tau=0.015625，正式历史 coverage=0.0030608109527127583；本轮未再推理。 |
| 月份差异 | NOT_EVALUATED_THIS_REVIEW | 完整月度分析缺失，不能给月份排名或物理解释。 |
| 空间差异 | NOT_EVALUATED_THIS_REVIEW | 尚无本轮 cell-level 统计；未创建 subregions。 |
| 强降水样本稀疏 | NOT_ESTABLISHED_THIS_REVIEW | 未计算 >10/20/30/50 计数；不推断稀疏程度或 extreme 定义。 |
| single-band / single-time 信息限制 | DESIGN_FACT | 输入仅 B13 一帧；不存在多通道/时序/GFS/地形/teacher。不能直接归因为某个误差。 |
| Historical probability calibration | OBSERVED_HISTORICAL_ONLY | 单调性不保证 coverage；各 tau 历史校准误差已列表。没有进行再校准。 |
| 科学因果解释 | HYPOTHESIS_NOT_ESTABLISHED | 云顶—地面降水非唯一性等尚无额外变量证据，不作为结论。 |
| 数据可用性 | ENGINEERING_BLOCKER | 当前 H 不可见；第一场未进入模型；不是已经完成的科研链回退。 |

接受 Phase-A 与是否迁移预算由研究者决定；本 packet 未完备，Phase-B 仍未授权。
