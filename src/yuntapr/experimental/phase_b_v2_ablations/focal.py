"""Stable candidate focal numerator, explicitly separate from normalization."""
from __future__ import annotations
import torch
from torch.nn import functional as F
from .config import finite_number
from .validation import boolean_mask, finite_tensor, graph_zero, occurrence_logits


def occurrence_numerator(logit: torch.Tensor, rainy: torch.Tensor, valid: torch.Tensor,
                         *, alpha: float, gamma: float) -> torch.Tensor:
    alpha, gamma = finite_number("alpha", alpha), finite_number("gamma", gamma)
    if not 0 <= alpha <= 1 or gamma < 0:
        raise ValueError("alpha in [0,1] and gamma>=0 required")
    occurrence_logits(logit)
    boolean_mask("rainy hard labels", rainy, logit)
    boolean_mask("valid", valid, logit)
    dtype = torch.float64 if logit.dtype == torch.float64 else torch.float32
    with torch.autocast(logit.device.type, enabled=False):
        if not bool(valid.any()):
            return graph_zero(logit, dtype=dtype)
        # FP16/BF16 inputs retain gradients through this cast; BCE computes FP32.
        logits, labels = logit[valid].to(dtype), rainy[valid]
        bce = F.binary_cross_entropy_with_logits(logits, labels.to(dtype), reduction="none")
        alpha_t = torch.where(labels, torch.full_like(logits, alpha), torch.full_like(logits, 1 - alpha))
        if gamma == 0:
            terms = alpha_t * bce  # deliberately .5*BCE for E1, not plain BCE
        else:
            pt = torch.exp(-bce)
            terms = alpha_t * (1 - pt).pow(gamma) * bce
        result = terms.sum()
    finite_tensor("occurrence numerator", result)
    return result
