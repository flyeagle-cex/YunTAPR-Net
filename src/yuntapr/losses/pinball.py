"""Conditional log1p pinball summed over rainy valid Yunnan pixels."""
import torch


def frozen_taus(device=None, dtype=torch.float32) -> torch.Tensor:
    return (torch.arange(1, 33, device=device, dtype=dtype) - 0.5) / 32


def pinball_sum(qlog: torch.Tensor, log_rain: torch.Tensor, rainy_valid: torch.Tensor,
                quantile_axis_reduction: str) -> torch.Tensor:
    if quantile_axis_reduction != "mean":
        raise ValueError("Unsupported explicit quantile axis reduction")
    if qlog.ndim != 4 or qlog.shape[1] != 32 or log_rain.shape != qlog[:, :1].shape:
        raise ValueError("Conditional pinball tensor shape mismatch")
    taus = frozen_taus(qlog.device, qlog.dtype).reshape(1, 32, 1, 1)
    error = log_rain - qlog
    per_pixel = torch.maximum(taus * error, (taus - 1) * error).mean(dim=1, keepdim=True)
    return (per_pixel * rainy_valid).sum()
