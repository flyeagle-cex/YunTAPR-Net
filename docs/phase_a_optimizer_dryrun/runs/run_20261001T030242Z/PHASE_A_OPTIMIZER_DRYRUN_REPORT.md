# PHASE_A_OPTIMIZER_DRYRUN_REPORT

结果：**PROTOCOL_ENGINEERING_VALIDATED = true**。Phase-A protocol 仍为 v1.0；本轮仅数值实现修正与 ENGINEERING_ONLY dry-run，正式训练未启动、未授权。

Run `run_20261001T030242Z`；baseline `8d5d15f6df85649cefedd264301d70ee2ba89c7e`。

## 科学合同与唯一已有源码修正

研究者批准的唯一 scheduler 修正为 warmup 求值顺序 `(base_lr*u)/W` → `base_lr*(u/W)`。Cosine 部分未变，无 clamp/min/max/round/Decimal/isclose 或 tolerance 代替 exact LR 判据。所有 alpha/gamma、AdamW、weight decay、LR、batch、AMP、warmup/horizon、epoch/early-stop、seed、checkpoint metric 和 D1–D8 保持不变。

`previous_run=STOPPED_SCHEDULER_BOUNDARY_FAILURE`；`current_correction=WARMUP_EVALUATION_ORDER_ONLY`；`scientific_parameters_changed=false`；`protocol_version_changed=false`。旧 run_20261001T023702Z 和其全部产物未改写。除 scheduler 这一行外，1338 个基线文件逐一 Git blob / disk SHA 核验保持不变。

Protocol YAML SHA256 `dcacbe34050da7e777ad0cb72c53b5b51b48ce57eb9260b09fd283d96de12a4a`。文档 SHA256 `3480baca7e7dd1839a534660fef5e7a41a9e013107954cdef44574e110631e2c`。没有修改任何冻结文档或 YAML；完整继承来源/版本/hash见 protocol_identity.json。

## Exact scheduler gate

原16项 preliminary tests 原样实际执行，16/16 PASS。完整检查5860个warmup点和287140个cosine点：warmup严格递增且0<LR<=base，cosine单调非增且min<=LR<=base；只做数学检查，没有执行293000次模型更新。

| Update | LR | Float hex |
|---:|---:|---|
| 1 | 1.7064846416382254e-08 | `0x1.252bfcfd90a6fp-26` |
| 5860 | 0.0001 | `0x1.a36e2eb1c432dp-14` |
| 5861 | 9.99999999970373e-05 | `0x1.a36e2eb18ed3cp-14` |
| 293000 | 1e-06 | `0x1.0c6f7a0b5ed8dp-20` |

Phase-B仅验证同epoch进度的函数等式；epoch=1,2,10,25,49,50、steps/epoch=8000与Phase-A5860的LR及hex全部精确相等，absolute error=0。保持50-epoch horizon，未运行Phase B、未计算新normalization。详见 scheduler_finalfit_replay.json。

## 六个真实样本与读取链

完整11720行Train manifest仅用于固定身份索引；按[0,2343,4687,7031,9375,11719]等间隔选6个2023 eligible样本，读取前登记，未按雨量/模型结果筛选。3组batch2。原始B13/IMERG经英文staging、正式QC、pinned Phase-A normalization、tensor/CUDA/B0/SP04/heads进入 loss/backward/clipping/AdamW。2025像元读取数为0。

worker=2，各自独立ASCII root，prefetch=1、pin_memory=false、persistent_workers=false；one_file_at_a_time、700MiB cap，12次B13/IMERG读取均核验既有source SHA与copy SHA、size和cleanup。读取wall=4.401s；临时staging副本剩余0。H永久只读。六个正式reader结果仅在RAM中只读重放，无永久数据cache。固定fixture顺序不是正式epoch shuffle实现。时间与归一化身份、读写额外I/O逐样本记录于 real_sample_read_audit.json。

Model trainable=4,329,361；Conv2d kernels DECAY=4,322,832、bias/GN NO_DECAY=6,529，互斥且完整。参数名及exact heads详见 parameter_groups.json。

## 实际 optimizer 与数值精度

A/B完全fresh seed2026各3步；C完全fresh2步，保存专属临时checkpoint、销毁model/optimizer、重建并恢复后第3步。总共恰好9次ENGINEERING_ONLY optimizer.step，无额外seed、无完整epoch拟合。AdamW betas(.9,.999)、eps1e-8、decay1e-4仅Conv kernel，foreach/fused及其他冻结布尔参数为false。

每步参数/raw quantile=float32，BF16 autocast开启，qlog/qphysical/pinball=float64；loss、grad、post-step parameters/optimizer state全部finite，qlog及physical quantile严格单调，crossing=0。GradScaler未使用。

