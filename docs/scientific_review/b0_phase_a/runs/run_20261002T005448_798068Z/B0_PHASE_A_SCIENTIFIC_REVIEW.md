# B0 Phase-A Scientific Characterization Review v1

本轮 `B0_PHASE_A_SCIENTIFIC_REVIEW_COMPLETED=true`：完整 2024 Validation 再推理、月度/空间/雨强诊断、概率可靠性、32-quantile 校准、图件检查及 190 项测试均真实执行。
这是 `SCIENTIFIC_RESULT_REVIEW_ONLY` 的工程和结果审阅完成，不是科研接受决定或下一 Stage 授权。

Review run：`run_20261002T005448_798068Z`。执行 parent：`1130bc0160d1db317e93641d8c3631f637fcfe2c`；科研结果 baseline：`5383dfceda6cc64e6907c6953032a14935c0ee46`。
正式训练 run：`run_20261001T035003_243409Z`；旧阻塞 run `run_20261002T000346_890906Z` 的全部文件保持 immutable，并通过 parent Git blob 与收尾 SHA 核验。

## 1. 冻结身份、预检与只读执行

冻结 Protocol v1.0、Scientific Freeze v1.1、engineering v4、Phase-A 2023 normalization、Train/Validation manifests、SP04、Yunnan mask 的 SHA 均核验通过。
新 run 创建前，source preflight 已逐项核验全部 11727 个 B13 来源以及 245 个 IMERG 日文件的存在、size 和 SHA。
B13 size 独立匹配正式 ledger；IMERG 历史 ledger 独立冻结 SHA，本轮 size>0 且 hash 前后稳定，同时记录实际 bytes，未伪造历史 size 字段。
源路径始终为 `H:\葵花202303_202510` 与冻结 IMERG 2024 文件，无盘符替换、静默 fallback 或未来帧。

BEST：epoch=11；global_update=64460；official global_val_core_loss=0.04730775889882134。
`F:\pytorch\Research\outputs\formal_training\b0_phase_a\run_20261001T035003_243409Z\epoch_011.pt`；bytes=52062315；SHA256=`3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3`。
full payload 只做 provenance/checksum 验证；只将 model state 加载到独立推理模型，optimizer state 不应用。
完整顺序为 frozen eligible Validation identity order；batch=8，eval/no_grad，BF16 forward，FP32 raw quantile，qlog/qphysical float64。
模型逻辑 SHA 前后均为 `015e02a97fc916757c0442269000703393759657156df407a4d672ec34478dca`；checkpoint 文件未修改。
`MODEL_PARAMETERS_UPDATED=false`、`OPTIMIZER_STEPS=0`、`BACKWARD_CALLS=0`，硬 guard 的 prohibited attempts 全部为 0。
本轮仅访问 2024 raw sources；`2025_PIXELS_READ=0`。

保留原始 reader/QC/normalization/SP04 和 formal batch/forward 的输入合同，未改变冻结科学实现。
旧 mixed-year per-frame QC 文件不打开；source SHA 与 frozen pair 证据验证实际 B13 obs_start/obs_end/date_created。
历史 wrapper 的 FORMAL_SCIENTIFIC_RUN tensor-contract tag 不授予优化权限；本轮进程权限始终为更窄的只读 review scope。

## 2. 19 epoch 学习曲线、BEST 和 early stop

图件只用正式 training_history.csv / validation_history.csv 的完整 19 epoch 值，不平滑、不删点；BEST=11 与 stop=19 均标明。
Train/Val core、occurrence、quantile、Val Brier/AUROC/AP、conditional pinball、LR、grad-norm/clipping 和 gap 均已展示。
LR 图只显示 history 真实 epoch start/end 记录，不将中间连线宣称为逐 update 观测。
Train occurrence 保留原生产 AMP/FP32 算法，Val numerator 使用冻结 FP64 算法；gap 是规定的记录值差，不能全部解释成数据泛化或单一精度影响。

