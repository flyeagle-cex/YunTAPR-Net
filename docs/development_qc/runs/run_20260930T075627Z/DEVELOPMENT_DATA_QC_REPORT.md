# Development Data/QC Closure Audit v1

This independent run uses the frozen science contract at baseline `c5a7a6bb3746275c16cfd66c2a305cbae016aaff`. It is real-data engineering evidence, not a formal experiment or training authorization.

## Required status

- `B0_FORMAL_SCIENTIFIC_CONTRACT = FROZEN`
- `B0_FORMAL_SKELETON_IMPLEMENTED = true`
- `B0_FORMAL_TRAINING_STARTED = false`
- `DEVELOPMENT_DATA_COVERAGE = PARTIAL`
- `B13_PARTIAL_QC_EVIDENCE_READY = true`
- `MASK_AWARE_INPUT_DECISION_REQUIRED = true`
- `NORMALIZATION_EVIDENCE_READY = true`
- `QUANTILE_NUMERICAL_STABILITY_DECISION_REQUIRED = true`
- `FORMAL_TRAINING_AUTHORIZED = false`

## Source coverage

Himawari B13 Development covers 16 months (2023/2024 March–October): 70,560 expected nominal 10-minute slots, 69,313 files, 69,312 readable, 1,247 missing. Among readable files, 69,189 are fully valid, 88 partial and 35 all-fill; 1 file is unreadable. The ten-minute schedule is supported by the previous Stage-0 H09 index and verified source filenames. Per-month all-fill, partial, full-valid, metadata-invalid and causal-usable counts are in `himawari_b13_monthly_coverage.csv`. No other Himawari band is an eligibility gate for B0.

IMERG V07 Final: 704/704 expected days have 48-slot files; 33,792/33,792 half-hour slots have valid Yunnan target pixels. 2025 March–September is coverage inventory only and was excluded from normalization and QC threshold fitting. 2025 October remains observation/inference only, not a supervised blocker.

## Causal pairing and latest-slot fallback

All 23,520 valid Development IMERG windows were classified. Expected latest available: 23,474; latest missing/invalid but older causal exists: 46; no causal frame: 0; time metadata error: 0. Fallback expected-slot reasons: {'MISSING': 46}. `causal_pairing_summary.csv` separately records duplicated observation ends, equal-end ties, inverted intervals and metadata inconsistencies. An older frame is logged as fallback evidence; this run does not approve it as a formal sample.

## Partial B13, SP04 support, candidate impacts

Partial-frame invalid native pixels falling inside the frozen mapped weather domain: 6,987,625; distinct mapped centers affected: 156,123. The aggregated 501×501 frequency map remains in local evidence with SHA256 in the public JSON. Disjoint north/south/west/east/interior zones use a descriptive 25-native-pixel band. This geometry is an audit convention, not a scientific QC threshold. The existing frozen SP04 CSV was read and hash-verified; no mapping was regenerated. `sp04_support_distribution.csv` reports 25/25 through 0/25 for all 10,000 target cells and 3,430 Yunnan cells.

Candidate A requires whole-scene 100% validity; B/C/D are target-cell support 25/25, ≥24/25 and ≥23/25; E retains partial scenes and reports target-cell validity separately. The comparison grain is an exact-latest B13 frame paired to a valid IMERG half-hour window. The 46 older-frame fallback windows are excluded pending researcher approval. All are counterfactual comparisons only. No candidate is selected. Percentages and monthly rainy/dry/heavy-rate-proxy counts are in `qc_candidate_impact.csv`. A rate ≥20 mm/h is only an engineering intensity bin; IMERG intensity alone does not establish convection.

- A_SCENE_100_PERCENT: 23,447/23,474 scenes; 80,423,210/80,515,820 Yunnan cell-observations retained.
- B_CELL_25_OF_25: 23,474/23,474 scenes; 80,503,633/80,515,820 Yunnan cell-observations retained.
- C_CELL_GE24_OF_25: 23,474/23,474 scenes; 80,503,643/80,515,820 Yunnan cell-observations retained.
- D_CELL_GE23_OF_25: 23,474/23,474 scenes; 80,503,644/80,515,820 Yunnan cell-observations retained.
- E_PARTIAL_RETAIN_CELL_VALIDITY_SEPARATE: 23,474/23,474 scenes; 80,503,944/80,515,820 Yunnan cell-observations retained.

The monthly table provides the season comparison. For each candidate, the following Development-wide scene-retention rates are descriptive only:

- A_SCENE_100_PERCENT: DRY=99.59%, RAINY=99.88%, HEAVY_RATE_PROXY_GE20=99.95%.
- B_CELL_25_OF_25: DRY=100.00%, RAINY=100.00%, HEAVY_RATE_PROXY_GE20=100.00%.
- C_CELL_GE24_OF_25: DRY=100.00%, RAINY=100.00%, HEAVY_RATE_PROXY_GE20=100.00%.
- D_CELL_GE23_OF_25: DRY=100.00%, RAINY=100.00%, HEAVY_RATE_PROXY_GE20=100.00%.
- E_PARTIAL_RETAIN_CELL_VALIDITY_SEPARATE: DRY=100.00%, RAINY=100.00%, HEAVY_RATE_PROXY_GE20=100.00%.

A seasonal or convective bias cannot be settled from these counts alone: the missing Himawari slots themselves have no B13 scene, and IMERG rain rate is not a convective classification. The month-by-month counts expose any differential attrition for researcher review.

## Input and quantile decisions still required

The current B0 backbone receives 0.0 K as a placeholder at invalid B13 positions while its validity mask stays outside the backbone. The mask-aware input status above follows from observed mapped-domain partial invalid pixels; it does not add a channel, fill data or alter the science contract.

Decision 8 evidence uses 8,687,773,673 valid 2023 native pixels: mean 271.695348 K, population std 19.904070 K. Robust statistics and 2024 transformed observations are in the normalization JSON and decision note. No normalization rule is frozen.

The float32 quantile stress test includes raw values from −80 to 80, finite gradients and strict monotonicity checks. Very negative raw values produced adjacent equal outputs at float32 precision. The current v2 initialization only addresses the initial forward pass; future parameter updates can recreate equality. Engineering options are documented in `quantile_numerical_stress.json`; no sort, clamp or reparameterization was applied.

## Real integration and reproducibility

2 real Development samples crossed Dataset → B0 → frozen SP04 → probability heads → masked loss → backward with finite results. Focal α=0.25 and γ=2.0 were `ENGINEERING_TEST_ONLY`; no optimizer step or checkpoint was produced. The large per-frame tables, exact centikelvin histograms and invalid-frequency array remain outside GitHub. Their paths, schemas, row counts and SHA256 are in `manifest.json`. Raw Himawari/IMERG fields and the private mask payload are not in this repository.

One exceptional 607 MiB H09 file exceeded the standard 16 MiB B0 staging cap. A separate single-file, 700 MiB bounded, SHA-verified and cleaned audit read confirmed it was fully valid. Its original cap rejection, corrected classification and before/after aggregate hashes are recorded in `b13_oversize_reconciliation.json`; the B0 production staging setting remains 16 MiB.

The first QC candidate table used every B13 frame as its denominator. Its table, report and manifest were preserved in local revision history; `qc_impact_grain_reconciliation.json` records their hashes and the corrected supervised-window denominator.

Researcher decisions remain required for partial QC thresholds, fallback acceptability, mask-aware input handling, Decision 8 normalization and quantile numerical strategy. Formal training remains unauthorized.
