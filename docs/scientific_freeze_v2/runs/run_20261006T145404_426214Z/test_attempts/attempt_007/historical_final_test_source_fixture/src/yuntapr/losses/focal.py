"""Numerically stable logit focal BCE with no scientific alpha/gamma default."""
import torch
from torch.nn import functional as F


def focal_bce_sum(logit: torch.Tensor, rainy: torch.Tensor, valid: torch.Tensor,
                  alpha: float | None, gamma: float | None) -> torch.Tensor:
    if alpha is None or gamma is None:
        raise ValueError("focal_alpha and focal_gamma are REQUIRED_DEVELOPMENT_PARAMETER")
    if not 0 <= alpha <= 1 or gamma < 0:
        raise ValueError("Focal parameters outside valid numeric domain")
    label = rainy.to(logit.dtype)
    bce = F.binary_cross_entropy_with_logits(logit, label, reduction="none")
    pt = torch.exp(-bce)
    weight = torch.where(rainy, alpha, 1 - alpha)
    return (weight * (1 - pt).pow(gamma) * bce * valid).sum()
