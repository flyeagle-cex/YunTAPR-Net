"""Isolated physical-space conditional objective candidate, without an executor."""

from dataclasses import replace

import torch

from .config import get_config
from .pinball import frozen_taus
from .total import candidate_loss, combine_numerators
from .validation import finite_tensor, graph_zero, supervision


PHYSICAL_PROFILE = "PHYSICAL_PINBALL20_V1"


def profile_identity():
    return {
        "experiment_id": PHYSICAL_PROFILE,
        "base_experiment_id": "E0",
        "alpha": 0.5,
        "gamma": 2.0,
        "lambda_q": 1.0,
        "tau_nodes": 32,
        "tau_rule": "(k-0.5)/32; k=1..32",
        "physical_scale_mm_h": 20.0,
        "training_numerator": "SUM_RAINY_VALID(MEAN32(rho_tau((rate-expm1(qlog))/20)))",
        "training_objective": "(S_occ+S_physical)/N_valid",
        "scientific_s_qr": "ORIGINAL_LOG_UNWEIGHTED_32_NODE_NUMERATOR",
        "arithmetic": "FP64_EXPM1_NO_CLAMP_NONFINITE_FAIL",
    }


def physical_pinball_loss(logit, qlog, rate, imerg_valid, yunnan_mask, *, config):
    """Use physical Pinball/20 for training and retain log-space diagnostics."""
    if config != get_config("E0"):
        raise PermissionError("PHYSICAL_PINBALL20_V1 requires E0 occurrence loss and lambda1")
    base = candidate_loss(logit, qlog, rate, imerg_valid, yunnan_mask, config=config)
    target = supervision(logit, qlog, rate, imerg_valid, yunnan_mask)
    with torch.autocast(qlog.device.type, enabled=False):
        physical = torch.expm1(qlog)
        finite_tensor("physical quantiles", physical)
        numerator = graph_zero(qlog)
        if target.n_rain:
            errors = (target.clean_rate.double() - physical) / 20.0
            finite_tensor("physical normalized errors", errors)
            selected = errors.movedim(1, -1)[target.rainy_valid.squeeze(1)]
            tau = frozen_taus(qlog.device)
            numerator = torch.maximum(tau * selected, (tau - 1.0) * selected).mean(dim=-1).sum()
        finite_tensor("physical quantile numerator", numerator)
        objective = combine_numerators(base.s_occ, numerator, base.n_valid, lambda_q=1.0)
    return replace(
        base,
        experiment_id=PHYSICAL_PROFILE,
        training_objective=objective,
        weighted_quantile_per_valid=numerator / base.n_valid,
    )