| Epoch | Train core | Val core | Brier | AUROC | AP | Conditional pinball | Historical BEST | ES count |
|---|---|---|---|---|---|---|---|---|
| 9 | 0.03987191326 | 0.04757666937 | 0.09607397901 | 0.8885710855 | 0.5593711986 | 0.1274530741 | 9 | 0 |
| 11 | 0.03892391587 | 0.0473077589 | 0.09485221785 | 0.8881853942 | 0.5568845072 | 0.1255707637 | 11 | 0 |
| 12 | 0.0384440286 | 0.04758694544 | 0.0932065049 | 0.8854152652 | 0.5529604975 | 0.1252098031 | 11 | 1 |
| 13 | 0.03801822448 | 0.04768116502 | 0.08882896398 | 0.8894662387 | 0.5618270474 | 0.1268282325 | 11 | 2 |
| 15 | 0.03715352757 | 0.0482586143 | 0.08748304476 | 0.888924685 | 0.5478099418 | 0.1273701867 | 11 | 4 |
| 19 | 0.03534704008 | 0.0486348705 | 0.09169086961 | 0.8850312062 | 0.5445404338 | 0.1290711 | 11 | 8 |


`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`：criterion 冻结为 minimum global_val_core_loss。
epoch 13 的 AUROC/AP、epoch 15 的 Brier 和 epoch 12 的 conditional pinball 某些值更好，不改变正式 checkpoint 选择。

OBSERVED：epoch 11→19，Train core 从 0.03892391586529146 降至 0.03534704007581559；Val core 从 0.04730775889882134 升至 0.048634870497155404，差值 0.001327111598（相对约 2.8053%）。epoch 12–19 无一优于 epoch 11，epoch 19 的独立 early-stop counter=8。这里只描述 Validation degradation，不定义‘严重过拟合’，不确定物理原因。

## 3. 泛化差距

generalization_gap=Val core−Train core，逐 epoch 全表见 generalization_gap.csv。

| Epoch | Train core | Val core | Val − Train |
|---|---|---|---|
| 1 | 0.08127404553 | 0.0519111694 | -0.02936287613 |
| 3 | 0.04344276415 | 0.04943675858 | 0.005993994429 |
| 6 | 0.04136502694 | 0.04829794537 | 0.006932918435 |
| 9 | 0.03987191326 | 0.04757666937 | 0.007704756112 |
| 11 | 0.03892391587 | 0.0473077589 | 0.008383843034 |
| 15 | 0.03715352757 | 0.0482586143 | 0.01110508673 |
| 19 | 0.03534704008 | 0.0486348705 | 0.01328783042 |


## 4. 全量 2024 再推理与精确复现

真实推理 11,727 场（2024 March–October），N_valid=40,223,610，N_rain=4,809,183，prevalence=0.119561198013。
global core=0.047307758898821342；occurrence=0.032294367961026665；quantile core=0.015013390937794673。
Brier=0.094852217850；AUROC=0.888185394186；AP=0.556884507248；conditional mean pinball=0.125570763653。
全部 32 个 conditional coverage 对正式 epoch 11 **逐值精确相等**；global metrics/per-tau pinball 按预声明 atol=rtol=1e-12 比较均 PASS。
monthly/spatial/rate strata/probability bins/histograms 与全局计数对账全部通过；没有抽样替代全量。

DIAGNOSTIC_PROXY=p_rain×mean(32 physical conditional quantiles)，不是 exact expected precipitation。
全局 proxy MAE=0.259270339666、RMSE=0.845521029192、Bias=0.053690863006 mm/h。
全局 loss numerator 使用 N_valid 作为 denominator；conditional mean pinball 使用 N_rain。pinball 在 log1p(rate / mm h−1) 域，是无量纲量。

## 5. 月度性能与季节描述

