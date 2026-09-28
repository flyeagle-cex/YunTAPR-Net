# Decisions required before B0 formal experiment

1. Confirm SP04 97–107°E/20–30°N as the exact formal input domain, including whether bounds denote native centers or physical cell edges and how outside-context coverage is handled. This run verifies geometry but does **not** freeze the bbox.
2. Choose SA01–SA05 native→target operator; specify pixel/target footprints, boundary ownership, float tolerance, missing/valid support, edge behavior, projection point, padding/crop, and versioned B0–B8 index contract.
3. Choose conditional rain threshold (`R>0` or `R>0.1`) and treatment of valid drizzle `0<R≤0.1`; clarify full physical mean versus threshold-censored mean.
4. Approve exact 32 τ values (Q01/Q02/Q03 or sourced alternative), noncrossing method, quantile support transform, and whether outputs are physical or log1p.
5. Approve complete focal loss (γ, α, weighting, reduction), pinball reduction/τ quadrature, L_det definition, L_ext option/weights, and optional L_nc mechanism/weight. `L_KD=0` stays in B0–B8 core.
6. Approve full-mixture CDF/tail/interpolation/subthreshold policy for CRPS and exceedance probabilities, and a clearly labeled point estimate for MAE/RMSE/Bias/CC.
7. Approve four-level backbone's exact padding, skip matching, projection location and fairness/capacity accounting; then resolve independent prior readiness blockers (including time binding and missing 2025 October Final coverage) before any B0 formal run.

No item above was silently frozen. **B0_FORMAL_TRAINING_STARTED=false.**
