# B0 Phase-A Scientific Characterization Review v1

状态：**BLOCKED_SOURCE_DRIVE_UNAVAILABLE / REVIEW INCOMPLETE**。

Review run：`run_20261002T000346_890906Z`；baseline：`5383dfceda6cc64e6907c6953032a14935c0ee46`。
Scope：`SCIENTIFIC_RESULT_REVIEW_ONLY`。正式 training run：`run_20261001T035003_243409Z`。

## 执行结果与阻塞证据

真实全量再推理已启动，但第一个 B13 staging read 的 `resolve(strict=True)` 返回 WinError 3 / FileNotFoundError；当前文件系统 drive 列表没有 H。
第一场样本未进入模型，scenes inferred=0、Validation pixels read=0、2025 pixels read=0。
失败 trace 保存在 `failure_20261002T000607_942814Z.json` 与 `reinference_console.log`；私有 read ledger 长度为 0；本 run staging 内无临时文件残留。
F 盘第一日 IMERG 路径可见。没有把其它盘、其它时间或其它来源替换为冻结 H 源。

本轮完整 2024 再推理、monthly_metrics、空间 cell diagnostics、reliability、概率分布、雨强分层、强降水子集、客观案例及全量 quantile numerical checks 均为 NOT_RUN_SOURCE_DRIVE_UNAVAILABLE。没有用既有总体指标或抽样填充这些产物。全量覆盖、monthly/spatial/rain-bin/probability-bin 对账和新再推理 coverage 精确复现测试未执行，不能当作 PASS。

## 正式身份核验

Protocol v1.0、Scientific Freeze v1.1 文档与配置、engineering v4、Phase-A 2023 normalization、Train/Validation manifests、SP04 和云南 mask 的全部冻结 SHA 均核验通过，见 `identity_verification.json`。
正式 BEST：epoch=11，global_update=64460，global_val_core_loss=0.04730775889882134。
路径：`F:\pytorch\Research\outputs\formal_training\b0_phase_a\run_20261001T035003_243409Z\epoch_011.pt`；bytes=52062315；SHA256=`3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3`。
checkpoint full payload 对原始 `checkpoint_expected` 核验通过；只把 model state 加载到独立推理模型，不实例化或恢复 optimizer。
收尾复核原有 1466 个 baseline 文件的 SHA 未变，BEST 文件 SHA 与大小未变。

`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`。冻结 criterion 是 minimum global_val_core_loss。
epoch 13 的 AUROC/AP 较 epoch 11 高、epoch 15 的 Brier 较 epoch 11 低、epoch 12 的 conditional pinball 较 epoch 11 低，都不能事后替换 criterion 或 BEST。

## 19 epoch 学习曲线和比较

只使用原始 `training_history.csv` 与 `validation_history.csv` 的完整 19 epoch 数值生成 6 张 600 dpi 图。
Train/Val core、occurrence、quantile loss、Val Brier/AUROC/AP、conditional pinball、历史 LR、gradient norm/clipping fraction 和 generalization gap 均已绘制。
BEST=11 与 early-stop=19 标记可见；没有平滑、删点或省略不利 epoch。LR 图显示 history 的真实 epoch start/end 值，未伪造每 update 的观测。
表中 historical BEST/ES count 来自原有 epoch JSON，不对 checkpoint 进行新选择。

| epoch | Train core | Val core | Brier | AUROC | AP | conditional pinball | historical BEST | ES count |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 0.0398719133 | 0.0475766694 | 0.0960739790 | 0.8885710855 | 0.5593711986 | 0.1274530741 | 9 | 0 |
| 11 | 0.0389239159 | 0.0473077589 | 0.0948522179 | 0.8881853942 | 0.5568845072 | 0.1255707637 | 11 | 0 |
| 12 | 0.0384440286 | 0.0475869454 | 0.0932065049 | 0.8854152652 | 0.5529604975 | 0.1252098031 | 11 | 1 |
| 13 | 0.0380182245 | 0.0476811650 | 0.0888289640 | 0.8894662387 | 0.5618270474 | 0.1268282325 | 11 | 2 |
| 15 | 0.0371535276 | 0.0482586143 | 0.0874830448 | 0.8889246850 | 0.5478099418 | 0.1273701867 | 11 | 4 |
| 19 | 0.0353470401 | 0.0486348705 | 0.0916908696 | 0.8850312062 | 0.5445404338 | 0.1290711000 | 11 | 8 |


OBSERVED：epoch 11→19，Train core 从 0.03892391586529146 降至 0.03534704007581559，Val core 从 0.04730775889882134 升至 0.048634870497155404，增加 0.001327111598（相对 epoch 11 约 2.8053%）。epoch 12–19 均未优于 epoch 11；epoch 19 的独立 early-stop counter 达到 8。该记录支持‘验证损失在 epoch 11 后未继续改善并总体上升’的描述，不据此定义‘严重过拟合’，也不确立气象物理原因。

## 泛化差距

gap 固定为 Val core − Train core，逐 epoch 记录在 `generalization_gap.csv`。
Train 是 2023、Val 是 2024；Train occurrence 使用原有生产 AMP/FP32 算法，Val numerator 使用冻结 float64 算法。
因此 gap 是所定义的记录值差，不能将其全部归因于数据泛化、物理过程或单一精度因素。

