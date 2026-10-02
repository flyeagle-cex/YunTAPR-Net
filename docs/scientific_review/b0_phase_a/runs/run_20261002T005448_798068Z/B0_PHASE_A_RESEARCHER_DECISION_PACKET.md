# B0 Phase-A researcher decision packet

完整 scientific review `run_20261002T005448_798068Z` 已执行；本 packet 将证据提供给研究者，**不代为接受实验**。

## A. Protocol compliance

所有冻结身份、源 preflight、11,727-scene fixed order、full counts、FP32/BF16/FP64 路径、因果约束与 numerical checks 均 PASS。
Model logical SHA 和 BEST 文件前后不变；review optimizer=0、backward=0、2025 pixels=0。
旧 blocked run immutable；approved fixture tests 单独进程且已清理。

## B. Training convergence evidence

OBSERVED：epoch 11→19，Train core 从 0.03892391586529146 降至 0.03534704007581559；Val core 从 0.04730775889882134 升至 0.048634870497155404，差值 0.001327111598（相对约 2.8053%）。epoch 12–19 无一优于 epoch 11，epoch 19 的独立 early-stop counter=8。这里只描述 Validation degradation，不定义‘严重过拟合’，不确定物理原因。

## C. Selected checkpoint identity

epoch 11 / global_update 64460 / official core 0.04730775889882134。
`F:\pytorch\Research\outputs\formal_training\b0_phase_a\run_20261001T035003_243409Z\epoch_011.pt`；bytes=52062315；SHA=`3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3`。
`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`，minimum global_val_core_loss criterion 未变。

## D. Occurrence performance

N_valid=40,223,610 / N_rain=4,809,183 / prevalence=0.119561198013。
Brier=0.094852217850；AUROC=0.888185394186；AP=0.556884507248；conditional mean pinball=0.125570763653。
10 个固定-bin reliability 与 rainy/dry probability distributions 完整；Brier 和 rank metrics 不能互相替代，未选 cutoff/校准。

## E. Probabilistic quantile performance

完整 32 tau conditional pinball/coverage 与正式 epoch 11 复现通过，所有 qlog/qphysical crossing、nonfinite、q1 support violation=0。
qlog/physical float64；无 quantile sort/clamp/校准。

## F. Calibration diagnostics

lowest tau=0.015625，coverage=0.003060810953；error=-0.012564189047。
low/middle/high analytic-only MAE 见 quantile_tail_diagnostics.json；reliability fixed-bin weighted absolute deviation=0.135589834112（BINNED_DIAGNOSTIC）。
Numerical stability 与 probabilistic calibration 分别核验；严格单调不等于校准正确。

## G. Monthly / spatial / rain-rate weaknesses

- OBSERVED：core loss 范围 0.0100054335（2024-03）至 0.0725989771（2024-07）。
- OBSERVED：Brier 范围 0.0289755321（2024-03）至 0.1389291529（2024-07）。
- OBSERVED：AUROC 范围 0.8454145443（2024-10）至 0.9392615838（2024-03）。
- OBSERVED：AP 范围 0.2835895836（2024-03）至 0.6300870653（2024-07）。
- OBSERVED：conditional pinball 范围 0.1080925249（2024-10）至 0.1385859696（2024-03）。

Yunnan cell maps/ranges 完整，NO_PREDEFINED_SUBREGION_MASK_AVAILABLE；未创建事后 regions。
强降水 >50 mm/h count=72；true-rate 档和 >10/20/30/50 都仅描述性，极端科学定义 NOT_FROZEN。
详见主报告中的全表；没有从诊断地图/阈值反向改 protocol 或 loss weights。

## H. Known limitations

参见 B0_LIMITATION_INVENTORY.md：post-11 validation 回升、low-tau coverage deviation、月度/空间差异、强雨支持数量和 proxy 定义限制。
单帧单通道为设计事实；未证明其造成某项误差，B0 只作 CONTROL / BASELINE，不代表全 YunTAPR-Net 有效。

## I. Open questions

- 研究者如何评价当前 B0 收敛、概率校准和各月/雨强支持的充分性？本 packet 不建立新接受阈值。
- 是否接受 Phase-A 作为严格可比 baseline，以及后续试验预算/方案？没有自动实施。
- 物理原因未确立；没有额外气象/地形变量与可比实验，不给 causal conclusion。
- 正式 extreme definition 仍 NOT_FROZEN；所有本轮 thresholds 只是 DESCRIPTIVE_ONLY。
- 未触及 2025，后续 test/FinalFit 需原科研合同和独立授权。

## J. Researcher decision required

`ACCEPT_B0_PHASE_A=UNDECIDED`。
`B0_PHASE_A_ACCEPTED=UNDECIDED`。
`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`。
`PHASE_B_AUTHORIZED=false` / `B1_TO_B8_AUTHORIZED=false`。

测试：171 existing + 8 units + 11 artifacts = 190，全部 PASS/无跳过。
完整完成状态只表示 review requirements 已满足，接受与下一 Stage 仍由研究者决定。
