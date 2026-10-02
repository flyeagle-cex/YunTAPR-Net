# B0 Phase-A acceptance + Phase-B FinalFit preparation closure v1

研究者已接受 B0 Phase-A 作为 **CONTROL / BASELINE**，不是最终 YunTAPR-Net。本 run 只完成 preparation，`PHASE_B_AUTHORIZED=false`，`PHASE_B_FORMAL_TRAINING_STARTED=false`。真实工程 dry-run 的两个临时更新不属于正式训练；完成后停止。

## 1. 权威与历史身份

Baseline/Scientific Review commit：`5050b6cc77ab75eacb96e1494a165d61142227f4`；Scientific Review run：`run_20261002T005448_798068Z`；本 run：`run_20261002T014649_144967Z`。
独立 acceptance 文件为 `docs/researcher_decisions/B0_PHASE_A_ACCEPTANCE_v1.md` 和 `config/decisions/b0_phase_a_acceptance_v1.yaml`。
`ACCEPT_B0_PHASE_A=true`，`B0_PHASE_A_ACCEPTED=true`；选定 epoch=11、Val core=0.04730775889882134。
BEST SHA256：`3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3`；大小=52062315 bytes。仅只读 identity hash，没有 torch.load 或 state 应用。
Protocol、Scientific Freeze、Phase-A normalization、Train/Validation manifests、SP04、Yunnan mask 的路径和 SHA 均绑定在 acceptance YAML，preparation manifest 和 historical preservation 中。
本轮再次检查全部 1586 个 baseline 文件，完整 review、早前 H 阻塞 run、输出路径失败 run、正式 training run 和冻结 artifacts 全部保持原始 bytes。历史 review 的 UNDECIDED 状态保留；本独立研究者决定更新当前执行状态。

## 2. FinalFit population 与排序

独立 `phase_b_finalfit_manifest.csv` 含 23,447 个唯一身份：2023 March–October eligible Train=11,720，2024 March–October eligible Validation=11,727；2025=0。
清单来源是两份已冻结 manifest 与已冻结 formal source SHA ledger/eligibility/pairing。逐项比对路径、source role、时间、full-valid eligibility、bytes/SHA、IMERG V07 Final product 与 index；没有重新筛样本、partial/rejected scene、older fallback 或其它月份/product。
固定排序：UTC window_start 升序，再 sample_id、source_role；finalfit_index 从0开始。原 Train/Validation role 与原 index 单独保留，并统一标记当前 role=FinalFit。2024 此阶段成为训练 population，不再被视作独立的 FinalFit Validation 控制信号。
清单 SHA256：`00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff`。

## 3. 全量 FinalFit normalization

真正重读全部 23,447 原始 B13 文件：每场 501×501 full-valid native pixels，总计 **5,885,220,447**，与精确期望相等。
每文件经只读原始 H source → bounded English staging → size/source+copy SHA → 坐标/因果时间/full-valid QC → native pixel decode；不翻转、不插值、不重采样、不将缺测记0。
完整 int16 packed-code histogram 使用 runtime 相同 float32 scale/add_offset 解码后提升 float64；population mean/std，ddof=0；quantiles 为完整群体的 type-7/linear rank interpolation，无抽样、无 rounding/rebinning。
独立 merged per-frame float64 central moments 与 histogram mean/std 的差值分别为 3.41060513164848e-13 K、2.8421709430404e-14 K，均小于1e-9 K。Phase-A 常数未复用。

| Statistic | Kelvin |
|---|---|
| mean_K | 270.590048658646 |
| std_K | 20.3685838740673 |
| min_K | 177.119995117188 |
| p1_K | 209.559997558594 |
| q1_K | 260.630004882812 |
| median_K | 275.399993896484 |
| q3_K | 285.880004882812 |
| p99_K | 300.029998779297 |
| max_K | 330.970001220703 |
| IQR_K | 25.25 |