| 2024 month | Scenes | N valid | N rain | Prevalence | Core | Occurrence | Quantile core | Brier | AUROC | AP | Cond. pinball |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024-03 | 1485 | 5093550 | 84024 | 0.0164961569 | 0.01000543355 | 0.00771929765 | 0.0022861359 | 0.02897553211 | 0.9392615838 | 0.2835895836 | 0.1385859696 |
| 2024-04 | 1435 | 4922050 | 153074 | 0.03109964344 | 0.01725174892 | 0.01321279409 | 0.004038954828 | 0.04549752182 | 0.9152950397 | 0.3105287337 | 0.1298714191 |
| 2024-05 | 1485 | 5093550 | 663217 | 0.1302072229 | 0.05515746803 | 0.0374991456 | 0.01765832242 | 0.1056827206 | 0.8591167365 | 0.4697624002 | 0.1356170728 |
| 2024-06 | 1436 | 4925480 | 822114 | 0.1669104331 | 0.06451472658 | 0.04179780391 | 0.02271692267 | 0.1271854909 | 0.8624609516 | 0.5991028932 | 0.1361024727 |
| 2024-07 | 1485 | 5093550 | 1059791 | 0.2080652983 | 0.07259897712 | 0.04701676721 | 0.02558220991 | 0.1389291529 | 0.8568411325 | 0.6300870653 | 0.1229527947 |
| 2024-08 | 1487 | 5100410 | 831632 | 0.1630519899 | 0.05968680903 | 0.03928589785 | 0.02040091118 | 0.1173035869 | 0.8820585992 | 0.6191515492 | 0.1251190568 |
| 2024-09 | 1428 | 4898040 | 716163 | 0.1462142 | 0.05589420693 | 0.03866665374 | 0.01722755319 | 0.1125502601 | 0.8655786894 | 0.5668200094 | 0.1178240772 |
| 2024-10 | 1486 | 5096980 | 479168 | 0.09401017858 | 0.0432241448 | 0.03306234723 | 0.01016179757 | 0.08275581927 | 0.8454145443 | 0.4230303163 | 0.1080925249 |


| 2024 month | Proxy MAE mm/h | Proxy RMSE mm/h | Proxy Bias mm/h | Crossing | Nonfinite |
|---|---|---|---|---|---|
| 2024-03 | 0.08665333602 | 0.336820396 | 0.05372644425 | 0 | 0 |
| 2024-04 | 0.1205732557 | 0.4514143148 | 0.0633281848 | 0 | 0 |
| 2024-05 | 0.2899105985 | 0.9290481504 | 0.0363673798 | 0 | 0 |
| 2024-06 | 0.4059629897 | 1.431504135 | 0.06440752507 | 0 | 0 |
| 2024-07 | 0.3880192785 | 0.9385475039 | 0.04375830597 | 0 | 0 |
| 2024-08 | 0.3307934607 | 0.8523126792 | 0.07785328184 | 0 | 0 |
| 2024-09 | 0.2829403736 | 0.7926390437 | 0.05436954623 | 0 | 0 |
| 2024-10 | 0.1703519498 | 0.5271387463 | 0.03639949131 | 0 | 0 |


- OBSERVED：core loss 范围 0.0100054335（2024-03）至 0.0725989771（2024-07）。
- OBSERVED：Brier 范围 0.0289755321（2024-03）至 0.1389291529（2024-07）。
- OBSERVED：AUROC 范围 0.8454145443（2024-10）至 0.9392615838（2024-03）。
- OBSERVED：AP 范围 0.2835895836（2024-03）至 0.6300870653（2024-07）。
- OBSERVED：conditional pinball 范围 0.1080925249（2024-10）至 0.1385859696（2024-03）。

以上是 March–October 的观察差异，各月 rain prevalence 和样本数不同，排名指标、Brier 与 conditional pinball 衡量性质不同。
月份关联不等于季节气象因果；具体天气系统、地形或云物理原因均为 `POSSIBLE_EXPLANATION_NOT_ESTABLISHED`。
没有用 2024 结果改已完成的 loss、LR、参数或 protocol。

## 6. 空间 cell diagnostics

