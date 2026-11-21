"""Synthetic-stage two-sided supervision of the existing A point readout."""

from dataclasses import dataclass

import torch
from torch.nn.functional import softplus

from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from .config import get_config
from .total import CandidateLossResult, candidate_loss
from .validation import finite_tensor, graph_zero, same_shape_device


POINT_A20_PROFILE = "A20-BISIDE-V1"
THRESHOLD_MM_H = 20.0
SCALE_MM_H = 20.0
AUX_WEIGHT = 0.1


def profile_identity():
    return {
        "experiment_id": POINT_A20_PROFILE,
        "base_experiment_id": "E0",
        "readout": "DETACHED_EMITTED_P_TIMES_MEAN32_EXPM1_QLOG",
        "strong_truth": "STRICT_FP32_GT_20",
        "threshold_mm_h": THRESHOLD_MM_H,
        "scale_mm_h": SCALE_MM_H,
        "auxiliary_weight": AUX_WEIGHT,
        "denominator": "SEPARATE_PER_CLASS_MEANS_NO_N_VALID_DIVISION",
        "positive_loss": "SOFTPLUS_NEGATIVE_SIGNED_MARGIN",
        "negative_loss": "SOFTPLUS_SIGNED_MARGIN",
        "no_positive": "EXACT_E0",
        "positive_only": "POSITIVE_MEAN_ONLY",
        "physical_precision": "FP64",
    }


@dataclass(frozen=True, kw_only=True)
class PointA20AuxResult(CandidateLossResult):
    n_strong: int
    n_non_strong: int
    s_positive: torch.Tensor
    s_negative: torch.Tensor
    weighted_point_auxiliary: torch.Tensor


def point_a20_aux_loss(output: LogDomainOutput, rate, imerg_valid, yunnan_mask, *, config):
    """Add a training diagnostic for A while retaining the original E0 terms."""
    if config != get_config("E0"):
        raise PermissionError("A20-BISIDE-V1 requires the unchanged E0 loss")
    logit, qlog = output.rain_logit, output.conditional_quantiles_log
    base = candidate_loss(logit, qlog, rate, imerg_valid, yunnan_mask, config=config)
    probability = output.rain_prob
    same_shape_device("point A occurrence probability", probability, logit)
    if not probability.is_floating_point():
        raise ValueError("Point A occurrence probability must be floating-point")
    probability = probability.detach()
    finite_tensor("point A occurrence probability", probability)
    if bool(((probability < 0) | (probability > 1)).any()):
        raise ValueError("Point A occurrence probability must be in [0, 1]")

    valid = (imerg_valid & yunnan_mask)[:, 0]
    strong = rate[:, 0][valid] > THRESHOLD_MM_H
    n_strong = int(strong.sum().item())
    n_non_strong = base.n_valid - n_strong
    s_positive = s_negative = auxiliary = graph_zero(qlog)
    objective = base.training_objective

    if n_strong:
        with torch.autocast(qlog.device.type, enabled=False):
            nodes = qlog.movedim(1, -1)[valid]
            physical = torch.expm1(nodes)
            finite_tensor("valid physical quantiles for point A", physical)
            point = probability[:, 0][valid].double() * physical.mean(dim=-1)
            finite_tensor("valid point A", point)
            margin = (point - THRESHOLD_MM_H) / SCALE_MM_H

            s_positive = softplus(-margin[strong]).sum()
            s_negative = softplus(margin[~strong]).sum()
            auxiliary = s_positive / n_strong
            if n_non_strong:
                auxiliary = auxiliary + s_negative / n_non_strong
            auxiliary = AUX_WEIGHT * auxiliary
            objective = objective + auxiliary
            finite_tensor("weighted point A auxiliary", auxiliary)
            finite_tensor("E0 plus point A auxiliary", objective)

    return PointA20AuxResult(
        experiment_id=POINT_A20_PROFILE,
        s_occ=base.s_occ,
        s_qr=base.s_qr,
        training_objective=objective,
        weighted_quantile_per_valid=base.weighted_quantile_per_valid,
        n_valid=base.n_valid,
        n_rain=base.n_rain,
        conditional_skipped=base.conditional_skipped,
        n_strong=n_strong,
        n_non_strong=n_non_strong,
        s_positive=s_positive,
        s_negative=s_negative,
        weighted_point_auxiliary=auxiliary,
    )
