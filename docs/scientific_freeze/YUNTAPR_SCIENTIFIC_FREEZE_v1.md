# YunTAPR-Net Scientific Freeze v1

**Authority:** the researcher's explicit Scientific Freeze Synchronization decision on 2026-09-30.  
**Machine contract:** [`config/science_contract_v1.yaml`](../../config/science_contract_v1.yaml).  
**Status:** `B0_FORMAL_SCIENTIFIC_CONTRACT=FROZEN`; `B0_FORMAL_TRAINING_STARTED=false`.  
**Next phase:** `FORMAL_B0_SKELETON_IMPLEMENTATION` only.

This file and its machine contract are the repository's authoritative **scientific execution rules for Decisions D1–D7**. Earlier Stage-0, smoke, formal-readiness, and spatial/probability decision reports remain unchanged as historical evidence. Where one of those reports calls a D1–D7 rule `NOT_YET_FROZEN` or `RESEARCHER_DECISION_REQUIRED`, this later researcher-approved freeze takes precedence. Earlier observations, hashes, data-gap findings, and decisions outside D1–D7 are not erased. A future science change requires an explicitly approved new version; do not silently edit v1. GitHub is the trusted source for this *contract and its executable coordinate/index mapping*; raw observations and the locally frozen, licence-restricted Yunnan mask remain separate data artifacts verified by hash.

## D1 — Time contract · FROZEN

For the formally selected IMERG V07 Final converted CF coordinate `T`, the researcher defines `T` as the start of the native 30-minute precipitation interval `[T,T+30 min)`. `analysis_time=T+30 min`. For B0, choose the latest **completed** Himawari observation with `obs_end ≤ analysis_time`, using decoded observation metadata. No future satellite frame is permitted. A filename's `nominal_time` alone cannot establish this condition. Record `date_created`, but do not use it as proof of historical operational availability or claim that this contract alone establishes real-time replay. A same-`obs_end` tie breaker must be deterministic and logged as an engineering configuration before execution.

## D2 — Data role and IMERG product · FROZEN

The only main supervised label product is **IMERG V07 Final**. The main experiment does not depend on V08; V07/V08 mixed supervision and Early/Late substitution for Final are prohibited. `T_supervised ⊆ T_observation`. The observation goal remains March–October of 2023–2025. The audited local collection lacks 2025-10 V07 Final, so this month is `supervised_eligible=false`, `internal_test_eligible=false`, `inference_eligible=true`. Preserve its Himawari and GFS files. It may support unlabeled inference, workflow replay, or cases; external validation needs an independent gauge, radar, GPM DPR/CMB, or other independently justified reference. This is a statement about the **audited local collection**, not a claim that the product does not exist anywhere.

## D3 — Spatial contract · FROZEN

The SP04 input domain is **97–107°E, 20–30°N**. Actual float32 Himawari and IMERG coordinates and their hashes are the coordinate authority. Do not reconstruct production axes from `arange`, `linspace`, or a nominal step. The full native Himawari input is `[501,501]`, latitude descending, with **all** centers retained in native convolutional context. The actual IMERG target subset is `[100,100]`, latitude ascending, corresponding to rows 10–109 and columns 20–119 of the frozen `[130,140]` grid. The primary evaluation domain remains the GADM 4.1 `CHN.30_1` Yunnan center-in-polygon mask with 3430 cells; no GADM geometry or mask-cell payload is published here.

The authoritative axis values are in [`sp04_coordinate_axes_v1.csv`](../../config/spatial/sp04_coordinate_axes_v1.csv), with float32 bit patterns and source SHA256 in [`sp04_coordinate_manifest_v1.json`](../../config/spatial/sp04_coordinate_manifest_v1.json). The **versioned explicit target-to-native index table** is [`sp04_target_cell_membership_v1.csv`](../../config/spatial/sp04_target_cell_membership_v1.csv), SHA256 `3f4dea000efa0146cec292578bca07c370f897328c933e804346097f8ab9d3fd`. Indices are zero-based original array indices. The map was independently regenerated and compared row-for-row with the prior SP04 geometry candidate.

The approved `[south,north) × [west,east)` rule is numerically defined as follows: infer interior edges by float64 midpoints of the **actual target float32 centers**, extrapolate the two outer edges by half the local center spacing, then **explicitly round the inferred edges to float32 before comparison with the native float32 centers**. This final rounding is part of v1, not an implicit NumPy casting side effect. Every one of the 10,000 target cells then has exactly 5 row × 5 column native centers. Direct aggregation uses source latitude rows 1–500 and longitude columns 0–499; native northmost row 0 and eastmost column 500 are excluded from the *direct target membership*, while remaining inside the full 501×501 native encoder input.

