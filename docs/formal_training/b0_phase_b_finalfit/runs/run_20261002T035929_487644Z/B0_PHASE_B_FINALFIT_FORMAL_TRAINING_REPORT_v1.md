# B0 Phase-B FinalFit formal training v1

Baseline `4de37ac087183bddf3b9f8c7d548a0f976a50e91`; independent formal run `run_20261002T035929_487644Z`.
Researcher scope B0_PHASE_B_FINALFIT_ONLY. Fresh seed2026 model identity matches
`57a4d103a31aa7be1a52af079cdf7fb81bc73c51ba3e0e97d395513d21d9023d`.
No Phase-A model/optimizer/scheduler state was used. Historical false authorization
fields, all baseline files and the SHA-pinned runner/module/config remain unchanged.

All 11 fixed-budget epochs completed: each of the 23,447 identities appeared
exactly once per epoch. Physical batch size was 2, with one final singleton batch.
There was no skip, drop, duplication, padding or replacement. Each epoch contained
11,724 updates, giving 128,964 in total. Actual private update-log identities,
order, LR and denominators were
independently rechecked after training. All original source SHA preflight and runtime
staged source/QC/causality checks passed. No source/numerical failure was bypassed.

Normalization mean 270.5900486586461 K / std 20.368583874067266 K, SHA
`c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327`, reused unchanged. Manifest SHA `00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff`.
Architecture/loss/AdamW/BF16/FP32 parameters/raw quantiles/FP64 quantile/pinball and
global norm clip 5 inherit the unchanged protocol. W=11,724/U=586,200 retain the
50-epoch scheduler horizon. Epoch-one actual singleton LR is exactly 1e-4;
every singleton actual denominator is 3430, each full batch 6860.

No independent 2024 validation, early stopping, BEST selection, epoch reselection,
training-loss budget adjustment, 2025 access or next-stage execution occurred.
Global loss uses accumulated raw numerators divided by total actual valid pixels;
it is not a mean of batch losses. Requested LR/gradient/clip/GPU/I/O/tail metrics
are in `training_history.csv` and eleven `epoch_*_summary.json` files.

LAST and FINAL both identify epoch 11. Checkpoints use temporary writes, fsync,
round-trip/SHA checks and atomic rename. All eleven boundary payloads remain at
the researcher-approved F: root. Binary payloads are excluded from Git. FINAL
readability/SHA/provenance passed; post-training tests never applied FINAL state.

All current 242 tests plus 12 legal new tests were
executed after training: total 254, zero failures/errors/skips.
Isolated fixture artifacts were cleaned; FINAL SHA before/after tests is unchanged.
The Phase-B result describes fixed-budget FinalFit completion; it makes no 2025
Final Test or B1-B8 performance claim.

A report-only execution-manifest path error occurred after all 254 tests passed. Its failure record is preserved, along with the timestamped metadata correction. The correction rechecked FINAL SHA/provenance and added zero formal optimizer updates.

```json
{
  "state": "B0_PHASE_B_FINALFIT_FORMAL_TRAINING_COMPLETED_POST_TEST_CLOSURE_PASS",
  "run_id": "run_20261002T035929_487644Z",
  "PHASE_B_AUTHORIZED": true,
  "PHASE_B_FORMAL_TRAINING_STARTED": true,
  "PHASE_B_FINALFIT_COMPLETED": true,
  "TOTAL_COMPLETED_EPOCHS": 11,
  "FORMAL_OPTIMIZER_STEPS": 128964,
  "EXPECTED_FORMAL_OPTIMIZER_STEPS": 128964,
  "FINAL_EPOCH": 11,
  "FINAL_CHECKPOINT_SHA256": "05359d2fee2ae61daf654ae5a59b7977cb65247fd46d97a69a690a0133da7f65",
  "FINAL_CHECKPOINT_LOCAL_PATH": "F:\\pytorch\\Research\\outputs\\formal_training\\b0_phase_b_finalfit\\run_20261002T035929_487644Z\\epoch_011.pt",
  "FINAL_CHECKPOINT_READABLE_SHA_PROVENANCE_PASS": true,
  "2025_PIXELS_READ": 0,
  "B1_STARTED": false,
  "B1_TO_B8_AUTHORIZED": false,
  "FINAL_TEST_2025_AUTHORIZED": false,
  "FINAL_TEST_2025_EXECUTED": false,
  "TOTAL_POST_TRAINING_TESTS_EXECUTED": 254,
  "TEST_FAILURES": 0,
  "TEST_ERRORS": 0,
  "TEST_SKIPS": 0,
  "FINAL_SHA_UNCHANGED_BY_TESTS": true,
  "CHECKPOINT_BINARY_NOT_COMMITTED_TO_GIT": true,
  "baseline_commit": "4de37ac087183bddf3b9f8c7d548a0f976a50e91",
  "completed_utc": "2026-10-02T13:25:06.369083+00:00"
}
```

STOP after publication. Final Test 2025 and B1-B8 remain unauthorized.
