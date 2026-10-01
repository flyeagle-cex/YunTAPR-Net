# Scheduler candidates — RESEARCHER_DECISION_REQUIRED

| Candidate | Explicit candidate definition | FINALFIT_REPLAY_COMPLEXITY | Reason |
|---|---|---|---|
| Constant LR | eta(u)=eta0 for every optimizer update | LOW | No validation-triggered schedule; still pin steps, budget and LR |
| Warmup + Cosine | linear eta0*(u+1)/W during W updates; then eta_min+(eta0-eta_min)*(1+cos(pi*(u-W)/(U-W)))/2 | MEDIUM | Must define update-vs-epoch clock, W, U, eta_min and replay alignment |
| ReduceLROnPlateau | after each global 2024 validation metric, reduce LR by factor after patience non-improvements | HIGH | FinalFit consumes 2023+2024 and has no same held-out 2024 control signal |

Warmup candidates 0, 1 or 3 epochs, minimum LR ratio 0, 0.01 or 0.1; no choice.
Cosine formula assumes W<U and a pinned endpoint/step-index convention;
W=0 skips warmup. Updates depend on accumulation; changing effective batch
changes U even if epochs are equal. Pin whether FinalFit replays normalized epoch
progress or an absolute update sequence; these are not automatically equivalent.

Plateau candidates factor 0.1 or 0.5, patience 2 or 3 validation calls, minimum
LR 1e-6 or 1e-5; no choice. Metric, min_delta/threshold mode, cooldown, ordering
relative to validation and early stopping must be pinned. In Phase B, directly
feeding 2024 into the same scheduler would reuse training data as control data.
Possible future approved replay options are a recorded LR sequence mapped to
progress, or a fully predetermined replacement schedule; neither is selected.
Never use 2025 to trigger changes. Complexity labels are engineering assessments
of the proposed replay conditions, not measured model-performance results.