先检索冻结 config/src/scientific_freeze/training_protocol；无预定义区域：`NO_PREDEFINED_SUBREGION_MASK_AVAILABLE`。
不生成 regional_metrics.csv，不创建事后 A/B/C 或‘差区域’；仅对正式 Yunnan mask 内 3,430 个 target cell 展示统计。
网格为 100×100，精确冻结 Float32 lat/lon；lat ascending，无 transpose，无 silent flip。原数组坐标 hash 见 spatial_summary.json。
空间汇总先在本 run 的英文私有路径写入，再验证 size/SHA 后复制到中文仓库；reader 从公共文件字节构造 netCDF memory dataset，不改变任何原始 source path。
raw proxy signed/absolute/squared sums 的物理单位另行审计，metadata 修改前后全部变量数值与坐标逐字节 hash 相同，见 spatial_metadata_audit.json。
评价之外不显示指标；每 cell valid/rain counts 完整保留并对账至 global counts。
conditional pinball 仅 rainy_count≥30 时报告，`DISPLAY_DIAGNOSTIC_ONLY`；低于规则的 cell 数=0。
此显示规则不排除全局/月度评价样本、不改变 loss weight 或 evaluation mask。

| Cell diagnostic | Min | Median | Max |
|---|---|---|---|
| valid_count | 11727 | 11727 | 11727 |
| rainy_count | 839 | 1334 | 3026 |
| rain_frequency | 0.07154429948 | 0.1137545834 | 0.2580370086 |
| mean_probability | 0.2143275197 | 0.2474120199 | 0.3393335259 |
| brier | 0.0721024226 | 0.09411994334 | 0.1540193468 |
| conditional_pinball | 0.08476956564 | 0.1250087781 | 0.1824107687 |
| DIAGNOSTIC_PROXY_bias_mm_h | -0.1008839894 | 0.05265211431 | 0.2400180863 |
| DIAGNOSTIC_PROXY_MAE_mm_h | 0.1941884903 | 0.2463271704 | 0.4184794438 |
| DIAGNOSTIC_PROXY_RMSE_mm_h | 0.3804945634 | 0.7286783505 | 18.19081618 |


OBSERVED：表中的 cell 范围和图中的差异属于 cell diagnostics；不是新科研分区，不能从这些地图重定义训练 region 或物理归因。

## 7. Occurrence reliability 与概率分布

固定预声明 bins：[0,0.1)，…，[0.9,1]，末 bin 包含 1；所有 40,223,610 valid pixels 分箱，不选择 cutoff 或拟合 calibration。

| Bin | Lower | Upper | Count | Mean p | Rain frequency |
|---|---|---|---|---|---|
| 0 | 0 | 0.1 | 7315696 | 0.06722329399 | 0.002476729487 |
| 1 | 0.1 | 0.2 | 10580662 | 0.1510653483 | 0.01467620835 |
| 2 | 0.2 | 0.3 | 9241226 | 0.2462354605 | 0.05069035212 |
| 3 | 0.3 | 0.4 | 6180689 | 0.3466050563 | 0.1583139032 |
| 4 | 0.4 | 0.5 | 3894972 | 0.4446404672 | 0.3352848236 |
| 5 | 0.5 | 0.6 | 2033408 | 0.5427437045 | 0.5510448469 |
| 6 | 0.6 | 0.7 | 836414 | 0.6416998079 | 0.7597015354 |
| 7 | 0.7 | 0.8 | 139996 | 0.7268998143 | 0.9032972371 |
| 8 | 0.8 | 0.9 | 547 | 0.803609175 | 0.9926873857 |
| 9 | 0.9 | 1 | 0 |  |  |


overall Brier=0.094852217850。补充固定-bin weighted absolute calibration deviation=Σ(N_bin/N_valid)|mean p_bin−observed frequency_bin|=0.135589834112，仅 `BINNED_DIAGNOSTIC`，不是新 checkpoint metric 或接受阈值。
没有做 temperature/isotonic/Platt scaling，也没有 probability cutoff、POD/FAR/CSI 冻结。

| Truth group | Count | Mean p | SD p | p1 | p5 | p25 | Median | p75 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|---|
| rainy_truth | 4809183 | 0.4563017582 | 0.1363660495 | 0.1337890625 | 0.2216796875 | 0.36328125 | 0.458984375 | 0.5546875 | 0.67578125 | 0.73046875 |
| dry_truth | 35414427 | 0.2199076782 | 0.1292498572 | 0.033203125 | 0.0517578125 | 0.1157226562 | 0.19921875 | 0.30078125 | 0.46484375 | 0.57421875 |


