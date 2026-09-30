"""Strict conditional quantiles in the frozen log1p rate domain."""
import math
import torch
from torch.nn import functional as F


def monotonic_quantiles(raw: torch.Tensor, threshold: float) -> torch.Tensor:
    if raw.ndim != 4 or raw.shape[1] != 32:
        raise ValueError("Raw quantile tensor requires [B,32,H,W]")
    increments = F.softplus(raw)
    first = math.log1p(threshold) + increments[:, :1]
    rest = first + torch.cumsum(increments[:, 1:], dim=1)
    q = torch.cat((first, rest), dim=1)
    if not torch.isfinite(q).all() or not (q[:, :1] > math.log1p(threshold)).all() or not (q[:, 1:] > q[:, :-1]).all():
        raise FloatingPointError("Quantile support/strict monotonicity lost at tensor precision")
    return q
