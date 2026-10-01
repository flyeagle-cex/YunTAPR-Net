# B0 Phase-A formal training report

Run `run_20261001T035003_243409Z`; baseline `aa65a5b4b33f04d7adddd1ca832963dcb21e4487`; scope `FORMAL_SCIENTIFIC_RUN`. Completion: **True**. Stop reason: **EARLY_STOP**. Completed epochs: **19**.

Researcher authorization is separate from the immutable historical protocol. B0 only, Protocol v1.0, seed 2026, 11720 frozen 2023 Train identities and 11727 frozen 2024 Validation identities. No 2025 sources, Phase-B, Phase-B normalization, B1–B8, calibration or threshold selection.

Formal training started: True. Selected checkpoint epoch: 11; global Validation core loss: 0.04730775889882134.

Train uses batch 2, accumulation 1, AdamW (.9,.999), eps 1e-8, decay 1e-4 on Conv2d kernels only; BF16 forward, FP32 parameters/raw quantiles, float64 qlog/qphysical/pinball, no GradScaler. Every update checks finite outputs/loss/gradients/parameters/optimizer state, strict quantiles and determinism. LR uses the approved corrected expression base_lr*(u/W), unchanged 50-epoch horizon, no warmup clamp. Grad norm clips at 5. Train permutation uses independent Generator(2026+zero-based epoch). Any sample read, identity, QC or numerical failure stops; no sample skipping or automatic tuning.

Global Train loss accumulates undivided production per-cell focal arithmetic promoted before summation and float64 pinball over the global valid denominator. Validation uses frozen float64 BCE/focal and pinball raw numerators with complete fixed-order population. Both avoid averaging batch means. Exact grouped AUROC/AP, per-tau pinball/coverage and DIAGNOSTIC_PROXY_METRIC are in each completed epoch JSON. POD/FAR/CSI remain THRESHOLD_NOT_FROZEN. The proxy is not E[R].

Validation hashes lacking historical full-population pins are explicitly additional run-preflight byte identities; the frozen identity/order and eligibility manifests remain untouched. Historical spot-check hashes are compared. All source reads use one-file bounded SHA-verified English staging in independent ASCII worker roots. Copy/read seconds, temporary bytes and cleanup are in epoch I/O summaries. H and IMERG raw sources remain read-only.

Only completed Train+Validation epochs can create BEST/LAST. Exact minimum chooses BEST; ties keep earliest. Early stopping independently requires improvement greater than 1e-4 with patience 8. Checkpoint write is temporary → fsync/close → round-trip/hash/provenance verification → atomic rename. New verified registry precedes old owned-file cleanup. Resume validates all provenance before applying states and starts the next whole epoch from LAST.

Checkpoint root: `F:\pytorch\Research\outputs\formal_training\b0_phase_a\run_20261001T035003_243409Z`. CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT=true. BEST SHA256: `3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3`; LAST SHA256: `6bb680f74f0b3ce0b02be435ac8b28ba7e0fa8e8409af83ebfa558a8564e0558`. Absolute paths, filenames, sizes and identities are in checkpoint_registry.json and BEST/LAST identity JSON.

Post-run current 162 tests actually executed and PASS: True; provenance PASS: True; historical files preserved: True. Additional formal guard tests also execute.

Artifacts: formal_run_manifest.json, preflight.json, source_identity_preflight.csv, epoch_*.json, training_history.csv, validation_history.csv, early_stopping_summary.json, runtime_summary.json, test_results_post_training.txt and final_status.json. No completed epoch means the histories are empty, not fabricated, and no checkpoint is selected.

PHASE_B_AUTHORIZED=false. This run stops here for researcher review; it does not enter the next stage.

## Completed-epoch observations

The table uses only completed Train and Validation epochs. Scalar curves are also available in [training_history.csv](training_history.csv) and [validation_history.csv](validation_history.csv).

| Epoch | Train core loss | Validation core loss | BEST epoch | Early-stop count |
| --- | --- | --- | --- | --- |
| 1 | 0.08127404553 | 0.0519111694 | 1 | 0 |
| 2 | 0.04490618169 | 0.04992138597 | 2 | 0 |
| 3 | 0.04344276415 | 0.04943675858 | 3 | 0 |
| 4 | 0.04263508008 | 0.04963783689 | 3 | 1 |
| 5 | 0.04195316906 | 0.04967412557 | 3 | 2 |
| 6 | 0.04136502694 | 0.04829794537 | 6 | 0 |
| 7 | 0.04085129639 | 0.04808821837 | 7 | 0 |
| 8 | 0.04033194665 | 0.04805584488 | 8 | 1 |
| 9 | 0.03987191326 | 0.04757666937 | 9 | 0 |
| 10 | 0.03939065532 | 0.04766025164 | 9 | 1 |
| 11 | 0.03892391587 | 0.0473077589 | 11 | 0 |
| 12 | 0.0384440286 | 0.04758694544 | 11 | 1 |
| 13 | 0.03801822448 | 0.04768116502 | 11 | 2 |
| 14 | 0.03759059091 | 0.047659183 | 11 | 3 |
| 15 | 0.03715352757 | 0.0482586143 | 11 | 4 |
| 16 | 0.03670260743 | 0.04796555806 | 11 | 5 |
| 17 | 0.03626438049 | 0.04803469107 | 11 | 6 |
| 18 | 0.03581716272 | 0.0483021274 | 11 | 7 |
| 19 | 0.03534704008 | 0.0486348705 | 11 | 8 |