The mask file's separate ancillary `lat_bounds`/`lon_bounds`, when compared in float64, yield 4, 5, or 6 native centers for some cells (11/78/11 along each axis). They do **not** define v1 feature membership. The frozen Yunnan evaluation mask itself is unchanged. The 5×5 relation defines **center membership for learned-feature projection**, not exact physical pixel-footprint equivalence. Extract native features first; then apply the fixed coordinate-defined 5×5 index aggregation to learned features to produce `[B,48,100,100]` from `[B,48,501,501]`, followed by the two probability heads. The arithmetic feature-reduction operator and partial-input feature-mask propagation must be explicitly configured and logged in the skeleton before any training; the researcher did not assign their numerical behavior here. Implicit reshape, bare stride, silent flip/transpose, silent crop, and bare adaptive pooling are prohibited.

## D4 — Split contract · FROZEN

| Phase | Period | Rule |
|---|---|---|
| A Development train | March–October 2023 | Train only on eligible V07 Final labels. |
| A Development validation | March–October 2024 | Architecture, loss, hyperparameters, epoch budget and calibration may be decided within Development only. |
| B Final fit | March–October 2023 **plus** March–October 2024 | Begin only after protocol freeze; the epoch budget must already have been determined in Phase A. |
| Internal Final Test | March–September 2025 | No architecture, loss, normalization, epoch, checkpoint or threshold tuning from 2025. |

Do not randomly split adjacent 30-minute samples. B0–B8 must share this split, final-fit and test protocol. October 2025 remains an observation/inference target and is not silently moved into the internal supervised Test.

## D5 — Missing/QC principles · FROZEN PRINCIPLES

IMERG `0` is a valid no-rain observation. Missing, masked, NaN, declared fill, and declared missing values remain separate from zero. Reject a sample if a required Himawari frame is missing or B13 is all-fill. For partial B13, keep the source validity mask, invalid count and valid fraction; do not automatically reject the entire frame. Each target cell records `support_fraction=N_valid_native_centers/25`. Partial/support numeric thresholds are `DEVELOPMENT_ESTIMATED_PARAMETER`, using only 2023–2024 Development QC; 2025 may not set them. Source missing pixels may not be silently imputed to zero in the encoder; the skeleton must record a mask-aware or other explicitly reviewed treatment.

The main supervised domain is the frozen 3430-cell Yunnan mask. An invalid IMERG target pixel is excluded from loss and metric denominators; it does not require discarding the entire scene. The loss denominator is the **number of valid supervised Yunnan pixels**. An empty-denominator batch must be rejected or skipped with a logged reason. These are execution principles; no dataset, split, threshold fitting, or loss calculation was run in this synchronization.

## D6 — Probability core · FROZEN

For rain rate `R` in mm h⁻¹, the occurrence head represents `p=P(R>0.1)`. The conditional law is **`R | R>0.1`**, so valid `R≤0.1` pixels are occurrence negatives and are excluded from conditional pinball. The model outputs `rain_logit[B,1,100,100]` and 32 conditional log1p-space quantiles `[B,32,100,100]`; `p=sigmoid(rain_logit)`. For `i=1,…,32`, `τ_i=(i−0.5)/32`, ranging from 0.015625 to 0.984375. A monotonic-by-construction parameterization uses a base strictly above `log1p(0.1)` and positive softplus increments, so quantiles remain ordered and on conditional support. No silent clamp or post-hoc sorting is allowed. Floating-point implementations must check those invariants rather than assume softplus cannot round to zero.

The core family is `L=L_occ+L_qr`: Focal BCE occurrence loss and conditional masked pinball. Only valid supervised Yunnan pixels enter the denominator. `focal_alpha` and `focal_gamma` are **`DEVELOPMENT_ESTIMATED_PARAMETER`**, with no prefilled scientific default. The precise quantile-axis reduction and the Focal implementation's numerical conventions are engineering configurations that must be logged before training. `L_KD=0` for B0–B8 core. Keep an `L_ext` interface **disabled** in v1; enabling it later requires a new protocol and a uniform B0–B8 rerun.

