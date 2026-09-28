"""Synthetic-only calculations for reviewing, not approving, probability contracts."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def occurrence_target(rain: torch.Tensor, valid: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    if rain.shape != valid.shape:
        raise ValueError("rain and validity shapes differ")
    return rain > 0.1, valid.bool()


def conditional_mask(rain: torch.Tensor, valid: torch.Tensor) -> torch.Tensor:
    """Candidate R>0.1 conditioning, not a frozen scientific choice."""
    return valid.bool() & (rain > 0.1)


def pinball(y: torch.Tensor, q: torch.Tensor, tau: torch.Tensor) -> torch.Tensor:
    if q.ndim != 4 or y.ndim != 4 or tau.shape != (q.shape[1],):
        raise ValueError("expected y[B,1,H,W], q[B,Q,H,W], tau[Q]")
    if y.shape[0] != q.shape[0] or y.shape[2:] != q.shape[2:] or y.shape[1] != 1:
        raise ValueError("target/output spatial shape mismatch")
    u = y - q
    t = tau.reshape(1, -1, 1, 1)
    return torch.maximum(t * u, (t - 1) * u)


def stable_rain_probability(logit: torch.Tensor) -> torch.Tensor:
    return torch.sigmoid(logit)


def monotonic_quantiles(base: torch.Tensor, increments: torch.Tensor) -> torch.Tensor:
    if base.ndim != 4 or base.shape[1] != 1 or increments.shape[0] != base.shape[0] or increments.shape[2:] != base.shape[2:]:
        raise ValueError("base/increment dimensions incompatible")
    return torch.cat((base, base + torch.cumsum(F.softplus(increments), dim=1)), dim=1)


def inverse_log1p(raw: torch.Tensor) -> torch.Tensor:
    """Exact inverse; negative predictions remain visible, never silently clamped."""
    return torch.expm1(raw)
