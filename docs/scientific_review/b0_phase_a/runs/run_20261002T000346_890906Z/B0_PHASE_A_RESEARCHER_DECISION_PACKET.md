# B0 Phase-A researcher decision packet — INCOMPLETE

Review `run_20261002T000346_890906Z`。**不能把这份 partial packet 视为完整 Scientific Characterization Review 通过。**

## A. Protocol compliance

冻结身份与 BEST 核验 PASS，1466 个 baseline 文件及 BEST 未修改。没有训练、optimizer step/backward、2025 pixels 或下一 Stage。
正式协议符合性以原有 run evidence 为历史输入，本轮 171-test rerun 尚未执行。

## B. Training convergence evidence

OBSERVED：epoch 11→19，Train core 从 0.03892391586529146 降至 0.03534704007581559，Val core 从 0.04730775889882134 升至 0.048634870497155404，增加 0.001327111598（相对 epoch 11 约 2.8053%）。epoch 12–19 均未优于 epoch 11；epoch 19 的独立 early-stop counter 达到 8。该记录支持‘验证损失在 epoch 11 后未继续改善并总体上升’的描述，不据此定义‘严重过拟合’，也不确立气象物理原因。

## C. Selected checkpoint identity

epoch 11；update 64460；Val core 0.04730775889882134；bytes 52062315。
`F:\pytorch\Research\outputs\formal_training\b0_phase_a\run_20261001T035003_243409Z\epoch_011.pt`；SHA `3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3`。`CHECKPOINT_SELECTION_REMAINS_EPOCH_11`。

## D. Occurrence performance

HISTORICAL_ONLY：Brier=0.094852217850, AUROC=0.888185394186, AP=0.556884507248, conditional mean pinball=0.125570763653。固定-bin reliability 和 rainy/dry probability distributions 尚未计算。

## E. Probabilistic quantile performance

冻结 32 个 tau；历史 conditional pinball 已列表。本轮 full float64 numerical checks 未执行。

## F. Calibration diagnostics

最低 tau 历史 coverage=0.0030608109527127583；32 项历史 calibration 表与 analytic-only tail grouping 已保存。
完整再推理精确 coverage reproduction 尚未执行，不能以历史统计替代。

## G. Monthly/spatial/rain-rate weaknesses

NOT_RUN_SOURCE_DRIVE_UNAVAILABLE。没有预冻结 subregion masks，未来只按原冻结 Yunnan mask 做 cell diagnostics。
未据模型输出画区域、选择阈值或调整训练。

## H. Known limitations

见 `B0_LIMITATION_INVENTORY.md`。已观察的 history loss 回升和最低 tau 误差，与单帧单通道设计事实分别表述。
月份、空间与强降水限制尚缺本轮证据。

## I. Open questions / missing gates

- 需要冻结 H 源重新可见；不使用另源替代 11,727 场完整样本。
- 研究者尚未答复：是否允许既有 171 tests 在独立 fixture 执行 optimizer/backward，同时审阅进程硬禁止这些操作。
- 尚缺 full population metrics、所有计数对账、full artifact tests 和完整图件。
- 具体物理误差原因未确立；项目 extreme definition 仍为 NOT_FROZEN。

## J. Researcher decision required

`ACCEPT_B0_PHASE_A=UNDECIDED` / `B0_PHASE_A_ACCEPTED=UNDECIDED`。
`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`。
`PHASE_B_AUTHORIZED=false`；`B1_TO_B8_AUTHORIZED=false`。
本轮没有替研究者决定接受、迁移预算或启动 Phase-B。
