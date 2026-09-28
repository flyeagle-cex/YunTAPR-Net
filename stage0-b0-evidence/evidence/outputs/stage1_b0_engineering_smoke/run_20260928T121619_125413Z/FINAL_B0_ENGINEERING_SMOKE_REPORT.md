# Final B0 Engineering Smoke Report

**B0 ENGINEERING SMOKE: PASS**。**B0 FORMAL EXPERIMENT: NOT_READY / HOLD**。

独立 run：`F:\pytorch\Research\outputs\stage1_b0_engineering_smoke\run_20260928T121619_125413Z`。本轮是 offline engineering smoke，真实数据闭环已执行；没有科研实验许可升级。

## 1. Engineering status

PASS：真实文件 → B13 / IMERG reader → 候选时间配对 → 显式空间接口 → Tensor → B0SmokeDataset → DataLoader → small U-Net → forward → masked MSE → backward → optimizer → checkpoint save/reload → inference → diagnostic metric 全部真实执行。

## 2. Sample count

16 个真实样本。按已有 2024-07 P0 审计时间表选择首 16 个 exact nominal 候选，不按雨量挑选，不扫描全库。未以虚构数据替代主 smoke。

## 3. Sample date range

IMERG converted coordinate：2024-07-01T00:00:00Z 至 2024-07-01T07:30:00Z；candidate analysis_time 从 2024-07-01T00:30:00+00:00 至 2024-07-01T08:00:00+00:00。不是 native half-hour window 宣告。

## 4. Real Himawari files

16 个文件；首 `H:\葵花202303_202510\202407\01\NC_H09_20240701_0020_R21_FLDK.06001_06001.nc`，末 `H:\葵花202303_202510\202407\01\NC_H09_20240701_0750_R21_FLDK.06001_06001.nc`。逐条路径、时间和因果检查见 B0_SMOKE/smoke_sample_manifest.csv 与 JSON；17 个 raw 的原始 SHA 在 logs/raw_inputs_before.json。推理对前 4 个真实源重新读取。

## 5. Real IMERG files

1 个 daily file：`F:\云南极端降水数据\raw\IMERG\2024\imerg_20240701.nc`，使用相应 16 个真实 converted coordinate 的 precipitation 切片；目标 units=mm hr-1，0 rain 有效。未读取 QI 作为 predictor。

## 6. B13 variable mapping

`tbb_13`；packed int16 → float32 K；shape 501×501；missing_value=-32768，无单独 _FillValue。复用原 Stage-0 decode_packed/_time 函数体，单变量封装；没有读七通道 tensor。详见 himawari_b13_reader_report.md、reader_actual_metadata.json、reader_reuse.json。

## 7. Time pairing

研究者本轮明确批准 ENGINEERING_SMOKE_TIME_MAPPING_ONLY：T 为 converted CF coordinate，analysis_time=T+30min，nominal=analysis_time−10min。每个实际文件重读 obs_start/obs_end/date_created，强制 obs_end<=analysis_time；本 16 个均通过。future 样本拒绝测试也已执行。date_created 仅记录，不作为 operational availability。native exact window 和正式跨源绑定未冻结。

The cross-source IMERG-Himawari time binding used in this
B0 smoke run is provisional and was used only to test the
engineering pipeline. It is not a frozen scientific sample
timing convention.

## 8. Spatial smoke alignment

PROVISIONAL_SMOKE_ALIGNMENT：以真实 IMERG lat[44:76]/lon[54:86] 组成 32×32 crop，源 B13 按坐标最近点索引 gather。范围 lat=[23.44999885559082, 26.549999237060547]，lon=[100.44999694824219, 103.54999542236328]。明确 descending source → ascending target 的索引顺序；无 silent flip、插值、填补、域外外推或科学方法冻结。仅 ENGINEERING_SMOKE_CROP_ONLY，不是 model_input_bbox。

## 9. Tensor contract

item x/y=[1,32,32]；batch=[B,1,32,32]；float32；mask 相同 shape / bool。x 为 K，y 为 mm hr-1。显式添加 channel/batch，不无记录 squeeze。实际输入 crop 全有效；原缺测仍为 NaN+mask；模型不静默填零。

## 10. Dataset

B0SmokeDataset PASS，只服务本轮。__getitem__ 实际读 B13/IMERG，重验坐标、时间与因果，再做 smoke gather。缓存仅保存 16 个小 crop tensor；未构建 FormalTrainingDataset、全量 index 或科研样本库。

## 11. DataLoader

batch_size=1 与 4 均 PASS；shuffle=False、num_workers=0。Windows 未启用 multiprocessing。metadata 保留为逐样本 list；合约与加载秒数见 dataloader_check.json。

## 12. Model

ENGINEERING_SMOKE_MODEL：两级 encoder、bridge、skip connections 与 ConvTranspose decoder；width=8，输入单 B13 单时次，输出单 precipitation field（Softplus 非负）。没有 EfficientNet、quantile/probability heads；不宣称等价于完整 GPROF-IR 科学实现。不是正式 architecture freeze。

## 13. Parameter count

29321 个可训练参数；完整模块结构见 model_summary.txt。

## 14. Loss

masked MSE，只对 target_valid_mask=True 的原单位目标计算；invalid 像元先索引排除，0 rain 保留。target 无变换。模型内部固定 x/300 仅 smoke 数值 conditioning，不是数据拟合的 mean/std 或正式 normalization。

## 15. Updates

单 seed=42、1 epoch、4 optimizer steps，Adam lr=1e-3（ENGINEERING_SMOKE_ONLY）。没有 early stopping、调参、多 seed、正式训练/验证/测试。

## 16. Loss finite

