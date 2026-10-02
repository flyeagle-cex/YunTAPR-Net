# B0 Phase-A researcher acceptance v1

研究者正式接受 B0 Phase-A 作为 CONTROL / BASELINE；不声称完整 YunTAPR-Net 已被证明。

Scientific Review run: `run_20261002T005448_798068Z`；commit: `5050b6cc77ab75eacb96e1494a165d61142227f4`。历史 review 保持 immutable；它当时的 UNDECIDED 状态由本独立决策继承并更新，不回写历史。

`ACCEPT_B0_PHASE_A=true`；`B0_PHASE_A_ACCEPTED=true`；BEST epoch=11，Val core=0.04730775889882134，checkpoint SHA256=`3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3`。完整 identity/hash 见 config/decisions/b0_phase_a_acceptance_v1.yaml。

`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=11`；FinalFit 11 epochs，fresh model seed=2026。BEST 仅为科学身份和预算选择证据，不载入 FinalFit model/optimizer/scheduler。

FinalFit population=23,447 eligible March–October scenes：2023 Train 11,720 + 2024 Validation 11,727。仅对其 full-valid native B13 重算 ddof=0 normalization。2025 禁止读取。

physical batch=2、drop_last=false；尾部 singleton 不丢弃、不复制、不替换。每 epoch 所有身份恰好一次，11,724 updates/epoch；计划总更新128,964。保持1 epoch warmup及50 epoch cosine horizon，W=11,724，U=586,200；不能压缩为11 epoch。

保留所有已知限制：epoch11后 Validation degradation、低tau calibration deviation、月份与空间差异、稀疏强雨样本、single-band/single-time设计信息限制。物理原因未证实，不据此修改冻结规则或参数。

本轮仅 acceptance + preparation + 两个独立 ENGINEERING_ONLY batch；`PHASE_B_AUTHORIZED=false`，`PHASE_B_FORMAL_TRAINING_STARTED=false`。不启动正式FinalFit或B1–B8。
