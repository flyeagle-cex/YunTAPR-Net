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