4/4 步 loss finite。原值见 step_log.csv，仅用于工程数值检查，不讨论收敛或模型优劣。

## 17. Gradient

每步所有可训练参数 grad 非 None 且 finite；存在非零梯度。gradient_update_check.json 保存逐步证据。

## 18. Optimizer update

每步至少一个参数 tensor 在 optimizer.step 后实际变化；不是只调用 API 后推断成功。更新数量逐步保存。

## 19. Checkpoint

真实保存 `F:\pytorch\Research\outputs\stage1_b0_engineering_smoke\run_20260928T121619_125413Z\B0_SMOKE\checkpoints\b0_smoke_only.pt`，含 model_state_dict、optimizer_state_dict、step、config、sample contract version。新建 model instance 后 weights-only reload；同输入最大绝对差 0.0，检查 rtol=1e-05 / atol=1e-06 通过；optimizer state 也重载。**SMOKE CHECKPOINT / NOT SCIENTIFIC CHECKPOINT**。

## 20. Inference

reload 后对 4 个真实样本重新读取原文件、配对并推理，输出 [4,1,32,32]、finite、无崩溃。数值保存 inference_outputs.npz；没有生成科研预测产品。

## 21. Diagnostic MAE / RMSE

MAE=0.934484422 mm hr-1；RMSE=1.446439624 mm hr-1。**ENGINEERING_DIAGNOSTIC_ONLY / IN_SAMPLE**，4096 个有效 crop 像元，含 922 个真实 0 rain 像元。来自参与过 smoke update 的 4 个样本，没有 held-out 或整省评价含义，禁止论文引用或模型优劣结论。未做 occurrence threshold、CRPS 或概率指标。

## 22. Device

cpu；torch 2.14.0+cpu；CUDA_available=False。CPU Intel64 Family 6 Model 198 Stepping 2, GenuineIntel。无 CUDA 时按任务继续 CPU smoke。

## 23. Memory / timing

首 batch_size=1 load=0.040302s；batch_size=4 load=0.093752s（部分小 tensor 已在本轮 cache）。平均 forward=0.002950s、backward=0.004168s。GPU peak=NOT_APPLICABLE_CPU。这是 SMOKE PERFORMANCE DIAGNOSTIC，不是正式 benchmark。固定 random/NumPy/PyTorch seed；deterministic enabled、warn_only=True、CPU threads=2；不声称 CUDA bitwise 保证。

## 24. Pytest

先通过 19 个独立单元测试再读真实数据执行；最终 47 passed，failures/errors/skipped 全 0。覆盖用户列出的 30 类 reader、mask、causality、tensor、batch、forward/backward、update、checkpoint、inference、raw/Stage-0 保护与禁用输入要求。真实 stdout/XML 在 tests/pytest_final_output.txt、tests/pytest_final.xml。单位测试使用 synthetic fixture，主端到端只用上述真实文件。

归档复现入口另修正 vendor 快照重复复制并排除历史临时 fixture；最终 pytest 显式限定两个测试模块，新增实际临时目录回归测试；此前 46 项通过记录保留。最终 47 项通过；未重跑训练、未改数据/科学规则。详见 logs/reproduction_entry_fix.json。

## 25. Dependencies

始终 `F:\pytorch\Research\.venv\Scripts\python.exe`。没有安装/升级依赖，全部 distribution 版本前后快照相同。numpy=2.5.3、netCDF4=1.7.4、pyarrow=25.0.1。教学模型因多通道/概率头/导入即运行而未导入。

## 26. Raw integrity / frozen conventions

全部 17 个选定 raw 文件与 24 个登记 Stage-0 输入 size/mtime/SHA256 在测试后仍相同；原件/旧 run 写操作 0。冻结 registry、正式主 mask 和 comparison 保持原 hash。不声称全库所有文件都新做了哈希验证。

## 27. Cache

本轮新 run 内 cache/staging，单文件上限 16777216 bytes。实际 40 次 copy，累计 136492902 bytes，峰值单副本 5910378 bytes；每次 size/hash 一致，copy累计=0.109722s、read累计=0.252222s。cleanup failures=0，剩余副本=0。仅清理自身登记的临时副本；未删旧 diagnostic cache。累计 I/O 不是永久库复制量；SHA/启动/完整性耗时不在 copy/read 区间内。

## 28. Scientific limitations

时间绑定 provisional，native half-hour 语义未定；空间 crop/nearest gather/输入 conditioning/architecture/loss/lr 全是 smoke。没有 operational replay、正式 normalization、split、科研训练、多 seed、2025 评价、论文图表或科学结论。云南正式行政 mask 仍冻结，但本次小 crop metric 不是全省正式主评价。

## 29. Formal experiment blockers

Stage-0 Final Gate 中 10 项正式入口依赖原样保留，详见 B0_FORMAL_EXPERIMENT_HOLD.md：2025-10 缺月、native timing/正式 analysis binding、bbox/context、精确 Train/Val、missing/QC、正式归一化来源、availability 声明、正式概率实验协议、其余月份工程证据。本轮临时候选批准不等于这些科学项已解决；GFS/DEM 的未来阶段事项不成为 smoke 输入。

## 30. Gate conclusion

B0 ENGINEERING SMOKE PASS，B0 FORMAL EXPERIMENT NOT_READY。完成本次安全工程任务后停止，不自动进入正式 B0、B1 或任何下一 Stage。

B0 engineering smoke run complete.
Real-data Dataset-to-inference pipeline was tested.
No formal B0 scientific experiment was started.
No formal Train/Validation/Test split was executed.
No scientific result is claimed from this smoke run.
All Stage-0 frozen conventions remain unchanged.
