# L_ext options — no approved mathematics yet

V1.3 mentions moderate weighting at ≥10/20 mm h⁻¹ and `λ_ext=0.2` as an initial suggestion, not a frozen rule. **EX01:** pixel/sample weight `w(R)` multiplying conditional pinball; must specify thresholds, weights, normalization, label dependence and gradient behavior. **EX02:** auxiliary exceedance loss at 10/20 from probability head/CDF, or an additional head; must define CDF/tails, Brier/log score, coupling and capacity effect. **EX03:** omit L_ext in *first* B0 formal protocol; if later added, rerun B0–B8 consistently under a new protocol. EX03 is cleanest for first-pass ablation fairness if every stage shares the same omission, but it does not meet an eventual extreme-loss design objective by itself.

No method is selected. A selected EX01/EX02 must be identically applied across B0–B8 and versioned before formal experiments. **RESEARCHER_DECISION_REQUIRED.**