Normalization artifact：`normalization_phaseB_finalfit_2023_2024.json`，SHA256=`c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327`。
完整逐场 read ledger 和 packed-code histogram 保存在该 run 的 F private directory；公开 `normalization_execution.json` 记录其 absolute path/bytes/SHA。实际读取2023/2024像元，2025_PIXELS_READ=0。
同时验证 490 个所需 IMERG daily 文件的冻结 SHA 与正/稳定 size；norm fit 仅使用 native B13，不使用任何 target statistics。

## 4. Fresh initialization、尾批与预算

`PHASE_B_MODEL_INITIALIZATION=FRESH_SEED_2026`。两次独立 fresh B0Model 初始化逻辑状态 SHA 一致：`57a4d103a31aa7be1a52af079cdf7fb81bc73c51ba3e0e97d395513d21d9023d`。torch.load 被禁止，实际调用0；没有应用 epoch_011、Phase-A optimizer 或 scheduler state。
保持冻结 backbone/head/loss/AdamW参数组/BF16/FP64 quantiles/clip5 与 seed，未修改 alpha/gamma/LR 或 science/protocol artifacts。
`FINALFIT_EPOCHS=11`；early stopping=false，validation-triggered scheduler=false，不根据2025或后续表现重新选epoch。
physical batch=2、drop_last=false；前11,723批各2场，最后singleton1场：11,723×2+1=23,447。尾批不丢弃、不复制、不padding、不replacement，实际有效batch为1、accumulation=1。
全11个计划epoch均验证各身份恰好出现一次；epoch0用独立 torch.Generator seed2026，后续seed=2026+zero_based_epoch_index。epoch1 permutation 和真实dry-run选样在读取前登记。
tail loss沿用 actual batch 中全部 valid Yunnan supervised pixels 的分母，绝不固定除以2；quantile轴仍32分位均值。

## 5. Scheduler 数值推导与精确 replay

steps_per_epoch=ceil(23,447/2)=11,724，W=11,724，U=50×11,724=586,200。
base_lr=1e-4、min_lr=1e-6；1 epoch warmup + 50 epoch cosine horizon；计划实际11 epoch，总更新128,964。
warmup lr(u)=base_lr×(u/W)，随后 min_lr+(base_lr−min_lr)×(1+cos(pi×(u−W)/(U−W)))/2；在step前设置，update一基。
warmup允许低于min_lr，cosine阶段才要求min_lr下界。首步=8.5295121119071997e-09，W=0.0001，U=9.9999999999999995e-07，计划最后update=9.0169974282463853e-05。
检查全部586,200个LR数值、warmup严格递增/cosine非递增和边界范围。A/B在200个共同quarter-epoch进度点（覆盖50-epoch horizon）float.hex完全一致，包含1/11/50 epoch端点；不是把cosine压缩成11 epoch，也没有用A的W=5860。
本数值sweep optimizer steps=0；不是正式训练。

## 6. 独立真实 ENGINEERING_ONLY dry-run

选样规则先登记：seed2026 epoch1 permutation 的首个batch2和最后singleton，三种身份没有按照降水或模型误差挑选。
用新的 PhaseBNormalizer 读取真实 H B13 + IMERG V07 Final；逐样本 source SHA、时间因果、full-valid、frozen supervised/rainy counts 均通过。
临时fresh seed2026 model和临时fresh AdamW完成各batch的forward/loss/backward/clip/step。参考loss按独立逐像元公式核验 actual valid-pixel denominator，occ tolerance1e-7、FP64 quantile tolerance1e-12。

| Batch size | Valid denominator | Core loss | LR | Preclip norm | Postclip norm |
|---|---|---|---|---|---|
| 2 | 6860 | 1.11693521637 | 8.52951211191e-09 | 9.34409999847 | 5 |
| 1 | 3430 | 0.217225478507 | 1.70590242238e-08 | 3.15972566605 | 3.15972590446 |

