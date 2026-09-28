# Unified B0–B8 probability output interface — candidate

For SP04 target `H=W=100`, `rain_logit:[B,1,100,100]`, `conditional_quantiles_raw:[B,32,100,100]`, versioned `tau:[32]`, and `target_valid_mask:[B,1,100,100]` Boolean. Raw quantile tensor's rank i corresponds to τᵢ; its physical/log transform status must be metadata. The mask is an IMERG *data-validity* mask, distinct from the frozen Yunnan evaluation mask and from `R>0.1` conditional-training mask.

`rain_prob=sigmoid(rain_logit)∈[0,1]`; if raw quantiles are in log1p(mm h⁻¹) space, `q_physical=expm1(q_raw)` exactly. Any negative raw value maps to a negative physical quantile, revealing a violated support contract; no implicit clamp, relabeling, or sorting. An approved support parameterization or explicit error policy is needed. If conditional law is `R>0.1`, its physical quantiles should lie above 0.1, again requiring an approved support mechanism.

Raw model outputs, transformed physical conditional quantiles, deterministic diagnostic (mixture median/mean **choice pending**), and exceedance products are distinct named objects. An unchosen tail/CDF rule must produce `NOT_ESTABLISHED`, not silent zeros. Brier/reliability/CRPS need probability forecasts plus observed thresholds and valid/evaluation masks; no training/metric calculation occurred. **RESEARCHER_DECISION_REQUIRED.**
