# L_nc candidate

If NC01 is selected: `L_nc=Σ valid pixels Σ_{i=1}^{31} max(q_i−q_{i+1},0) / (31·N_valid)` is one candidate; transformed-vs-log units and whether the mask is all valid or conditional positive need approval. V1.3 `λ_nc=0.05` is explicitly **OPTIONAL**, not frozen. If NC02 guarantees monotonicity in raw space and expm1 is monotonic, crossings cannot occur in physical space, so L_nc can be omitted or kept only as a zero-valued diagnostic. NC03 sorting is not a loss and is not silently applied. **RESEARCHER_DECISION_REQUIRED.**