概率 SD 的 ddof=0；percentiles 使用完整群体的精确 weighted type-7/linear order statistics。图是预声明 0.01-bin density-style histogram，不做 KDE 或平滑。

## 8. 32-quantile calibration 与 tails

tau=(i−0.5)/32。全部 32 项 coverage、coverage−tau、absolute calibration error、conditional pinball 见 quantile_calibration.csv；实际输出未 sort/clamp/校准。

| tau | Coverage | Coverage − tau | Abs. error | Pinball (log1p domain) |
|---|---|---|---|---|
| 0.015625 | 0.003060810953 | -0.01256418905 | 0.01256418905 | 0.00919442781 |
| 0.046875 | 0.08937713537 | 0.04250213537 | 0.04250213537 | 0.02739257065 |
| 0.484375 | 0.5092049939 | 0.02482999386 | 0.02482999386 | 0.1773592386 |
| 0.515625 | 0.5301282983 | 0.0145032983 | 0.0145032983 | 0.1803171387 |
| 0.796875 | 0.7905226314 | -0.006352368609 | 0.006352368609 | 0.1487790022 |
| 0.953125 | 0.9424846174 | -0.01064038255 | 0.01064038255 | 0.05865329463 |
| 0.984375 | 0.9774913951 | -0.006883604892 | 0.006883604892 | 0.02524557121 |


OBSERVED：lowest tau=0.015625，coverage=0.0030608109527127583，error=-0.012564189047287242，低于名义 tau。
中间 pair 是 tau=0.484375/0.515625（本模型不存在恰好 0.5 的输出 tau），高 tail 包含 0.953125/0.984375；表与 32 项曲线完整报告误差方向。
low tau<0.2、middle 0.2≤tau≤0.8、high tau>0.8 均仅 `ANALYTIC_GROUPING_ONLY`，不是模型定义或新分位设计。

- low：6 个 tau，mean absolute coverage error=0.023982123757。
- middle：20 个 tau，mean absolute coverage error=0.015406321679。
- high：6 个 tau，mean absolute coverage error=0.009429479758。

单调性不等于 calibration；coverage 贴合也不自动证明完整条件分布/高尾外推或科学接受。

## 9. Quantile 数值检查

下表在每场全部 100×100 输出 cell 上检查（117,270,000 cell outputs），评价统计另用 frozen valid Yunnan population。
qlog 与 qphysical crossing 定义为相邻 q[i+1]≤q[i]，检查严格单调；q1 support violation 定义为 qlog[1]≤log1p(0.1)。

| Full output numerical check | Count |
|---|---|
| qlog_crossing_count | 0 |
| qphysical_crossing_count | 0 |
| nonfinite_qlog | 0 |
| nonfinite_qphysical | 0 |
| q1_support_violation | 0 |


所有输出 tensor 的 finite/FP32参数/FP64 quantile 精度 gate 也实际通过；global accumulation nonfinite/crossing=0。

## 10. 描述性雨强和强降水子集

仅根据真实 float32 IMERG target 的 frozen R>0.1 label 分层，生产阈值先在原 dtype 判定、再提升 FP64。
`DESCRIPTIVE_RATE_BINS_ONLY`，不是 extreme precipitation definition，也不用于 loss reweight。

| True-rate bin mm/h | Count | Rain fraction | Cond. pinball | Proxy Bias mm/h | Proxy MAE mm/h |
|---|---|---|---|---|---|
| (0.1,1] | 2958855 | 0.6152510728 | 0.08410353024 | 0.1030990068 | 0.3363382779 |
| (1,5] | 1570559 | 0.3265750128 | 0.156520526 | -1.176063667 | 1.369687288 |
| (5,10] | 222116 | 0.04618580744 | 0.3457864429 | -4.844925431 | 4.859714386 |
| (10,20] | 49586 | 0.01031069103 | 0.5248238111 | -10.57030688 | 10.57030688 |
| (20,30] | 6495 | 0.001350541246 | 0.757552923 | -20.81127609 | 20.81127609 |
| (30,50] | 1500 | 0.00031190329 | 0.9269654295 | -32.38302806 | 32.38302806 |
| (50,inf) | 72 | 1.497135792e-05 | 1.09084143 | -53.50137933 | 53.50137933 |