| Run A update | LR | Core loss | Pre-clip norm | Post-clip norm | Clipped |
|---:|---:|---:|---:|---:|---|
| 1 | 1.7064846416382254e-08 | 0.113872000394273 | 5.28128242 | 4.99999905 | True |
| 2 | 3.412969283276451e-08 | 0.530168591174423 | 6.47863436 | 4.99999952 | True |
| 3 | 5.119453924914676e-08 | 1.21951402230372 | 12.3380165 | 5 | True |

顺序为backward→独立pre norm→clip_grad_norm_(max_norm=5,error_if_nonfinite=true)→记录→AdamW.step。clip函数返回norm与独立pre norm exact一致；post-clip解释保留PyTorch的5/(pre+1e-6)比例与float32舍入，不加GradScaler。各步LR在step前设置，两个optimizer组均与stateless函数精确一致。

## Optimizer VRAM gate

Dedicated VRAM=8150.5625 MiB。9步最大peak reserved=3292.0 MiB；最小保守设备空闲=3630.000 MiB（44.537%）。全部通过20% dedicated engineering headroom，不改batch。每步同时记录allocated/reserved/device-free及峰值；A/B/C step1记录AdamW moment首次初始化。

采用两项共同判据：peak reservation<=80% dedicated，以及min(post-device-free, pre-device-free−incremental-peak-reservation)>=20% dedicated。设备空闲含其他应用，峰值空闲为保守估计，不冒称持续采样的瞬时最小值。记录的allocator与CUDA mem_get_info数据来自实际9步，包含本次活跃桌面负载；该短dry-run不是完整epoch热稳定性证据。

| Run | Update | Peak allocated MiB | Peak reserved MiB | Post device free MiB | Estimated min free MiB | Optimizer CUDA state MiB |
|---|---:|---:|---:|---:|---:|---:|
| A | 1 | 2703.33 | 3254.00 | 3668.00 | 3668.00 | 33.0304 |
| A | 2 | 2735.43 | 3260.00 | 3662.00 | 3662.00 | 33.0304 |
| A | 3 | 2735.43 | 3260.00 | 3662.00 | 3662.00 | 33.0304 |
| B | 1 | 2703.33 | 3254.00 | 3668.00 | 3668.00 | 33.0304 |
| B | 2 | 2735.43 | 3260.00 | 3662.00 | 3662.00 | 33.0304 |
| B | 3 | 2735.43 | 3260.00 | 3662.00 | 3662.00 | 33.0304 |
| C | 1 | 2703.33 | 3254.00 | 3668.00 | 3668.00 | 33.0304 |
| C | 2 | 2735.43 | 3260.00 | 3662.00 | 3662.00 | 33.0304 |
| C | 3 | 2737.38 | 3292.00 | 3630.00 | 3630.00 | 33.0304 |

## Bit-exact replay 与 temporary resume

Run A/B每步loss、LR、pre-clip norm、clipping action exact相同。initial/final model（含buffers）、optimizer logical state和全部Python/NumPy/torch CPU/CUDA RNG摘要也相同。A/B final model SHA256=`0e22354fd53dc7254511d880c62144e8674d49061cb8f41993914b2bc939b153`。未使用tolerance冒充bit-exact。

Run C第二步临时checkpoint SHA256=`58e0c60d7dfe92800684ff3172c4e59020b7fafb3585b284710ff939b4dcdaf4`，bytes=52,066,875。completed_epoch=0、global_update=2，是原协议明确允许的临时schema例外，不是正式epoch checkpoint。完整required schema检查通过，旧model/optimizer weakref确认已销毁；恢复model、optimizer、RNG、global_update及全部provenance后step3与A exact一致，包括optimizer和RNG logical state。临时checkpoint、三份篡改copy及自有空目录均已删除。

protocol、normalization、scientific contract SHA三种序列化篡改均被实际loader拒绝，错误包含具体字段；mock调用计数确认model.load_state_dict、optimizer.load_state_dict、restore_rng均为0，并交叉核验拒绝前后state/RNG摘要不变。冻结artifact没有被篡改。

## 全部测试与保留的工程错误历史

完整套件本轮实际执行162项：137项历史+17项protocol+8项新real-evidence测试，全部PASS，skipped=0。原scheduler exact断言未改变；新增测试交叉检查实际步数/参数组、显存state、dtype/clip、replay/resume、serialized provenance与staging。没有用旧历史PASS替代本轮执行，测试没有新增optimizer更新。

