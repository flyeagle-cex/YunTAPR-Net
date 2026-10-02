# B0 Phase-A scientific review

This workflow is `SCIENTIFIC_RESULT_REVIEW_ONLY`. It has no optimizer/training action and cannot authorize Phase-B. Existing scientific/model/protocol/normalization files remain unchanged.

## Current attempt

`runs/run_20261002T000346_890906Z/` is **BLOCKED_SOURCE_DRIVE_UNAVAILABLE**, with full review completion **false**. The first frozen Himawari source was unavailable because H was absent; 0 scenes and 0 Validation pixels were inferred. Its actual failure trace is retained. The 6 history figures, 19-epoch tables, historical epoch-11 quantile analysis, BEST identity verification and 8 executed unit tests are valid partial evidence. They do not replace the required full reinference, 171-test rerun or full artifact checks.

Read [B0_PHASE_A_SCIENTIFIC_REVIEW.md](runs/run_20261002T000346_890906Z/B0_PHASE_A_SCIENTIFIC_REVIEW.md), [researcher decision packet](runs/run_20261002T000346_890906Z/B0_PHASE_A_RESEARCHER_DECISION_PACKET.md), and [final_status.json](runs/run_20261002T000346_890906Z/final_status.json).

## Implementation and data controls

- `scripts/review_b0_phase_a_scientific_v1.py` verifies baseline, all frozen identities, formal BEST file/payload, immutable sources and official Validation order. It predeclares diagnostic rules before inference. The full population is 11,727 scenes / 40,223,610 valid / 4,809,183 rainy cells.
- `src/yuntapr/training/scientific_review.py` blocks optimizer construction, optimizer steps and backward in the review process. It rejects non-2024 Validation roles/paths before staging reads. Statistics reuse the unchanged formal global accumulator, BF16 forward, FP32 raw head and FP64 quantiles. Rain labels use the existing float32 comparison before promotion.
- The old mixed-year per-frame QC ledger is not opened. The formal source ledger and frozen 2023/2024 eligibility metadata provide the identities. B13 timestamps are read from each SHA-verified 2024 source and checked against frozen pairing before using the unchanged assembler. No optimizer checkpoint states are applied; their inert checksums are verified as part of full checkpoint provenance.
- B13/IMERG remain read-only. A separate `cache/staging/review_<run_id>/` bounds each worker to one temporary file, with size/source+copy SHA verification and required cleanup. Only owned copies can be removed. Diagnostic caches and old runs are preserved.
- `scripts/plot_b0_scientific_review_v1.py` uses the already installed CPU plotting environment; no dependency installation or upgrades. `--history-only` renders legitimate historical curves when raw data are unavailable. Spatial plots require the actual frozen target axes and mask.
- `scripts/report_b0_review_blocked_v1.py` seals a failed-source attempt with explicit incomplete/NOT_RUN statuses. It never manufactures population metrics or substitutes historical results for current full checks.
- Reliability bins, rain-rate strata, count>=30 display rule, tail groupings and objective top-10 case selection are declared in `case_selection_rules.json`. They do not change sample eligibility, loss, calibration, regions or scientific thresholds.

The inherited formal input/forward wrappers retain their original `FORMAL_SCIENTIFIC_RUN` tensor-contract tag; the new process-level authority is narrower `SCIENTIFIC_RESULT_REVIEW_ONLY`, enforced by its operation guard. The historical training authorization is provenance, never permission for this review to optimize.

## Tests and missing gates

Run unit boundaries without opening raw data:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& 'F:\pytorch\Research\.venv-cuda\Scripts\python.exe' -B -m unittest discover -s tests/scientific_review -p test_review_units.py -v
```

11 additional full-artifact tests require `YUNTAPR_SCIENTIFIC_REVIEW_EVIDENCE` to point to an actually completed full reinference run. Missing artifacts fail rather than skip. They verify global/monthly/spatial/rate/reliability counts, exact quantile coverage reproduction, coordinate identity, BEST SHA, model-state preservation, zero optimizer/backward, no 2025 access, numerical zero counts and objective cases. These 11 have **not run** in the current blocked attempt.

The required existing 171 tests are also **NOT_RUN**: some isolated fixture tests create optimizers or use backward, and the researcher scope question is pending. Their historical passes are not current execution evidence. If approved, rerun them in an isolated process, never using or applying formal BEST state, and verify BEST/baseline identities before and after.

Recovery needs H at the frozen path and resolution of the test scope. Retain this failed attempt, confirm the new Git baseline for the recovery task, and initialize a separate review run; the current entry deliberately pins its original `5383dfceda6cc64e6907c6953032a14935c0ee46` baseline rather than silently adopting a different HEAD. No automatic retry, alternative-source fallback or next-stage execution is configured.

## Publication boundary

Only code, tests, text, CSV/JSON and modest figures are public. Model/optimizer binaries, raw data, staging cache, wheels and environments are excluded. Large read ledgers remain in `F:\pytorch\Research\outputs\scientific_review\b0_phase_a\<run_id>\`; only absolute path, bytes and SHA are public evidence.

`B0_PHASE_A_ACCEPTED=UNDECIDED`, `TRANSFER_EPOCH_BUDGET_TO_PHASE_B=UNDECIDED`, `PHASE_B_AUTHORIZED=false`.
