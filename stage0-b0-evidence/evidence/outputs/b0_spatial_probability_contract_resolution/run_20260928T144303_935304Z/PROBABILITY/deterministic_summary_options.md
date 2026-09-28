# Point estimates for MAE/RMSE/Bias/CC

Conditional median describes `R | R>threshold`, **not** the marginal mixture median. Conditional mean reconstructed from 32 quantiles requires CDF interpolation, both endpoint tails, and integration in **physical R space**; mean of log quantiles is not mean rain. `p·E[R|R>0.1]` is the mean of threshold-censored `R·I(R>0.1)`, not exact `E[R]` if subthreshold rain exists. Exact marginal mixture mean requires `(1−p)E[R|R≤0.1]` too. Exact mixture median requires a specified subthreshold distribution and may be zero or in `(0,0.1]`.

Candidate diagnostic labels must state what they estimate. MAE is aligned to marginal median, RMSE to marginal mean, while Bias/CC can be calculated for either with label retained. CRPS needs a full predictive CDF or declared quantile-integral approximation, including subthreshold and tails. **RESEARCHER_DECISION_REQUIRED.**
