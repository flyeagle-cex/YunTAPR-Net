"""Global Validation accounting, independent of checkpoint/early-stop state."""
from __future__ import annotations
import math
import numpy as np
import torch
import torch.nn.functional as F


def grouped_occurrence_metrics(probability, rainy):
    """Non-interpolated AP at END of each exact equal-score group; half-credit AUC ties."""
    p, y = np.asarray(probability, dtype=np.float64), np.asarray(rainy, dtype=np.bool_)
    if p.ndim != 1 or p.shape != y.shape or not len(p) or not np.isfinite(p).all():
        raise ValueError("Finite, nonempty one-dimensional scores and labels required")
    if ((p < 0) | (p > 1)).any():
        raise ValueError("Occurrence probabilities outside [0,1]")
    order = np.argsort(-p, kind="stable")
    scores, labels = p[order], y[order]
    ends = np.r_[np.flatnonzero(scores[:-1] != scores[1:]), len(scores)-1]
    cumulative_tp = np.cumsum(labels, dtype=np.int64)[ends]
    cumulative_count = ends + 1
    positive, negative = int(y.sum()), int((~y).sum())
    if positive:
        delta_tp = np.diff(np.r_[0, cumulative_tp])
        ap = float(np.sum((delta_tp / positive) * (cumulative_tp / cumulative_count), dtype=np.float64))
    else:
        ap = None
    if positive and negative:
        tpr = np.r_[0., cumulative_tp / positive]
        fpr = np.r_[0., (cumulative_count - cumulative_tp) / negative]
        auc = float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2, dtype=np.float64))
    else:
        auc = None
    return {"AUROC": auc, "Average_Precision": ap,
            "AP_convention": "NON_INTERPOLATED_END_OF_EXACT_EQUAL_SCORE_GROUP",
            "AUROC_convention": "TRAPEZOID_GROUPED_ROC_HALF_CREDIT_EXACT_TIES",
            "undefined_reason": "SINGLE_CLASS" if auc is None else None,
            "probability_cutoff_status": "THRESHOLD_NOT_FROZEN"}


class GlobalValidationAccumulator:
    """Accumulate undivided float64 focal/pinball numerators over every valid cell.

    Validation arithmetic is float64, including occurrence BCE, without changing
    the float32/BF16 training forward or adding any loss multiplier. No per-batch
    loss is accepted by this API. Scores are retained on CPU for exact tied ranks.
    """
    def __init__(self):
        self.n_valid = self.n_rain = self.crossing = self.nonfinite = 0
        self.s_occ = self.s_qr = self.brier = 0.0
        self.tau_sum = np.zeros(32, dtype=np.float64)
        self.coverage = np.zeros(32, dtype=np.int64)
        self.proxy_abs = self.proxy_squared = self.proxy_signed = 0.0
        self.scores, self.labels = [], []

    @torch.no_grad()
    def add(self, output, target, imerg_valid, yunnan):
        valid = imerg_valid & yunnan
        if not valid.any():
            raise ValueError("Validation batch has no valid supervised cells")
        if (output.conditional_quantiles_log.dtype != torch.float64
                or output.conditional_quantiles_physical.dtype != torch.float64):
            raise ValueError("Quantile float64 policy violation")
        with torch.autocast(device_type=target.device.type, enabled=False):
            rate = target[valid].double()
            z = output.rain_logit[valid].double()
            p = output.rain_prob[valid].double()
            q = output.conditional_quantiles_log.movedim(1, -1)[valid.squeeze(1)]
            physical = output.conditional_quantiles_physical.movedim(1, -1)[valid.squeeze(1)]
            self.nonfinite += sum(int((~torch.isfinite(t)).sum()) for t in (rate, z, p, q, physical))
            if self.nonfinite or (rate < 0).any():
                raise FloatingPointError("Nonfinite/negative Validation value")
            crossing = int((q[:, 1:] <= q[:, :-1]).sum()) + int((physical[:, 1:] <= physical[:, :-1]).sum())
            self.crossing += crossing
            if crossing:
                raise FloatingPointError("Strict quantile monotonicity failed")
            # Label BEFORE promotion, preserving the production float32 R==0.1 boundary.
            rainy = target[valid] > .1
            bce = F.binary_cross_entropy_with_logits(z, rainy.double(), reduction="none")
            focal = .5 * (1 - torch.exp(-bce)).pow(2.) * bce
            self.s_occ += float(focal.sum(dtype=torch.float64))
            tau = (torch.arange(1, 33, dtype=torch.float64, device=q.device) - .5) / 32
            error = torch.log1p(rate[rainy])[:, None] - q[rainy]
            pinball = torch.maximum(tau * error, (tau - 1) * error)
            self.s_qr += float(pinball.mean(-1).sum(dtype=torch.float64))
            self.tau_sum += pinball.sum(0, dtype=torch.float64).cpu().numpy()
            self.coverage += (rate[rainy, None] <= physical[rainy]).sum(0).cpu().numpy()
            self.brier += float((p - rainy.double()).pow(2).sum(dtype=torch.float64))
            proxy_error = p * physical.mean(-1) - rate
            self.proxy_abs += float(proxy_error.abs().sum(dtype=torch.float64))
            self.proxy_squared += float(proxy_error.square().sum(dtype=torch.float64))
            self.proxy_signed += float(proxy_error.sum(dtype=torch.float64))
            self.n_valid += len(rate)
            self.n_rain += int(rainy.sum())
            self.scores.append(p.cpu().numpy())
            self.labels.append(rainy.cpu().numpy())

    def report(self):
        if not self.n_valid:
            raise ValueError("Empty Validation population")
        ranking = grouped_occurrence_metrics(np.concatenate(self.scores), np.concatenate(self.labels))
        return {"S_occ": self.s_occ, "S_qr": self.s_qr, "D_valid": self.n_valid,
                "global_val_core_loss": (self.s_occ + self.s_qr) / self.n_valid,
                "global_L_occ": self.s_occ / self.n_valid, "global_core_L_qr": self.s_qr / self.n_valid,
                "N_valid": self.n_valid, "N_rain": self.n_rain, "prevalence": self.n_rain / self.n_valid,
                "Brier_Score": self.brier / self.n_valid, **ranking,
                "conditional_mean_pinball": self.s_qr / self.n_rain if self.n_rain else None,
                "per_tau_pinball": (self.tau_sum / self.n_rain).tolist() if self.n_rain else [None] * 32,
                "per_tau_conditional_coverage": (self.coverage / self.n_rain).tolist() if self.n_rain else [None] * 32,
                "coverage_convention": "R <= physical conditional quantile, rainy valid cells only",
                "strict_crossing_count": self.crossing, "nonfinite_count": self.nonfinite,
                "POD": "THRESHOLD_NOT_FROZEN", "FAR": "THRESHOLD_NOT_FROZEN", "CSI": "THRESHOLD_NOT_FROZEN",
                "DIAGNOSTIC_PROXY_METRIC": {"name": "p_rain_times_mean_32_physical_conditional_quantiles",
                    "MAE": self.proxy_abs / self.n_valid, "RMSE": math.sqrt(self.proxy_squared / self.n_valid),
                    "Bias": self.proxy_signed / self.n_valid, "is_exact_expected_precipitation": False},
                "checkpoint_metric": "global_val_core_loss", "numerator_dtype": "float64"}
