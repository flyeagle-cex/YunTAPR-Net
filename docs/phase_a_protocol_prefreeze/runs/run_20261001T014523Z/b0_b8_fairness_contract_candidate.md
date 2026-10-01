# B0–B8 fairness contract candidate

Status: RESEARCHER_DECISION_REQUIRED. A proposed shared experiment protocol,
not a scientific freeze or training authorization.

Every comparison must pin and share optimizer family/betas/eps/parameter-group
rule, LR policy and schedule clock, core loss family/alpha/gamma/reduction,
probability head architecture/semantics/numerics, checkpoint metric/tie rule,
validation metric definitions/masks/aggregation/threshold protocol, seed policy,
and training budget/early-stop/FinalFit replay policy.
Shared engineering policies also include normalization-fit scope, eligibility,
AMP precision, accumulation weighting/tail policy, clipping and data shuffle.

B0–B3 retain the already specified shared backbone/decoder/SP04/heads/loss family,
with the approved input-information differences. B4–B8 add their protocol-defined
scientific modules; additions do not implicitly authorize new optimizers, losses,
heads, metrics, validation populations or seed/epoch budgets.
If a future B1–B8 changes any shared item, record the reason and reconsider fair
comparison; separate the module effect from protocol/tuning-budget effects.
If memory requires a different physical batch, preserve a researcher-approved
effective-batch/accumulation policy or disclose the confound. Effective batch,
epochs and number of optimizer updates are different notions of training budget;
the chosen fairness criterion must be explicitly approved. Freeze which settings
transfer from B0 and what model-specific tuning is allowed before results are seen.
Checkpoint and all tuning decisions use 2024 Development Validation only; 2025
is sealed from protocol selection. After Phase-A decisions, FinalFit replay must
be approved without 2025 feedback. No model or contract was changed here.