The deterministic diagnostic is the **probability-weighted 32-point midpoint threshold-censored mean**: `p × (1/32)Σᵢ expm1(q_i_log1p)`. This is an approximation to the mean of `R·I(R>0.1)`, **not** the exact physical mean, because the `0<R≤0.1` component and finite-quantile tails are not fully determined. `P(R>0.1)=p`; exceedance probabilities outside supported quantiles remain `NOT_ESTABLISHED` until a new tail rule is approved. Do not silently set unsupported tails to zero.

## D7 — Formal B0 backbone · FROZEN

B0 takes a single selected causal B13 frame `[B,1,501,501]`. Its family is a four-level residual U-Net with channels **48 → 96 → 192 → 256**. A residual block is `Conv3×3 → GroupNorm → GELU → Conv3×3 → GroupNorm → GELU → residual`. Downsampling is a learned stride-2 convolution. At each decoder level, explicitly resize to `skip.shape[-2:]`, concatenate the skip feature and enter a residual block. Restore the final native feature to `[B,48,501,501]`, project by the versioned spatial index table to `[B,48,100,100]`, and attach occurrence and conditional-quantile heads. Do not crop silently or change the scientific domain to make tensor shapes convenient. The precise GroupNorm group count, padding/kernel choices consistent with this shape, and decoder resize mode are `ENGINEERING_CONFIG`, not frozen scientific numbers.

B0 must not introduce GFS, DEM, DOTE, DTFM, MEE, ERA5 Teacher, attention, Transformer or recurrent temporal modules. B0–B3 share backbone, decoder, projection, heads and loss family; only Himawari input information changes. No B1–B3 implementation or model training is part of this freeze synchronization.

## Decision status and precedence

| decision_id | name | status | supersedes | remaining_numeric_parameters | evidence |
|---|---|---|---|---|---|
| D1 | Time Contract | FROZEN | Candidate cross-source time binding | None; equal-`obs_end` tie-break is engineering config | Researcher approval; [prior time audit](../../stage0-b0-evidence/evidence/outputs/stage1_b0_formal_readiness_resolution/run_20260928T124313_169375Z/TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md) |
| D2 | Data role / IMERG product | FROZEN | Old October blocking interpretation | None | Researcher approval; [2025-10 evidence](../../stage0-b0-evidence/evidence/outputs/stage1_b0_formal_readiness_resolution/run_20260928T124313_169375Z/GAPS/IMERG_2025_10_DECISION_CARD.md) |
| D3 | Spatial contract | FROZEN | SP04 and projection candidates | Feature-reduction operator: ENGINEERING_CONFIG | Researcher approval; [actual-axis/index manifest](../../config/spatial/sp04_coordinate_manifest_v1.json) |
| D4 | Split contract | FROZEN | Earlier split candidates | Phase A-derived final-fit epoch budget | Researcher approval; [prior split evidence](../../stage0-b0-evidence/evidence/outputs/stage1_b0_formal_readiness_resolution/run_20260928T124313_169375Z/SPLIT/B0_TRAIN_VAL_DECISION.md) |
| D5 | Missing/QC | FROZEN PRINCIPLES | Earlier QC threshold candidates | Partial/support thresholds: DEVELOPMENT_ESTIMATED_PARAMETER | Researcher approval; [prior QC candidate](../../stage0-b0-evidence/evidence/outputs/stage1_b0_formal_readiness_resolution/run_20260928T124313_169375Z/DATA_CONTRACT/b0_missing_qc_contract_candidate.md) |
| D6 | Probability core | FROZEN | Earlier τ, conditioning and loss candidates | Focal α/γ: DEVELOPMENT_ESTIMATED_PARAMETER; quantile-axis reduction: ENGINEERING_CONFIG | Researcher approval; [prior probability analysis](../../stage0-b0-evidence/evidence/outputs/b0_spatial_probability_contract_resolution/run_20260928T144303_935304Z/FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md) |
| D7 | Formal B0 backbone | FROZEN | Smoke small U-Net and candidate architecture | GroupNorm groups and shape implementation: ENGINEERING_CONFIG | Researcher approval; [prior shape analysis](../../stage0-b0-evidence/evidence/outputs/b0_spatial_probability_contract_resolution/run_20260928T144303_935304Z/MODEL/b0_b3_backbone_shape_options.md) |

The scientific contract is frozen; **formal training has not started and is not authorized by this synchronization**. Do not modify raw data, compute formal normalization or a split here, train a model, or tune from 2025 Test. The next authorized activity is `FORMAL_B0_SKELETON_IMPLEMENTATION`, with separate validation before any formal experiment.
