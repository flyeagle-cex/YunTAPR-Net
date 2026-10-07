"""Strict conditional quantiles in the frozen log1p rate domain."""
import math
from contextlib import nullcontext
import torch
from torch.nn import functional as F


def monotonic_quantiles(raw: torch.Tensor, threshold: float, *, epsilon_mono: float = 0.0,
                        accumulation_dtype: torch.dtype = torch.float32) -> torch.Tensor:
    """Active v4 uses float64; default float32 preserves historical v1/v3 diagnostics."""
    if raw.ndim != 4 or raw.shape[1] != 32:
        raise ValueError("Raw quantile tensor requires [B,32,H,W]")
    if epsilon_mono < 0 or not math.isfinite(epsilon_mono):
        raise ValueError("Invalid explicit monotonicity epsilon")
    if accumulation_dtype not in (torch.float32, torch.float64):
        raise ValueError("Unsupported monotonic accumulator dtype")
    guard = (torch.autocast(device_type=raw.device.type, enabled=False)
             if raw.device.type in ("cpu", "cuda") else nullcontext())
    with guard:
        converted = raw.to(dtype=accumulation_dtype)
        if not torch.isfinite(converted).all():
            raise FloatingPointError("QUANTILE_MONOTONICITY_LOST: nonfinite raw quantile tensor")
        increments = F.softplus(converted) + epsilon_mono
        first = math.log1p(threshold) + increments[:, :1]
        if accumulation_dtype == torch.float32 and epsilon_mono == 0.0:
            rest = first + torch.cumsum(increments[:, 1:], dim=1)
            q = torch.cat((first, rest), dim=1)
        else:
            quantiles = [first]
            for i in range(1, 32):
                quantiles.append(quantiles[-1] + increments[:, i:i+1])
            q = torch.cat(quantiles, dim=1)
        if not torch.isfinite(q).all() or not (q[:, :1] > math.log1p(threshold)).all() or not (q[:, 1:] > q[:, :-1]).all():
            raise FloatingPointError("QUANTILE_MONOTONICITY_LOST: support or strict order lost at tensor precision")
    return q
