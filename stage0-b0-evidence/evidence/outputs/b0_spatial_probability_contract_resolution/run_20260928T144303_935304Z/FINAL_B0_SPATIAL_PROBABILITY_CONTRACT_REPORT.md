# FINAL B0 Spatial + Probability Contract Resolution Report

**Run:** `run_20260928T144303_935304Z`  
**Spatial status:** `SPATIAL_CONTRACT_READY_FOR_RESEARCHER_DECISION`  
**Probability status:** `PROBABILITY_CONTRACT_READY_FOR_RESEARCHER_DECISION`  
**B0_FORMAL_TRAINING_STARTED:** `false`

## Answers A–M

**A. Geometry:** 501×501 native axis centers span 20–30°N and 97–107°E inclusive, with latitude descending. Actual IMERG centers inside SP04 make 100×100, latitude ascending, with inferred cell edges close to the source endpoints. Under explicit raw half-open cell membership, **all 10,000 target cells contain exactly 25 native centers** ({25: 10000}); strict interiors contain 4×4 and near-boundary centers require a declared ownership rule. All 3430 frozen Yunnan evaluation cells lie in target subset.

**B. Integer mapping:** **yes, an exact 5×5 index mapping exists for these actual arrays under the explicitly stated raw half-open `[lower,upper)` rule**. It assigns native latitude rows 1–500 and longitude columns 0–499; northmost row 0 and eastmost column 500 are excluded. A direct 501×501 reshape is impossible, and no endpoint-ownership or physical-footprint choice is yet approved. The actual-coordinate index table is deterministic for each stated rule; do not replace it with an assumed generic stride-5 reshape.

**C. Candidate recommendation:** investigate SA05 coordinate-defined hybrid / SA04 native encoder plus coordinate-aware target projection for interpretability and B0–B8 consistency. It is an engineering recommendation, not approval or performance result.

**D. SP04 freeze:** source/target containment and mask retention are verified; exact domain-edge semantics, native→target mapping and padding remain undecided. Thus SP04 is **not yet safe to mark a complete formal input/projection contract**.

**E. Local τ source:** GPROF-IR manuscript mentions 32 quantiles and quantile regression, but bounded local search found no exact 32 τ vector or matching dual-head conditional law.

**F. τ candidates:** Q01 midpoint uniform reaches farther into tails; Q02 interior uniform gives more endpoint gap; Q03 illustrative upper-tail-dense grid shifts coverage and needs nonuniform CRPS quadrature. None frozen.

**G. Conditioning:** `R>0.1` aligns algebraically with occurrence `P(R>0.1)` for exceedances above 0.1. `R>0` without a drizzle component does not. Even `R>0.1` does not make `p·conditional_mean` an exact physical mean if drizzle is nonzero.

**H. Crossing:** NC01 independent+penalty, NC02 positive increments, NC03 post-hoc sorting; NC03 risks quantile-rank/calibration changes and is not default.

**I. Loss:** `L_qr` pinball family and `L_KD=0` for B0–B8 are specified; exact τ/reduction/conditioning and `L_det`, focal γ/α, `L_ext` mathematics/weights, optional `L_nc=0.05` remain researcher decisions. `λ_ext=0.2` is only initial suggestion.

**J. Tensor candidate:** rain logit `[B,1,100,100]`, conditional quantiles `[B,32,100,100]`, τ `[32]`, data-validity mask `[B,1,100,100]`; explicit sigmoid/log1p inverse, no silent clamp/sort.

**K. Metrics/products:** point diagnostic must be labeled mixture median/mean or conditional/censored diagnostic; full CRPS needs full CDF/subthreshold/tails or declared approximation. At 0.1, exceedance is p. At 1/5/10/20, use p·[1−F₊(r)] only after conditioning/CDF interpolation/tails are approved. Brier/reliability use threshold event indicators on valid Yunnan cells. Above max quantile: `NOT_ESTABLISHED` pending tail rule.

**L. Already frozen:** GADM4.1 Yunnan center mask (3430), true IMERG coordinates, 0≠missing, raw read-only, `obs_end≤analysis_time`, 2023–2025 March–October and 2025 Final Test, `L_KD=0` in B0–B8 core, and researcher direction of shared B0–B8 domain/dual-head probability. Geometry evidence can be registered, not a new silent scientific mapping freeze.

**M. Researcher decision:** SP04 exact domain and mapping, τ, conditioning/drizzle, loss math/weights, crossing/support, CDF/tails/point estimate, padding/projection/backbone, and remaining prior formal-readiness blockers. See `RESEARCHER_DECISIONS_REQUIRED.md`.

## Superseded draft preserved

`run_20260928T144036_365388Z` is an earlier diagnostic draft. Its prose incorrectly suggested that half-open native-center counts vary across target cells. It is preserved as traceable history and is **not** the final decision package. Actual-array recalculation in this run shows exactly 25 under the stated half-open rule for every target cell; the boundary/scientific-approval caveat remains.

## Execution and evidence

No science resampling, training, dataset, split, statistics, benchmark or next-stage run was performed. `SPATIAL/` contains exact axis arrays and 10,000-cell index mapping; `PROBABILITY/` contains definitions/candidates; `MODEL/` contains shape/fairness review; `DECISIONS/` contains researcher decision briefs. `logs/tests.txt` records focused automated checks. Previous runs were only read.

B0 spatial/probability contract resolution complete.  
No formal model training was started.  
SP04 geometry was evaluated using actual coordinate arrays.  
No provisional spatial projection was silently frozen.  
No unspecified quantile or loss hyperparameter was silently frozen.  
The final scientific contract remains subject to explicit researcher approval.