| epoch | Train core | Val core | Val - Train |
|---:|---:|---:|---:|
| 1 | 0.0812740455 | 0.0519111694 | -0.0293628761 |
| 3 | 0.0434427642 | 0.0494367586 | 0.0059939944 |
| 6 | 0.0413650269 | 0.0482979454 | 0.0069329184 |
| 9 | 0.0398719133 | 0.0475766694 | 0.0077047561 |
| 11 | 0.0389239159 | 0.0473077589 | 0.0083838430 |
| 15 | 0.0371535276 | 0.0482586143 | 0.0111050867 |
| 19 | 0.0353470401 | 0.0486348705 | 0.0132878304 |


## 历史 epoch 11 的概率指标与 quantile 校准

下列全部来自已核验的正式 epoch 11 历史统计，**不是本轮再推理结果**。
N_valid=40,223,610；N_rain=4,809,183；prevalence=0.119561198013。
Brier=0.094852217850, AUROC=0.888185394186, AP=0.556884507248, conditional mean pinball=0.125570763653。
DIAGNOSTIC_PROXY 为 p_rain × mean(32 physical conditional quantiles)，不是 exact expected precipitation。

tau=0.015625 的历史 coverage=0.0030608109527127583，coverage−tau=-0.012564189047287242。
这直接显示该最低 quantile 的历史 coverage 低于名义 tau。全部 32 个历史值与误差另存 `historical_quantile_calibration.csv`，没有变动 quantile、sort、clamp 或校准模型。

以下分组均为 `ANALYTIC_GROUPING_ONLY`：low tau<0.2；middle 0.2≤tau≤0.8；high tau>0.8。

- low：6 个 tau，mean absolute coverage error=0.023982123757。
- middle：20 个 tau，mean absolute coverage error=0.015406321679。
- high：6 个 tau，mean absolute coverage error=0.009429479758。

历史 epoch 11 crossing/nonfinite 为 0；**本轮全量 numerical count 为 null / NOT_RUN**，历史 0 不替代新检查。
单调性与校准是不同性质；历史严格单调不表示 coverage 已贴合 tau。

## 预声明诊断规则与空间边界

`case_selection_rules.json` 在再推理启动前已保存：10 个等宽 reliability bins（末 bin 包含 1）、7 个 true-rate bins、>10/20/30/50 的 DESCRIPTIVE_ONLY 子集，
以及三种固定 top-10 case 规则（最大绝对 proxy error、最高 truth rate、最低 rainy truth rate），ties 使用冻结 scene order 和 row-major cell index。
真实 rainy label 在 float32 target 上判定 R>0.1，再提升到 float64；没有改动生产阈值边界。
空间 conditional pinball 仅在 rainy_count≥30 时显示，规则为 DISPLAY_DIAGNOSTIC_ONLY；评价计数和 loss 样本不变。
没有发现 config/src/scientific_freeze/training_protocol 中预冻结 subregion masks：`NO_PREDEFINED_SUBREGION_MASK_AVAILABLE`。
因此准备使用 Yunnan-wide cell diagnostics，不创建事后地区，不从误差地图改 mask 或 loss weight。
由于 H 不可访问，本轮没有生成上述全量统计、case 结果或空间图。

## B0 的科学角色与解释边界

B0 是 `CONTROL / BASELINE`：只使用 latest causal Himawari B13 single frame。
没有 multi-temporal、multi-channel、GFS、DEM/terrain、DOTE、DTFM、MEE 或 ERA5 teacher。
这是设计事实，不等同于已证明某种缺失信息导致某个误差；B0 不能独立证明完整 YunTAPR-Net 有效。
月份差异、空间差异和强降水稀疏性在本轮未获新统计支持，不作结论。
具体天气成因均为 `POSSIBLE_EXPLANATION_NOT_ESTABLISHED`；没有以 hypothesis 替代 observed。

## 测试与科研授权

新增 8 项 unit tests 真实执行，通过、零 failure/error/skip，见 `test_results.txt`。
这些检查覆盖 probability edges/1.0、weighted percentiles、float32 threshold、toy count reconciliation、2025/path escape 拒绝、optimizer/step/backward 硬 guard 和分开的 quantile numerical counts。
现有 171 项未重跑：部分独立 fixture 会执行 optimizer/backward，已向研究者发出一项范围确认，尚未收到答复；没有把历史 171 PASS 当作本轮结果。
11 项 full-review artifact tests 已编写，因全量产物缺失未执行。测试总体为 PARTIAL_NOT_FULL_REVIEW_PASS。

`B0_PHASE_A_SCIENTIFIC_REVIEW_COMPLETED=false`；`FULL_2024_REINFERENCE_COMPLETED=false`。
`B0_PHASE_A_ACCEPTED=UNDECIDED`；`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`；`PHASE_B_AUTHORIZED=false`。
没有训练、epoch 20、模型更新、normalization 拟合、校准、阈值选择或 B1–B8 执行。
需要 H 恢复以及测试范围答复后，另建可追溯完整 review run；本次失败记录保留，不自动进入下一 Stage。