ENGINEERING_OPTIMIZER_STEPS=2、ENGINEERING_BACKWARD_CALLS=2；FORMAL_OPTIMIZER_STEPS=0。所有checkpoints load calls=0，不产生checkpoint binary。
temporary model/optimizer 已释放，owned staging已清理。详细dtype、数值、source audit和GPU memory见engineering_dryrun.json。没有正式11 epoch loop或新的模型交付。

## 7. Tests 与清理

最终实际执行 210 项：existing=171，scientific-review=19，new preparation=20；failures/errors/skips均0。
测试fixture独立临时目录，temporary optimizer/backward/step仅TEST_FIXTURE_ONLY。原始数据与正式checkpoint tensors禁止作为fixture；artifact阶段仅允许BEST只读SHA。临时目录清理成功，正式BEST与所有baseline artifacts前后不变。测试不计入两个real engineering steps，更不计入formal steps。

| Suite | Executed | Failures | Errors | Skips |
|---|---|---|---|---|
| scientific_freeze | 42 | 0 | 0 | 0 |
| b0_skeleton | 20 | 0 | 0 | 0 |
| development_qc | 8 | 0 | 0 | 0 |
| scientific_freeze_v1_1 | 30 | 0 | 0 | 0 |
| quantile_numerical_closure | 14 | 0 | 0 | 0 |
| training_environment_audit | 6 | 0 | 0 | 0 |
| gpu_training_feasibility | 6 | 0 | 0 | 0 |
| phase_a_protocol_prefreeze | 11 | 0 | 0 | 0 |
| phase_a_protocol_v1 | 17 | 0 | 0 | 0 |
| phase_a_optimizer_resume | 8 | 0 | 0 | 0 |
| formal_phase_a | 9 | 0 | 0 | 0 |
| scientific_review_units | 8 | 0 | 0 | 0 |
| scientific_review_full_artifacts | 11 | 0 | 0 | 0 |
| phase_b_preparation_units | 12 | 0 | 0 | 0 |
| phase_b_preparation_artifacts | 8 | 0 | 0 | 0 |

前置开发中12项测试的scheduler测试循环范围曾越过50 epoch；随后修正测试范围并全部通过，冻结scheduler未改。init的Path参数适配错误也在写入acceptance/run前修正，未改任何历史文件。此类调试与最终suite结果分开记录在implementation_gate_notes.json。

## 8. Staging I/O 与发布边界

normalization wall=1064.823s；copy workload sum=323.008s；read/QC/statistics context sum=496.741s；peak单文件temporary bytes=6387344。
本fit单进程、一次一个H文件，cap=734,003,200 bytes；source/copy SHA额外I/O不包含在copy计时，read计时包含QC与本场statistics。每文件size/SHA一致后仅删除本流程创建的UUID staging copy；H原始文件永久只读，既有diagnostic cache不删除。
不安装或升级环境包；运行python、torch、CUDA、GPU和包版本写在environment.json。
Git仅发布代码、测试、CSV/JSON/YAML、acceptance和report；不上传model/optimizer binary、raw、cache、venv或wheel。read ledger/histogram/permutation在F盘，仅公开identity。

## 9. 限制保留与最终授权

B0仍是single latest causal B13 control；没有multitemporal/multichannel/GFS/DEM/DOTE/DTFM/MEE/ERA5 teacher。接受B0不证明完整YunTAPR-Net，不排除已观察到的Validation degradation、低tau calibration deviation、月度/空间差异和强雨样本稀疏。设计信息限制不作为已证实物理误差原因。
Phase-A limitation inventory和Scientific Review全部原样保留，接受不会事后改BEST metric或science artifacts。
`B0_PHASE_A_ACCEPTED=true`；`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=11`；`PHASE_B_NORMALIZATION_READY=true`。
`PHASE_B_AUTHORIZED=false`；`PHASE_B_FORMAL_TRAINING_STARTED=false`；2025_PIXELS_READ=0。正式FinalFit仍需独立研究者授权，完成本轮后STOP。
