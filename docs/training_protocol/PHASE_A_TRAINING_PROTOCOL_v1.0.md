# PHASE_A_TRAINING_PROTOCOL_v1.0

状态：RESEARCHER_APPROVED_PROTOCOL。训练协议已由研究者批准；正式训练授权仍为 false。本发布只执行独立 ENGINEERING_ONLY optimizer / determinism / temporary-resume dry-run。

Scientific Freeze v1.1、engineering v4、D1–D8、既有模型和所有历史证据保持不变。本协议作为独立 overlay 提供已批准的 focal 和训练参数；旧合同中的 null 不被静默改写。所有继承对象的来源和 SHA 在以下完整机器配置中固定。

Occurrence 为直接 Conv2d(48,1,1,bias=true)，quantile 为直接 Conv2d(48,32,1,bias=true)，都没有 hidden layer。已有 sigmoid、softplus/float64 顺序单调累计、expm1 是保留的概率语义变换。核心 loss 为 L_occ+L_qr，alpha=.5、gamma=2，R>.1 为雨，R==.1 为负。训练 10.420417119% prevalence 只作描述；不采用强正类 balanced alpha=.8957958，不添加 loss multiplier。

AdamW 的两个组严格覆盖全部 4,329,361 个参数且互斥：Conv2d kernel 4,322,832 使用 decay=1e-4；bias/GroupNorm affine 6,529 不 decay。未知分类立即 STOP。physical batch=2、accumulation=1、effective=2、BF16、validation batch=8、workers=2；无 augmentation、无按雨量重采样。

LR 用一基 update u，在 step 前设置。W=5860、U=293000；warmup 为 base*u/W；之后为 min+(base-min)*(1+cos(pi*(u-W)/(U-W)))/2。lr(1)=1e-4/5860，lr(W)=1e-4，lr(U)=1e-6。研究者已确认保留精确公式：warmup 的范围为 0<LR<=base，min_lr 下界只对 cosine 阶段生效；不 clamp。未来 Phase B 只定义 SAME_EPOCH_PROGRESS_ON_50_EPOCH_HORIZON，使用自己的 steps/epoch，训练 selected_checkpoint_epoch 个 epoch，不能把 cosine 压缩到 e_best；本轮不执行 Phase B。

每完成一个正式 epoch 才运行完整 2024 Validation。checkpoint 选择最低 exact global (S_occ+S_qr)/D_valid，raw 分子以 float64 累计，不能平均 batch loss；相等时选最早 epoch。Validation focal 在 float64 中按同一公式计算；这不改变 BF16/float32 训练前向。独立 early-stop reference 只有 new_val<best_es-1e-4 才更新；连续8次不满足才停止。小于1e-4的真实改进仍可更新 checkpoint best。

Validation 必须输出下列配置中的全部指标。AP 为 non-interpolated，在每个精确 equal-score 组末端计算 precision；AUROC 对 ties 给半信用。conditional coverage 使用 R<=qphysical，rainy valid cells；无雨 conditional 指标与单类 AUROC 输出 null 并说明。POD/FAR/CSI 必须为 THRESHOLD_NOT_FROZEN，不定义 probability cutoff。p_rain*mean(32 physical conditional quantiles) 的 MAE/RMSE/Bias 仅叫 DIAGNOSTIC_PROXY_METRIC，不是 E[R]。

主 B0–B8 seed=2026。必须在 Python/CUDA 启动前设置 PYTHONHASHSEED 和 CUBLAS_WORKSPACE_CONFIG，并按配置启用 deterministic algorithms、禁 TF32，不支持的操作 STOP。独立 Generator 为每 epoch 生成 seed2026+epoch_index 的完整一次性 permutation。未来 robustness seeds17/42 只给 B0/B8，本轮不执行，不将混合重复度比较说成公平的三 seed 主消融。

正式 checkpoint 只在 completed epoch boundary 保存；崩溃时从最近完成 epoch 重启下一整个 epoch。本轮 step2 temporary checkpoint 是 ENGINEERING_ONLY schema 例外，completed_epoch=0、global_update=2，不是正式 epoch checkpoint；测试后删除，不能上传。loader 必须在应用任何状态前核验 protocol、science、engineering、normalization、Train/Validation manifest、SP04、Yunnan 身份。模型、optimizer、RNG 和元数据的完整 schema 见配置。

dry-run 固定六个2023身份，三组 batch2，A/B 独立各三步，C 两步后临时 roundtrip 加第三步，最多九次真实更新。六个 reader/QC/normalization 输出保留为进程内不可修改 fixture 供相同 batches 重放，无永久 raw/cache 副本。每 worker 独立英文 staging，一次一个文件，700MiB cap，大小/SHA核验和清理；H 原始文件永久只读。