## Selected checkpoint: completed epoch 11

| Validation observation | Actual value |
| --- | --- |
| global_val_core_loss | 0.04730775889882134 |
| global_L_occ | 0.032294367961026665 |
| global_core_L_qr | 0.015013390937794673 |
| N_valid | 40223610 |
| N_rain | 4809183 |
| prevalence | 0.1195611980128089 |
| Brier_Score | 0.09485221785034452 |
| AUROC | 0.8881853941862204 |
| Average_Precision | 0.5568845072477755 |
| conditional_mean_pinball | 0.12557076365349107 |
| strict_crossing_count | 0 |
| nonfinite_count | 0 |

Full precision, conventions and per-tau observations are retained in [epoch_011.json](epoch_011.json). The 32 quantile levels use the immutable science-contract formula `(i-0.5)/32`, i=1,...,32. Coverage is conditional on rainy valid cells and uses `R <= physical quantile`; pinball uses the frozen log1p loss domain. No probability cutoff was selected; POD/FAR/CSI remain `THRESHOLD_NOT_FROZEN`.

| tau | Conditional pinball | Conditional coverage |
| --- | --- | --- |
| 0.015625 | 0.00919442781 | 0.003060810953 |
| 0.046875 | 0.02739257065 | 0.08937713537 |
| 0.078125 | 0.04338474012 | 0.1018407908 |
| 0.109375 | 0.05882444254 | 0.1207134351 |
| 0.140625 | 0.07385969544 | 0.1626881323 |
| 0.171875 | 0.08807206236 | 0.2035840599 |
| 0.203125 | 0.1010719259 | 0.2283710144 |
| 0.234375 | 0.1132091154 | 0.254731417 |
| 0.265625 | 0.1249471042 | 0.2947741851 |
| 0.296875 | 0.1351331323 | 0.3206810803 |
| 0.328125 | 0.1448196702 | 0.3577821846 |
| 0.359375 | 0.1534427798 | 0.3887795495 |
| 0.390625 | 0.1604899962 | 0.4027430439 |
| 0.421875 | 0.1675074422 | 0.4479800415 |
| 0.453125 | 0.1726188409 | 0.470454545 |
| 0.484375 | 0.1773592386 | 0.5092049939 |
| 0.515625 | 0.1803171387 | 0.5301282983 |
| 0.546875 | 0.1823363058 | 0.559120125 |
| 0.578125 | 0.1832573035 | 0.5896905982 |
| 0.609375 | 0.1828737514 | 0.6199606045 |
| 0.640625 | 0.1810877074 | 0.6534461259 |
| 0.671875 | 0.1777969197 | 0.6721792454 |
| 0.703125 | 0.173094874 | 0.7035111785 |
| 0.734375 | 0.1666810316 | 0.734374217 |
| 0.765625 | 0.15865555 | 0.764264949 |
| 0.796875 | 0.1487790022 | 0.7905226314 |
| 0.828125 | 0.136744526 | 0.8205231533 |
| 0.859375 | 0.1222481446 | 0.8499387526 |
| 0.890625 | 0.1050138511 | 0.8796211332 |
| 0.921875 | 0.08415228042 | 0.9108640698 |
| 0.953125 | 0.05865329463 | 0.9424846174 |
| 0.984375 | 0.02524557121 | 0.9774913951 |

The same observations are exported in [selected_checkpoint_quantile_metrics.csv](selected_checkpoint_quantile_metrics.csv). These are evaluation observations, not an acceptance decision or a new calibration step.

## Evidence closure

The initialization manifest and in-process evidence index are retained as `formal_run_manifest_initialized.json` and `evidence_sha256_pre_log_close.json`. The final manifest mirrors actual final status. The evidence index is refreshed after the final stdout record and the execution log close. The original automatically generated report is retained as `B0_PHASE_A_FORMAL_TRAINING_REPORT_generated.md`; this report adds tables from the already completed epoch evidence. Frozen scientific files, run implementation and checkpoint payloads remain unchanged.
