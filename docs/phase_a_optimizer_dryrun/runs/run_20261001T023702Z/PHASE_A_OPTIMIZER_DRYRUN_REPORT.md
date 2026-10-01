# PHASE_A_OPTIMIZER_DRYRUN_REPORT

状态：**STOPPED_SCHEDULER_BOUNDARY_FAILURE**。协议已按研究者批准冻结，工程验证未通过。

Baseline `11a4ab1a21275fb3a5b1b75bd7478cf3d6e0fd2b`；run `run_20261001T023702Z`。

## 真实执行结果

已创建独立 protocol v1.0 文档与完整 YAML，核验全部继承身份 SHA；Scientific Freeze v1.1 和历史文件未修改。研究者已确认：保留精确 warmup 公式，min_lr 下界仅作用于 cosine。
CPU 小测试确认 head 实现和参数组正确：decay=4,322,832；no-decay=6,529；total=4,329,361，互斥且完整。初步16项 protocol 单元测试执行13 PASS、3 FAIL；无 skipped。

## 触发 STOP 的问题

当前 `base_lr * u / W` 按 `(base_lr*u)/W` 求值，在 u=W=5860 产生 `0.00010000000000000002`，规定端点为 `0.0001`。差值为 `2.710505431213761e-20`，是浮点操作顺序的数值边界错误，不是科研参数缺失。它导致端点精确比较、warmup<=base 上界、Phase-A/FinalFit相同epoch进度的精确比较共3项失败。

附件第27节规定 scheduler boundary failure 必须 STOP、只报告问题、不自动修改研究者批准参数。本轮在此停止；未修正求值顺序，未放宽测试为 tolerance，未使用 clamp。
可供研究者批准的后续修复是按等价数学公式 `base_lr*(u/W)` 求值，保留全部科学参数，再在独立新 run 验证完整 schedule。当前失败 run 必须保留。此建议尚未应用。

## 未执行项目

六个真实样本选择/reader/QC、GPU optimizer、20% VRAM gate、A/B bit-exact replay、Run C temporary checkpoint/resume、序列化checkpoint破坏保护、全部137历史测试均为 NOT_RUN。本轮未产生 optimizer.step、真实数据读取、GPU memory测量、checkpoint文件。CPU 单元测试只实例化 AdamW 检查 defaults/groups，未更新参数；metadata-only rejection 单元测试不能替代真实 checkpoint loader test。
optimizer CSV 和各 replay/memory JSON 明确标为 NOT_RUN；任何未执行项目均不算 PASS。未执行137旧测试不构成其回归或通过结论；历史137 PASS证据仍属于既有 baseline。新增 validation helper 的 batch全局分子、AP exact ties、R==.1边界等已通过本轮 CPU 小测试，但不代表完整真实 Validation epoch 已执行。

## 冻结身份

Protocol SHA256 `dcacbe34050da7e777ad0cb72c53b5b51b48ce57eb9260b09fd283d96de12a4a`。
Document SHA256 `3480baca7e7dd1839a534660fef5e7a41a9e013107954cdef44574e110631e2c`。
全部来源/版本/hash 见 protocol_identity.json，参数名完整列表见 parameter_groups.json。config/document 是本轮冻结 overlay；实现代码保持失败时的版本，不能作为已经工程验证通过的训练入口。

## 最终状态

```json
{
  "run_status": "STOPPED_SCHEDULER_BOUNDARY_FAILURE",
  "stop_condition": "SCHEDULER_BOUNDARY_FAILURE",
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
  "DRYRUN_OPTIMIZER_STEP_PASS": false,
  "DRYRUN_MEMORY_SAFE": false,
  "DETERMINISTIC_REPLAY_PASS": false,
  "RESUME_REPLAY_EXACT_PASS": false,
  "CHECKPOINT_PROVENANCE_GUARD_PASS": false,
  "PROTOCOL_ENGINEERING_VALIDATED": false,
  "B0_FORMAL_TRAINING_STARTED": false,
  "FORMAL_TRAINING_AUTHORIZED": false,
  "actual_optimizer_steps": 0,
  "real_data_samples_read": 0,
  "2025_pixels_read": false,
  "formal_or_temporary_checkpoints_created": 0,
  "execution_status": {
    "protocol_freeze": "PASS",
    "head_pin": "PASS",
    "parameter_groups": "PASS",
    "scheduler": "FAIL",
    "optimizer_dryrun": "NOT_RUN",
    "optimizer_memory": "NOT_RUN",
    "A_B_deterministic_replay": "NOT_RUN",
    "temporary_checkpoint_resume": "NOT_RUN",
    "serialized_checkpoint_provenance_guard": "NOT_RUN",
    "full_required_test_suite": "NOT_RUN"
  },
  "boolean_interpretation": "False for unexecuted gates means not proven; consult execution_status. NOT_RUN is never PASS."
}
```

manifest 保存新产物 SHA 与全部 baseline 文件的 Git blob / disk SHA 核验。仅发布文本配置、源码、测试和失败证据；没有提交原始数据、wheel、venv、cache、模型或 optimizer 二进制。B0_FORMAL_TRAINING_STARTED=false，FORMAL_TRAINING_AUTHORIZED=false。发布后停止。
