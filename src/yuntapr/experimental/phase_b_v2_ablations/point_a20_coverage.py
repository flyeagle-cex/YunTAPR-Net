"""Extend the existing A20 negative term to valid no-strong-rain batches."""

from dataclasses import replace

import torch
from torch.nn.functional import softplus

from yuntapr.models.quantile_v2.outputs import LogDomainOutput
from .point_a20_aux import AUX_WEIGHT, SCALE_MM_H, THRESHOLD_MM_H, point_a20_aux_loss
from .point_a20_aux import profile_identity as original_identity
from .validation import finite_tensor


COVERAGE_PROFILE = "A20-NEG-COVERAGE-V1"


def profile_identity():
    return dict(original_identity(), experiment_id=COVERAGE_PROFILE, no_positive="NEGATIVE_MEAN_IF_VALID")


def point_a20_coverage_loss(output: LogDomainOutput, rate, imerg_valid, yunnan_mask, *, config):
    original = point_a20_aux_loss(output, rate, imerg_valid, yunnan_mask, config=config)
    if original.n_strong or not original.n_non_strong:
        return replace(original, experiment_id=COVERAGE_PROFILE)

    qlog = output.conditional_quantiles_log
    valid = (imerg_valid & yunnan_mask)[:, 0]
    with torch.autocast(qlog.device.type, enabled=False):
        nodes = torch.expm1(qlog.movedim(1, -1)[valid])
        finite_tensor("valid physical quantiles for point A", nodes)
        point = output.rain_prob.detach()[:, 0][valid].double() * nodes.mean(dim=-1)
        finite_tensor("valid point A", point)
        negative = softplus((point - THRESHOLD_MM_H) / SCALE_MM_H).sum()
        auxiliary = AUX_WEIGHT * (negative / original.n_non_strong)
        objective = original.training_objective + auxiliary
        finite_tensor("weighted point A auxiliary", auxiliary)
        finite_tensor("E0 plus point A auxiliary", objective)
    return replace(original, experiment_id=COVERAGE_PROFILE, training_objective=objective,
                   s_negative=negative, weighted_point_auxiliary=auxiliary)
