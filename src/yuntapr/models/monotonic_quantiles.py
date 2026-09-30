"""Strict conditional quantiles in the frozen log1p rate domain."""
import math
import torch
from torch.nn import functional as F


def monotonic_quantiles(raw: torch.Tensor, threshold: float, *, epsilon_mono: float = 0.0) -> torch.Tensor:
    """epsilon=0 preserves the historical v1 diagnostic; active heads pass pinned v3 epsilon."""
    if raw.ndim != 4 or raw.shape[1] != 32:
        raise ValueError("Raw quantile tensor requires [B,32,H,W]")
    if epsilon_mono < 0 or not math.isfinite(epsilon_mono):
        raise ValueError("Invalid explicit monotonicity epsilon")
    increments = F.softplus(raw) + epsilon_mono
    first = math.log1p(threshold) + increments[:, :1]
    if epsilon_mono == 0.0:
        rest = first + torch.cumsum(increments[:, 1:], dim=1)
        q = torch.cat((first, rest), dim=1)
    else:
        quantiles = [first]
        for i in range(1, 32):
            quantiles.append(quantiles[-1] + increments[:, i:i+1])
        q = torch.cat(quantiles, dim=1)
    if not torch.isfinite(q).all() or not (q[:, :1] > math.log1p(threshold)).all() or not (q[:, 1:] > q[:, :-1]).all():
        raise FloatingPointError("Quantile support/strict monotonicity lost at tensor precision")
    return q
