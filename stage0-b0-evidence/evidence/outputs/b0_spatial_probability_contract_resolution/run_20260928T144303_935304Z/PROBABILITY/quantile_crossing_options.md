# Quantile crossing options

**NC01 independent outputs + penalty:** quantile rank i retains exact τᵢ identity under pinball supervision. Candidate `L_nc=mean_valid Σᵢ relu(qᵢ−qᵢ₊₁)`; soft penalty permits crossings and weight must be selected. V1.3 lists optional `λ_nc=0.05`, not frozen.

**NC02 monotonic parameterization:** `q₁=base`, `qᵢ=qᵢ₋₁+softplus(δᵢ)` for i>1, with numerically stable softplus. Outputs are ordered by construction, so `L_nc` is mathematically zero and usually unnecessary; parameter sharing constrains expressiveness and may over-smooth rare high tail. The base must obey approved physical/log-domain support. Exact rank semantics still depend on pinball at each τ. No evidence here that GPROF-IR uses this parameterization.

**NC03 post-hoc sort:** sorting independent outputs after training enforces order numerically but reassigns predictions to τ ranks. This can alter calibration/quantile identity and conceal training defects. It is **not a default**; if considered, it needs a separate validation protocol and explicit declaration. No silent sort in any test or proposed interface.

Researcher chooses mechanism, penalty formula/normalization, and weight. **RESEARCHER_DECISION_REQUIRED.**
