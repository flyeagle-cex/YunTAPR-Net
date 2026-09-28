# Conditional rain is an unresolved scientific definition

Let `R≥0` be physical precipitation and `p=P(R>0.1)`. The phrase *positive rain* could mean `R>0` or `R>0.1` mm h⁻¹. For a mathematically consistent two-part exceedance formula at `r>0.1`, define `F₊(r)=P(R≤r | R>0.1)`; then `P(R>r)=p[1−F₊(r)]`, and at `r=0.1`, `P(R>0.1)=p` exactly. Conditional pinball pixels would be valid `R>0.1`; valid `0≤R≤0.1` still train the occurrence head as 0.

If instead `F₊=P(R≤r | R>0)` while `p=P(R>0.1)`, the formula above is generally wrong: the conditional law includes `0<R≤0.1` drizzle while the mixing weight excludes it. A separate `P(R>0)` and subthreshold component would be required. Even with conditioning on `R>0.1`, `p E[R|R>0.1]` is **the expectation of threshold-censored rain** (`R·I(R>0.1)`), not exact physical `E[R]`, which also includes `(1−p)E[R|R≤0.1]`. Do not silently zero drizzle or label the censored value the full physical mean.

**Candidate recommendation:** conditional law `R>0.1` for algebraic consistency with the occurrence head; researcher must approve the treatment of subthreshold rain and deterministic-mean label. **RESEARCHER_DECISION_REQUIRED.**
