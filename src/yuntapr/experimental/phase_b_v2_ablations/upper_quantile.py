"""One proposed upper-quantile profile, with unweighted diagnostics retained."""

from dataclasses import replace

import torch

from .config import get_config
from .pinball import frozen_taus
from .total import candidate_loss, combine_numerators
from .validation import finite_tensor, graph_zero, supervision


UNIFORM = "UNIFORM"
MILD_PROFILE = "UQ_MILD_V1"


def mild_weights(device=None):
    """Fixed w(tau)=2(1+tau)/3 on the original 32 midpoint nodes."""
    return (1.0 + frozen_taus(device)) / 1.5


def profile_identity():
    return {
        "experiment_id": MILD_PROFILE,
        "base_experiment_id": "E0",
        "alpha": 0.5,
        "gamma": 2.0,
        "lambda_q": 1.0,
        "tau_nodes": 32,
        "tau_rule": "(k-0.5)/32; k=1..32",
        "weight_rule": "2*(1+tau)/3",
        "normalization": "DIVIDE_BY_SUM_OF_FIXED_POSITIVE_WEIGHTS",
        "scientific_s_qr": "ORIGINAL_UNWEIGHTED_32_NODE_NUMERATOR",
    }


def upper_quantile_loss(logit, qlog, rate, imerg_valid, yunnan_mask, *, config):
    if config != get_config("E0"):
        raise PermissionError("UQ_MILD_V1 requires the unchanged E0 occurrence loss and lambda1")
    base = candidate_loss(logit, qlog, rate, imerg_valid, yunnan_mask, config=config)
    target = supervision(logit, qlog, rate, imerg_valid, yunnan_mask)
    weighted = graph_zero(qlog)
    if target.n_rain:
        with torch.autocast(qlog.device.type, enabled=False):
            errors = torch.log1p(target.clean_rate.double()) - qlog
            selected = errors.movedim(1, -1)[target.rainy_valid.squeeze(1)]
            tau = frozen_taus(qlog.device)
            nodes = torch.maximum(tau * selected, (tau - 1.0) * selected)
            weights = mild_weights(qlog.device)
            weighted = (nodes * weights).sum(dim=-1).sum() / weights.sum()
    finite_tensor("upper-quantile training numerator", weighted)
    objective = combine_numerators(base.s_occ, weighted, base.n_valid, lambda_q=1.0)
    # s_qr and its scientific mean keep their original, unweighted semantics.
    return replace(
        base,
        experiment_id=MILD_PROFILE,
        training_objective=objective,
        weighted_quantile_per_valid=weighted / base.n_valid,
    )
