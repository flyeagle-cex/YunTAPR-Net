# Occurrence loss candidate

For valid IMERG rate `R`, `z=I(R>0.1 mm h⁻¹)` (strict greater-than; `R=0.1` has z=0). Let `p=sigmoid(logit)`, `p_t=p` when z=1 else `1−p`, and `α_t=α` when z=1 else `1−α`. Focal BCE candidate: `L_occ = mean_valid[−α_t(1−p_t)^γ log(p_t)]`, implemented with stable logits/BCE rather than raw log near 0/1. Standard BCE is the γ=0/unweighted comparison, **not** a replacement of V1.3's Focal BCE direction.

Neither γ nor α was found frozen in local evidence. Do not assume 2 or 0.25. Positive/negative class reweighting, mask denominator, empty batch, exact transform, and occurrence-family weight require approval. Valid zero is a negative example; missing is excluded. **RESEARCHER_DECISION_REQUIRED.**
