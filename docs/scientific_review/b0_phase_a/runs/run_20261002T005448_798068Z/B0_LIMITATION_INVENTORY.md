# B0 limitation inventory

Scope: SCIENTIFIC_RESULT_REVIEW_ONLY；review `run_20261002T005448_798068Z`。

| Item | Evidence class | Supported statement / limit |
|---|---|---|
| Epoch 11 后 validation degradation | OBSERVED | OBSERVED：epoch 11→19，Train core 从 0.03892391586529146 降至 0.03534704007581559；Val core 从 0.04730775889882134 升至 0.048634870497155404，差值 0.001327111598（相对约 2.8053%）。epoch 12–19 无一优于 epoch 11，epoch 19 的独立 early-stop counter=8。这里只描述 Validation degradation，不定义‘严重过拟合’，不确定物理原因。 |
| Low-tau calibration deviation | OBSERVED | tau=0.015625 coverage=0.003060810953，error=-0.012564189047；严格单调不能消除校准偏差。 |
| 月份差异 | OBSERVED | 全 8 月 metrics 与 support 见 monthly_metrics.csv；不能只用月份排名推断天气成因。 |
| 空间差异 | OBSERVED | frozen Yunnan 内 cell metric ranges/maps 有差异；没有事后 regional masks；低计数只影响指标显示。 |
| 强降水样本支持 | OBSERVED_DESCRIPTIVE_ONLY | >50 mm/h 仅 72 个 rainy pixels（fraction=1.497135792e-05）；其它阈值 count 完整列表，不能把 pixel 数当独立事件数或固定 extreme definition。 |
| single-band / single-time | DESIGN_FACT | 仅 B13 一帧，缺少其它模块信息；未实验证明其造成某项特定误差。 |
| DIAGNOSTIC_PROXY 含义 | DEFINITION_LIMIT | p_rain×32-quantile physical mean，不是 exact expectation，proxy MAE/RMSE/Bias 不能改称精确期望预测误差。 |
| Quantile tail extrapolation | NOT_ESTABLISHED | 只有冻结 32 tau；未建立 outside-grid tail model，不宣称极端尾部分布已完备。 |
| 气象/地形因果 | HYPOTHESIS_NOT_ESTABLISHED | 云顶温度与地面雨强的非唯一性、天气系统或地形解释均缺独立变量/可比实验支持。 |
| 泛化范围 | DESIGN/EVIDENCE_BOUNDARY | 本结果是 frozen 2024 March–October Validation；没有读 2025，不证明未触及 test year、全国或所有年际天气泛化。 |
| Validation 的科研用途 | PROTOCOL_BOUNDARY | 本轮诊断不反向修改已完成 B0 Protocol、不改变 BEST；任何后续试验另由研究者批准。 |

不同月份/雨强/空间诊断不是独立试验；未构造置信区间、显著性或物理归因。
Acceptance 与 epoch-budget transfer 均 UNDECIDED，Phase-B 未授权。
