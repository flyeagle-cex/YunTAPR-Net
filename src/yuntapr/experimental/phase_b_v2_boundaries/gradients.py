"""Gradient stopping checks, never clipping, repairing, updating or retrying."""
from __future__ import annotations
import torch


def checked_gradients(model: torch.nn.Module, *, empty_rain: bool) -> dict:
    if type(empty_rain) is not bool:
        raise ValueError("Explicit synthetic rainfall case required")
    norms = {}
    for name, parameter in model.named_parameters():
        grad = parameter.grad
        if grad is None or grad.shape != parameter.shape or grad.dtype != torch.float32 or grad.device != parameter.device:
            raise FloatingPointError("Missing/shape/dtype/device gradient: " + name)
        if not bool(torch.isfinite(grad).all()):
            raise FloatingPointError("Nonfinite gradient; stop without repair: " + name)
        norms[name] = float(grad.detach().double().norm().cpu())
    if not norms:
        raise ValueError("No parameters")
    occurrence = {k:v for k,v in norms.items() if k.startswith("heads.occurrence.")}
    quantile = {k:v for k,v in norms.items() if k.startswith("heads.quantile.")}
    if len(occurrence) != 2 or len(quantile) != 2 or not any(v > 0 for v in occurrence.values()):
        raise FloatingPointError("Dual head gradient structure or occurrence signal absent")
    if empty_rain and any(v != 0 for v in quantile.values()):
        raise FloatingPointError("Dry-only batch must have connected zero quantile head gradient")
    if not empty_rain and not any(v > 0 for v in quantile.values()):
        raise FloatingPointError("Mixed-rain fixture has no quantile head signal")
    return {"parameter_tensors":len(norms),"missing":0,"nonfinite":0,
            "occurrence_head_norms":occurrence,"quantile_head_norms":quantile,
            "zero_tensors":[k for k,v in norms.items() if v == 0],
            "empty_rain_connected_zero":empty_rain,"optimizer_steps":0}