| True rate > mm/h (DESCRIPTIVE_ONLY) | Count | Cond. pinball | Proxy Bias mm/h | Proxy MAE mm/h |
|---|---|---|---|---|
| 10 | 57653 | 0.5622120004 | -12.34515319 | 12.34515319 |
| 20 | 8067 | 0.7920286305 | -23.25472661 | 23.25472661 |
| 30 | 1572 | 0.9344712005 | -33.35028079 | 33.35028079 |
| 50 | 72 | 1.09084143 | -53.50137933 | 53.50137933 |


>50 mm/h 子集 count=72，约占 rainy population 0.0014971358%。
各 threshold 子集重叠，不能相加当作互斥档；完整 per-tau conditional coverage/pinball 存在 strong_rain_quantiles_DESCRIPTIVE_ONLY.json。
高雨强组的数量、proxy 误差与 quantile 行为只支持本群体描述，不估计事件独立性、置信区间或全国/多年泛化。
项目正式 extreme definition=`NOT_FROZEN`；本轮不冻结任何强降水阈值。

## 11. 客观案例

case_selection_rules.json 在 inference_start 前写入并哈希固定；三种规则各 top-10，合计 30 case records。
最大绝对 proxy error、最高真实雨强、最低 rainy 真实雨强；tie 用原冻结 scene order 后 row-major cell index，没有人工选择‘好看’案例。
每条存 time/位置/IMERG/p_rain、全部 32 physical quantiles 及摘要、proxy 与 error。案例没有额外训练或改变总体评价。
最高 true-rate 案例：window_start=2024-06-13T19:00:00+00:00，R=77.22999572753906 mm/h，p_rain=0.71484375，proxy=5.006185313533549 mm/h。
case 集合由极值规则筛选，不能当作随机样本、总体误差率或 causal proof。

## 12. 科学角色、限制与解释

B0 是 `CONTROL / BASELINE`，仅 latest causal Himawari B13 single frame。
没有 multi-temporal/multi-channel/GFS/DEM/terrain/DOTE/DTFM/MEE/ERA5 teacher。
这是设计事实，不等于实验证明缺失某项信息导致某个误差；不能宣称 B0 已证明完整 YunTAPR-Net 有效。
后续 B1–B8 需严格可比实验且另获授权；本轮不启动。
直接支持的限制与未证实 hypothesis 分别列在 B0_LIMITATION_INVENTORY.md；气象物理解释没有额外变量证据时仍为 `POSSIBLE_EXPLANATION_NOT_ESTABLISHED`。

## 13. 190 项隔离测试、清理与完整性

existing regression/formal=171；scientific-review units=8；full-review artifact=11；合计=190。
实际 suite counts、每个 test 和结果见 test_results.txt / test_summary.json；无 failure/error/skip。
`TEST_FIXTURE_ONLY=true`。获批的临时 optimizer/backward/step 只属于隔离 fixture；测试进程没有加载 BEST 到测试模型，也没有共享 Scientific Review inference model。
测试的全量 artifact 阶段只读取 BEST SHA 作 identity verification，不应用 checkpoint tensors。
fixture 临时目录已完全清理，模型/optimizer 内存随独立进程退出释放；fixture 操作不计入 review OPTIMIZER_STEPS/BACKWARD_CALLS。
前后检查 1495 个 immutable parent 文件（含旧阻塞 run）及 BEST SHA 均不变，所有本 run staging 文件已清理。

## 14. 运行与中文路径 I/O