本轮不遍历完整训练集拟合、不创建正式 checkpoint、不读取2025、不计算 Phase-B normalization。即使 dry-run 全 PASS，也保持 FORMAL_TRAINING_AUTHORIZED=false，完成 GitHub 发布后停止。复现顺序：freeze → scheduler/group gate → real dry-run → 全部历史和新增 tests → seal → GitHub publication；需要既有 pinned 本地证据。运行脚本必须显式 --scope ENGINEERING_ONLY。

## 完整机器配置

```yaml
version: v1.0
status: RESEARCHER_APPROVED
scientific_status: RESEARCHER_APPROVED_PROTOCOL
baseline_commit: 11a4ab1a21275fb3a5b1b75bd7478cf3d6e0fd2b
scientific_freeze_version: v1.1
engineering_version: 4
authorization:
  PHASE_A_TRAINING_PROTOCOL_FROZEN: true
  FORMAL_TRAINING_AUTHORIZED: false
  B0_FORMAL_TRAINING_STARTED: false
  optimizer_dryrun_scope: ENGINEERING_ONLY
  full_train_fitting: false
  2025_access: false
  phase_b_normalization: false
identity:
  scientific_contract_v1.1:
    path: config/science_contract_v1.1.yaml
    sha256: 14209321d82107f58df96f234485cc56a806971cb62e8b9804ce4d25d05756c3
  scientific_freeze_v1.1_document:
    path: docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md
    sha256: 48e164cc7b6569d33e1929418ce60b13173957efbab3d97ca70cca0e6f7f1b6c
  engineering_v4:
    path: config/b0_engineering_v4.yaml
    sha256: bfcabbc31a6124d596cba893fc19ded09078a27780c2de40fa2b21ddd6b924a7
  phase_a_normalization_artifact:
    path: docs/b0_pretraining_closure/runs/run_20260930T095416Z/normalization_phaseA_2023_final_eligible.json
    sha256: 4bcfa0520550e343dd154fd4436715a306c015a02d16ec4a12bb2ed3cf606e0e
  eligible_train_manifest:
    path: docs/b0_pretraining_closure/runs/run_20260930T095416Z/normalization_phaseA_sample_manifest.csv
    sha256: dc0559f12f02817f8ec74916d03dd20e40ec0584ec58c59b34b5e02cc9a60e68
  eligible_validation_manifest:
    path: docs/phase_a_protocol_prefreeze/runs/run_20261001T014523Z/eligible_validation_manifest.csv
    sha256: ac5405d8185d6760acc15a4ab364804c1d8ec8de84064737d0757f6688aeb410
  combined_eligibility_source:
    path: docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv
    sha256: b4bad8ea45a78eddae3832df89cfade00cac3b184fc550eea4f0cf479c29de90
  SP04_mapping:
    path: config/spatial/sp04_target_cell_membership_v1.csv
    sha256: 3f4dea000efa0146cec292578bca07c370f897328c933e804346097f8ab9d3fd
  SP04_manifest:
    path: config/spatial/sp04_coordinate_manifest_v1.json
    sha256: e1c5d8ab1b58407503db4b56124f4a34a360507280b0e7989e8b9e2f60888473
  yunnan_mask:
    path: F:/pytorch/Research/outputs/stage0_spatial_decision_update/run_20260928T102636_513428Z/FROZEN/MASK/yunnan_evaluation_mask_center_gadm41_imerg_v1.nc
    sha256: 9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef
  prior_gpu_manifest:
    path: docs/gpu_training_feasibility/runs/run_20260930T154142Z/manifest.json
    sha256: c53cf3804c7f628951cd72d0134b0a4862b2e089d4141e06cf1ff5f420885eb8
model:
  name: B0
  backbone_policy: UNCHANGED_SCIENTIFIC_FREEZE_V1_1
  HEAD_IMPLEMENTATION_DETAIL_PINNED: true
  occurrence_head:
    type: Conv2d
    in_channels: 48
    out_channels: 1
    kernel_size: 1
    bias: true
    hidden_layers: 0
  quantile_head:
    type: Conv2d
    in_channels: 48
    out_channels: 32
    kernel_size: 1
    bias: true
    hidden_layers: 0
  extra_hidden_activation_attention_MLP_normalization: false
  semantic_output_transforms:
  - sigmoid occurrence
  - softplus sequential monotonic quantiles
  - expm1 physical quantiles
loss:
  core: L_occ + L_qr
  extra_multiplier: null
  occurrence:
    type: Focal_BCE
    alpha: 0.5
    gamma: 2.0
    alpha_t: alpha*y + (1-alpha)*(1-y)
    rainy: R > 0.1 mm/h
    R_equal_0_1: NEGATIVE
    denominator: all valid Yunnan supervised cells
    researcher_rationale: Do not adopt prevalence-derived alpha=0.8957958; gamma=2
      suppresses easy examples without gamma=3.
    train_positive_fraction_descriptive: 0.10420417118578294
  quantile:
    count: 32
    conditional_on: R > 0.1 mm/h
    domain: log1p
    tau: (i-0.5)/32 for i=1..32
    axis_reduction: mean
    denominator: all valid Yunnan supervised cells
    qlog_dtype: float64
    qphysical_dtype: float64
    pinball_dtype: float64
    raw_quantile_dtype: float32
    epsilon_mono: 0.0001
    sort_clamp_rank_repair_downcast: false
optimizer:
  type: AdamW
  betas:
  - 0.9
  - 0.999
  eps: 1.0e-08
  amsgrad: false
  maximize: false
  capturable: false
  differentiable: false
  foreach: false
  fused: false
  weight_decay: 0.0001
  DECAY_GROUP: all Conv2d kernel weights only
  NO_DECAY_GROUP: all Conv2d bias and GroupNorm affine
  expected_parameter_counts:
    DECAY_GROUP: 4322832
    NO_DECAY_GROUP: 6529
    total: 4329361
  unknown_parameter_policy: STOP
  assert_disjoint_complete_union: true
batch:
  train_physical: 2
  gradient_accumulation_steps: 1
  effective: 2
  validation: 8
  drop_last: false
precision:
  AMP: BF16
  autocast_device: cuda
  GradScaler: false
  model_parameters: float32
  raw_quantile: float32
  qlog: float64
  qphysical: float64
  pinball: float64
  TF32: false
data_loader:
  num_workers: 2
  pin_memory: false
  persistent_workers: false
  prefetch_factor: 1
  worker_root_policy: independent ASCII bounded staging root
  one_file_at_a_time: true
  max_temporary_bytes_per_worker: 734003200
  SHA_verification: true
  cleanup_required: true
  source_H_read_only: true
sampling:
  train_year: 2023
  train_count: 11720
  validation_year: 2024
  validation_count: 11727
  train_shuffle: true
  validation_shuffle: false
  train_once_per_epoch: true
  validation_order: pinned eligible manifest identity order
  rain_oversampling: false
  dry_undersampling: false
  class_balanced_sampler: false
  rate_based_sampler: false
  augmentation: NONE
  epoch_seed_rule: 2026 + epoch_index
  epoch_index_base: 0
  permutation: independent torch.Generator, randperm(11720)
scheduler:
  type: ONE_EPOCH_LINEAR_WARMUP_THEN_COSINE
  base_lr: 0.0001
  min_lr: 1.0e-06
  steps_per_epoch: 5860
  max_epochs: 50
  warmup_epochs: 1
  W: 5860
  U: 293000
  update_index_base: 1
  warmup: base_lr*u/W for 1<=u<=W
  cosine: min_lr+(base_lr-min_lr)*(1+cos(pi*(u-W)/(U-W)))/2 for W<u<=U
  apply_before_optimizer_step: true
  stateless: true
  resume_key: global_update
  ReduceLROnPlateau: false
  warmup_lower_bound_resolution: RESEARCHER_CONFIRMED_PRESERVE_EXACT_FORMULA
  warmup_range: 0 < lr <= base_lr; may be below min_lr
  cosine_range: min_lr <= lr <= base_lr
  resolution_reason: The exact first-step warmup formula gives 1e-4/5860; the Section19
    min_lr lower bound applies only to cosine. No clamping.
phase_b_replay:
  execution_authorized: false
  epoch_budget: selected_checkpoint_epoch
  normalization: future independent 2023+2024 recomputation; not executed now
  early_stopping: false
  2024_validation_trigger: false
  2025_use: false
  horizon_epochs: 50
  warmup_epochs: 1
  steps_per_epoch: FinalFit own population/batch
  compress_cosine_to_selected_epoch: false
  FINALFIT_LR_REPLAY_RULE: SAME_EPOCH_PROGRESS_ON_50_EPOCH_HORIZON
epochs:
  max_epochs: 50
  full_2024_validation_every_completed_epoch: true
  early_stopping:
    patience: 8
    min_delta_absolute: 0.0001
    mode: minimize
    first_call: initialize best_es and count=0
    improvement: new_val < best_es - 1e-4
    on_improvement: update best_es and reset count=0
    otherwise: count += 1
    stop: count >= 8
    separate_from_checkpoint_best: true
checkpoint:
  metric: global_val_core_loss
  definition: (S_occ + S_qr) / D_valid
  raw_numerator_dtype: float64
  validation_focal_arithmetic: float64 BCE/focal, same alpha/gamma/formula
  average_per_batch_loss: false
  selection: minimum exact global core loss
  tie_rule: earliest completed epoch
  min_delta_affects_selection: false
  EPOCH_BOUNDARY_RESUME_ONLY: true
  formal_save: only completed epoch boundary
  crash_resume: restart next complete epoch from latest completed epoch checkpoint
  mid_epoch_exact_resume_required: false
  temporary_step2_exception: ENGINEERING_ONLY TEMPORARY_PARTIAL_UPDATE_SCHEMA_TEST;
    completed_epoch=0, global_update=2; not a formal epoch checkpoint
  required_schema:
  - model_state_dict
  - optimizer_state_dict
  - completed_epoch
  - global_update
  - protocol_version
  - protocol_sha256
  - scientific_freeze_version
  - scientific_contract_sha256
  - engineering_config_sha256
  - normalization_artifact_sha256
  - train_manifest_sha256
  - validation_manifest_sha256
  - SP04_mapping_sha256
  - Yunnan_mask_sha256
  - focal_alpha
  - focal_gamma
  - optimizer_config
  - weight_decay_groups
  - base_lr
  - min_lr
  - physical_batch
  - effective_batch
  - AMP_mode
  - seed
  - epoch_seed_rule
  - best_checkpoint_metric
  - best_checkpoint_value
  - early_stop_best
  - non_improvement_count
  - python_rng_state
  - numpy_rng_state
  - torch_cpu_rng_state
  - torch_cuda_rng_state
  - environment
validation_metrics:
  required:
  - prevalence
  - Brier_Score
  - AUROC
  - Average_Precision
  - global_core_L_qr
  - conditional_mean_pinball
  - per_tau_pinball
  - per_tau_conditional_coverage
  - strict_crossing_count
  - nonfinite_count
  - N_valid
  - N_rain
  AP: NON_INTERPOLATED_END_OF_EXACT_EQUAL_SCORE_GROUP
  AUROC_ties: half credit
  coverage: R <= physical conditional quantile, valid rainy cells only
  no_rain_conditional_metrics: null
  single_class_AUROC: null
  strict_crossing_required: 0
  probability_cutoff: null
  POD_FAR_CSI: THRESHOLD_NOT_FROZEN
  selection_uses_only_global_core_loss: true
  diagnostic_proxy:
    name: DIAGNOSTIC_PROXY_METRIC
    formula: p_rain*mean(32 physical conditional quantiles)
    metrics:
    - MAE
    - RMSE
    - Bias
    is_exact_expectation: false
gradient_clipping:
  global_norm: 5.0
  norm_type: 2.0
  error_if_nonfinite: true
  order:
  - backward
  - compute pre-clip norm
  - clip_grad_norm_
  - record clipping
  - optimizer.step
  post_clip_interpretation: norm after torch scaling; scaling coefficient=min(1,5/(pre_norm+1e-6));
    no GradScaler
reproducibility:
  primary_seed: 2026
  Python_seed: 2026
  NumPy_seed: 2026
  torch_CPU_seed: 2026
  torch_CUDA_all_seed: 2026
  PYTHONHASHSEED: '2026'
  CUBLAS_WORKSPACE_CONFIG: :4096:8
  set_environment_before_Python_CUDA: true
  deterministic_algorithms: true
  warn_only: false
  cudnn_deterministic: true
  cudnn_benchmark: false
  cuda_matmul_allow_tf32: false
  cudnn_allow_tf32: false
  float32_matmul_precision: highest
  unsupported_operation: STOP
  robustness_future_only:
    models:
    - B0
    - B8
    extra_seeds:
    - 17
    - 42
    execute_now: false
fairness:
  main_models: B0-B8
  same_primary_seed: 2026
  shared:
  - loss semantics
  - alpha
  - gamma
  - AdamW family
  - decay policy
  - base LR policy
  - warmup/cosine
  - effective batch
  - AMP numerical policy
  - seed
  - checkpoint metric
  - validation metrics
  - epoch/early-stop policy
  future_memory_audited_exception:
    physical_batch: 1
    accumulation: 2
    effective: 2
  increase_effective_batch: false
  equal_repeat_count_claim_for_mixed_seed_comparison: false
dryrun:
  scope: ENGINEERING_ONLY
  fixed_real_2023_scenes: 6
  batches: 3
  selection: np.linspace(0,11719,6,dtype=int64), pinned manifest identity order
  training_updates_maximum_total: 9
  Run_A: fresh seed2026, three updates
  Run_B: independent fresh seed2026, identical three batches
  Run_C: fresh steps1,2; temporary checkpoint; destroy; restore; step3
  dedicated_VRAM_headroom_minimum: 0.2
  no_batch_reduction: true
  replay: bit-exact model state SHA and exact loss/LR/pre-clip norm/clipping
  temporary_checkpoint_cleanup_required: true
  stop_conditions:
  - OOM
  - headroom below20%
  - nonfinite loss/gradient
  - quantile crossing
  - unsupported deterministic op
  - A/B mismatch
  - resume mismatch
  - wrong groups
  - provenance rejection failure
  - scheduler boundary failure
  - existing test regression
```