另外保留两次新harness错误供追溯：run_20261001T025132Z 在首个forward后、backward前因审计脚本额外要求terminal backbone dtype=BF16而中止，optimizer更新0次；此要求不在冻结协议中。按实际参数/raw quantile/quantile/pinball与autocast要求修复新harness，末端activation float32继续如实记录。AMP是逐算子混合精度，见[PyTorch2.11 AMP](https://docs.pytorch.org/docs/2.11/amp.html)。未改变模型或AMP参数。该尝试的所有文件和脚本快照已seal，未覆盖。

本run的 tests_initial 保留第一次完整测试启动日志：137+17先通过，新8项因class路径属性覆盖TestCase.run未启动；只改新测试属性名后重跑完整162项全部通过，未改任何断言或GPU结果。完整初次日志、异常和source快照均保留。

## 环境、复现与发布边界

Python `F:\pytorch\Research\.venv-cuda\Scripts\python.exe`；torch=2.11.0+cu128，CUDA runtime=12.8，GPU=NVIDIA GeForce RTX 5060 Laptop GPU，driver=573.24。完整包版本与process flags见 environment.json。CPU reference venv和其他包未升级。

启动前设置PYTHONHASHSEED=2026、CUBLAS_WORKSPACE_CONFIG=:4096:8；seed package启用strict deterministic算法、cudnn deterministic，禁benchmark/TF32，float32 matmul precision=highest。全部实际GPU操作支持这些设置，没有warn-only/fallback。

复现说明见README.md；使用新的run目录依次initialize→preliminary→gpu→tests→finalize。完整原始来源与pinned本地mask需要可读；只发布源码、测试和文本证据，不提交checkpoint、optimizer binary、raw data、wheel、venv或cache。每phase调用hash和实际GPU源码快照记录调用身份，manifest记录最终提交源码及所有新产物SHA。

## 最终状态

```json
{
  "run_status": "PROTOCOL_ENGINEERING_VALIDATED",
  "SCHEDULER_BOUNDARY_PASS": true,
  "SCHEDULER_FINALFIT_REPLAY_PASS": true,
  "DRYRUN_OPTIMIZER_STEP_PASS": true,
  "DRYRUN_MEMORY_SAFE": true,
  "PRECISION_GATE_PASS": true,
  "DETERMINISTIC_REPLAY_PASS": true,
  "RESUME_REPLAY_EXACT_PASS": true,
  "CHECKPOINT_PROVENANCE_GUARD_PASS": true,
  "FULL_TEST_SUITE_PASS": true,
  "PROTOCOL_ENGINEERING_VALIDATED": true,
  "PHASE_A_TRAINING_PROTOCOL_VERSION": "v1.0",
  "PHASE_A_TRAINING_PROTOCOL_FROZEN": true,
  "HEAD_IMPLEMENTATION_DETAIL_PINNED": true,
  "FOCAL_ALPHA": 0.5,
  "FOCAL_GAMMA": 2.0,
  "OPTIMIZER": "AdamW",
  "BASE_LR": 0.0001,
  "WEIGHT_DECAY": 0.0001,
  "TRAIN_PHYSICAL_BATCH": 2,
  "GRADIENT_ACCUMULATION": 1,
  "EFFECTIVE_BATCH": 2,
  "AMP_MODE": "BF16",
  "VALIDATION_BATCH": 8,
  "NUM_WORKERS": 2,
  "MAX_EPOCHS": 50,
  "WARMUP_EPOCHS": 1,
  "MIN_LR": 1e-06,
  "EARLY_STOP_PATIENCE": 8,
  "EARLY_STOP_MIN_DELTA": 0.0001,
  "GRAD_CLIP_NORM": 5.0,
  "PRIMARY_SEED": 2026,
  "CHECKPOINT_METRIC": "global_val_core_loss",
  "B0_FORMAL_TRAINING_STARTED": false,
  "FORMAL_TRAINING_AUTHORIZED": false,
  "previous_run": "STOPPED_SCHEDULER_BOUNDARY_FAILURE",
  "current_correction": "WARMUP_EVALUATION_ORDER_ONLY",
  "scientific_parameters_changed": false,
  "protocol_version_changed": false,
  "actual_optimizer_steps": 9,
  "real_unique_2023_samples": 6,
  "2025_pixels_read": false,
  "Phase_B_executed": false,
  "Phase_B_normalization_computed": false,
  "formal_checkpoints_created": 0,
  "temporary_checkpoint_files_remaining": 0,
  "owned_staging_copies_remaining": 0,
  "full_test_count": 162,
  "skipped_test_count": 0,
  "retained_zero_update_harness_attempt": "docs/phase_a_optimizer_dryrun/runs/run_20261001T025132Z",
  "retained_initial_test_runner_attempt": "tests_initial",
  "execution_scope": "ENGINEERING_ONLY"
}
```

Protocol工程链验证完成不等于科研收敛、完整Validation或正式训练结果。本轮按授权发布至GitHub main后停止，B0_FORMAL_TRAINING_STARTED=false、FORMAL_TRAINING_AUTHORIZED=false。
