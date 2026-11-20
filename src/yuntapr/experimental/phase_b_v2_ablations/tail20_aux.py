"""Fixed strong-rain auxiliary objective for synthetic preparation."""

from dataclasses import dataclass

import torch

from .config import get_config
from .pinball import frozen_taus
from .total import CandidateLossResult, candidate_loss
from .validation import finite_tensor, graph_zero


TAIL20_PROFILE = "TAIL20-AUX-V1"
THRESHOLD_MM_H = 20.0
PHYSICAL_SCALE_MM_H = 20.0
LAMBDA_TAIL = 1.0


def profile_identity():
    return dict(experiment_id=TAIL20_PROFILE, base_experiment_id="E0", lambda_tail=LAMBDA_TAIL,
                strong_threshold_mm_h=THRESHOLD_MM_H, physical_scale_mm_h=PHYSICAL_SCALE_MM_H,
                nodes=32, denominator="N_VALID", truth_comparison="STRICT_FP32_GT",
                objective="E0 + SUM_STRONG_VALID(MEAN32(PHYSICAL_PINBALL_OVER20))/N_VALID",
                empty="EXACT_E0", physical_precision="FP64")


@dataclass(frozen=True, kw_only=True)
class Tail20AuxResult(CandidateLossResult):
    s_tail: torch.Tensor
    n_strong: int


def tail20_aux_loss(logit, qlog, rate, imerg_valid, yunnan_mask, *, config):
    """Retain the E0 objective and add a physical loss on valid strong truth."""
    if config != get_config("E0"):
        raise PermissionError("TAIL20-AUX-V1 requires the unchanged E0 objective")
    base = candidate_loss(logit, qlog, rate, imerg_valid, yunnan_mask, config=config)
    # candidate_loss has already validated the mask, target dtype and tensor shapes.
    strong = imerg_valid & yunnan_mask & (rate > THRESHOLD_MM_H)
    n_strong = int(strong.sum().item())
    numerator = graph_zero(qlog)
    objective = base.training_objective
    weighted = base.weighted_quantile_per_valid

    if n_strong:
        with torch.autocast(qlog.device.type, enabled=False):
            targets = rate[strong].double()[:, None]
            nodes = qlog.movedim(1, -1)[strong.squeeze(1)]
            physical = torch.expm1(nodes)
            finite_tensor("selected strong-rain physical quantiles", physical)
            errors = (targets - physical) / PHYSICAL_SCALE_MM_H
            finite_tensor("selected strong-rain physical errors", errors)
            tau = frozen_taus(qlog.device)
            numerator = torch.maximum(tau * errors, (tau - 1.0) * errors).mean(dim=-1).sum()
            finite_tensor("strong-rain auxiliary numerator", numerator)
            auxiliary = LAMBDA_TAIL * numerator / base.n_valid
            objective = objective + auxiliary
            weighted = weighted + auxiliary
            finite_tensor("E0 plus strong-rain objective", objective)
            finite_tensor("weighted conditional objective", weighted)

    return Tail20AuxResult(
        experiment_id=TAIL20_PROFILE,
        s_occ=base.s_occ,
        s_qr=base.s_qr,
        training_objective=objective,
        weighted_quantile_per_valid=weighted,
        n_valid=base.n_valid,
        n_rain=base.n_rain,
        conditional_skipped=base.conditional_skipped,
        s_tail=numerator,
        n_strong=n_strong,
    )
