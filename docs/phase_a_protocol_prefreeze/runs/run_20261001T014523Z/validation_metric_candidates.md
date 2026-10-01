# Validation metric candidates — RESEARCHER_DECISION_REQUIRED

All definitions below pool only eligible 2024 Validation pixels with
`m = IMERG_valid AND Yunnan_evaluation_mask`. Labels are `y=1[R>0.1 mm/h]`.
No metric has been computed on 2025, and no decision threshold was optimized.

## Checkpoint loss A and B

Let D=sum(m) over every validation sample/batch. Accumulate in float64:

\[
 S_o=\sum m\,\alpha_t(1-p_t)^\gamma\operatorname{BCEWithLogits}(z,y),\qquad
 S_q=\sum m y\,\frac1{32}\sum_{i=1}^{32}\rho_{\tau_i}(\log(1+R)-q_i).
\]

Candidate A: `val_core_loss=(S_o+S_q)/D`.
Candidate B: `val_occurrence_loss=S_o/D`, `val_quantile_loss=S_q/D`, then their sum.
A and B are mathematically equivalent with the SAME global valid denominator,
mask, fixed alpha/gamma, quantile precision and quantile-axis mean.
Accumulate raw numerators before division, rather than recovering them from
rounded batch losses. Average batch losses only with weights D_batch/D_total;
an unweighted mean changes the metric when the last batch is smaller or valid
counts differ. D=0 means undefined/reject, not a passing or zero metric.

Example: batches with D=(8,1), core numerators=(24,30) give 54/9=6;
unweighted batch means give (3+30)/2=16.5. Tests verify partition invariance.

Candidate checkpoint action: minimize global val_core_loss; candidate exact-tie
rule is earliest epoch. Neither metric nor tie handling is selected here.
Validation is eval/no_grad with identical AMP/precision policy. Nonfinite output,
nonfinite numerator, invalid causal/QC sample or crossing requires an explicit
failure. Do not silently reduce the frozen validation population.

## Occurrence report

Brier score: sum(m*(p_rain-y)^2)/D, pooled pixel weighting.
AUROC: P(score_positive>score_negative)+0.5*P(tie), pooled valid pixels.
No positive or no negative class makes AUROC undefined; log counts and NA.
AUPRC needs a pinned convention: candidate non-interpolated Average Precision,
AP=sum_k (recall_k-recall_(k-1))*precision_k. Group equal scores at one threshold;
this differs from trapezoidal PR-AUC. No-positive cases report NA plus counts.
The [official AP definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
supports this convention; this audit installs no sklearn dependency.
Always report prevalence because PR summaries depend on it. These pooled pixels
are temporally/spatially dependent; no independent-pixel significance claim is made.

The physical event threshold 0.1 mm/h does not justify probability cutoff 0.1.
`THRESHOLD_NOT_YET_FROZEN`: no scientific basis has been supplied for a binary
probability decision threshold. POD=TP/(TP+FN), FAR=FP/(TP+FP),
CSI=TP/(TP+FN+FP) all require an approved probability cutoff and comparator
(candidate `p_rain >= t_prob`); zero denominators are NA. Do not use a 2024-optimal
cutoff on Final Test without a separately approved calibration/threshold protocol.

## Conditional quantiles

q_i is log1p conditional on R>0.1; tau_i=(i-0.5)/32.
Per-tau conditional pinball: sum(m*y*rho_tau_i(log1p(R)-q_i))/N_rain.
Mean conditional pinball: average over 32 taus of that metric.
Core quantile loss instead divides by D, so L_qr=(N_rain/D)*mean_conditional_pinball.
When N_rain=0, conditional diagnostic is NA; current core skips the rainy term
with differentiable zero. Keep both denominators explicit.
Conditional coverage C_i=sum(m*y*1[log1p(R)<=q_i])/N_rain; compare C_i with tau_i
as a calibration diagnostic. Pin the <= convention and report per-tau counts.
Pooling does not establish conditional calibration for every month/location.
Adjacent crossing count=sum(1[q_(i+1)<=q_i]) must be zero for all emitted grids,
with nonfinite checks and q_1>log1p(0.1) separately required. No posthoc sort.
No complete CRPS: the 32-point conditional support and unresolved tails/drizzle
component do not establish a complete unconditional predictive distribution.

## Deterministic proxy only

d=p_rain*(1/32)*sum_i expm1(q_i) is the probability-weighted 32-point midpoint
threshold-censored diagnostic. It omits 0–0.1 drizzle and unresolved tails and
is not exact E[R]. Optional MAE=sum(m*abs(d-R))/D,
RMSE=sqrt(sum(m*(d-R)^2)/D), signed Bias=sum(m*(d-R))/D are all
`DIAGNOSTIC_PROXY_METRIC`, never posterior-mean precipitation error or exact
expected-rainfall RMSE. No threshold or metric selection is made by this audit.