reinference wall_seconds=522.921；peak GPU allocated=3,449,582,080 bytes；reserved=4,729,077,760 bytes。
staging copy_seconds sum=191.800；read_seconds sum=159.569；peak temporary bytes per worker=6,019,956；cleanup_success=True。
这些 sums 是两个 worker 的工作量，会重叠，不等于 wall time；copy 计时不包含独立 SHA 验证时间，实际 SHA/copy/read 额外 I/O 都存在。
每 worker 一次仅一个文件、cap=734003200 bytes，复制前后 size+SHA 相等，成功读取后只删除本流程 owned copy；原始 H 与诊断缓存不变。
详细 11,727-scene read ledger 存 F 盘，本仓库仅保存 path/bytes/SHA；不提交 raw data、model/optimizer binaries、cache、wheel 或 venv。

## 15. 图件、输出与研究者决定

- [figures/loss_curves.png](figures/loss_curves.png) — 600 dpi，7200×2100。
- [figures/occurrence_metrics.png](figures/occurrence_metrics.png) — 600 dpi，7200×2100。
- [figures/quantile_metrics.png](figures/quantile_metrics.png) — 600 dpi，3900×2400。
- [figures/learning_rate.png](figures/learning_rate.png) — 600 dpi，4200×2400。
- [figures/gradient_clipping.png](figures/gradient_clipping.png) — 600 dpi，6000×2400。
- [figures/generalization_gap.png](figures/generalization_gap.png) — 600 dpi，4200×2400。
- [figures/monthly_core_loss.png](figures/monthly_core_loss.png) — 600 dpi，4200×2400。
- [figures/monthly_AUROC_AP.png](figures/monthly_AUROC_AP.png) — 600 dpi，4200×2400。
- [figures/monthly_brier.png](figures/monthly_brier.png) — 600 dpi，4200×2400。
- [figures/monthly_conditional_pinball.png](figures/monthly_conditional_pinball.png) — 600 dpi，4200×2400。
- [figures/reliability_diagram.png](figures/reliability_diagram.png) — 600 dpi，5400×2400。
- [figures/probability_distributions.png](figures/probability_distributions.png) — 600 dpi，4200×2400。
- [figures/quantile_coverage.png](figures/quantile_coverage.png) — 600 dpi，3900×2700。
- [figures/quantile_coverage_error.png](figures/quantile_coverage_error.png) — 600 dpi，3900×2700。
- [figures/quantile_pinball.png](figures/quantile_pinball.png) — 600 dpi，3900×2700。
- [figures/spatial_rain_frequency.png](figures/spatial_rain_frequency.png) — 300 dpi，1800×1500。
- [figures/spatial_mean_probability.png](figures/spatial_mean_probability.png) — 300 dpi，1800×1500。
- [figures/spatial_brier.png](figures/spatial_brier.png) — 300 dpi，1800×1500。
- [figures/spatial_conditional_pinball.png](figures/spatial_conditional_pinball.png) — 300 dpi，1800×1500。
- [figures/spatial_DIAGNOSTIC_PROXY_bias_mm_h.png](figures/spatial_DIAGNOSTIC_PROXY_bias_mm_h.png) — 300 dpi，1800×1500。
- [figures/spatial_DIAGNOSTIC_PROXY_MAE_mm_h.png](figures/spatial_DIAGNOSTIC_PROXY_MAE_mm_h.png) — 300 dpi，1800×1500。
- [figures/spatial_valid_count.png](figures/spatial_valid_count.png) — 300 dpi，1800×1500。
- [figures/spatial_rainy_count.png](figures/spatial_rainy_count.png) — 300 dpi，1800×1500。
- [figures/rainrate_diagnostics.png](figures/rainrate_diagnostics.png) — 600 dpi，6600×2400。

所有图件均据真实 history 或本轮 full aggregates；曲线 600 dpi，空间 300 dpi，labels/units/坐标和 mask 逐图检查通过。
报告、CSV/JSON、spatial_cell_metrics.nc、manifest、test logs 和 artifact hash index 构成独立完整审阅证据。
spatial artifact 为小型汇总，不含 scene-level raw/prediction cube；exact axes/hash 保留。

`B0_PHASE_A_ACCEPTED=UNDECIDED`；`ACCEPT_B0_PHASE_A=UNDECIDED`；`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`；`PHASE_B_AUTHORIZED=false`。
审阅完成不替研究者接受实验、不迁移预算、不启动 Phase-B，完成后停止。
