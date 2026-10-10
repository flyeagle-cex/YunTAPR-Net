"""FP64 conditional pinball in log1p(mm/h), fixed 32-tau mean then sum."""
from __future__ import annotations
import torch
from .validation import boolean_mask, finite_tensor, graph_zero, image_tensor, quantiles, same_shape_device


def frozen_taus(device: torch.device | str | None = None) -> torch.Tensor:
    return (torch.arange(1, 33, device=device, dtype=torch.float64) - .5) / 32


def _pinball_from_errors(error: torch.Tensor, rainy_valid: torch.Tensor) -> torch.Tensor:
    """Private arithmetic kernel: signed errors are NOT model quantiles.

    This permits the P1-P4 hand-calculated constant-error fixtures without
    pretending that constant qlog is a legal strictly ordered v2 prediction.
    """
    image_tensor("error", error, 32)
    if error.dtype != torch.float64:
        raise ValueError("Pinball signed errors require FP64")
    boolean_mask("rainy_valid", rainy_valid, error[:, :1])
    finite_tensor("pinball errors", error)
    if not bool(rainy_valid.any()):
        return graph_zero(error)
    selected = error.movedim(1, -1)[rainy_valid.squeeze(1)]  # [N_rain,32]
    tau = frozen_taus(error.device)
    per_pixel = torch.maximum(tau * selected, (tau - 1) * selected).mean(dim=-1)
    result = per_pixel.sum()
    finite_tensor("quantile numerator", result)
    return result


def conditional_pinball_numerator(qlog: torch.Tensor, log_target: torch.Tensor,
                                  rainy_valid: torch.Tensor) -> torch.Tensor:
    quantiles(qlog)
    same_shape_device("log_target", log_target, qlog[:, :1])
    image_tensor("log_target", log_target, 1)
    if log_target.dtype != torch.float64:
        raise ValueError("log_target requires FP64")
    boolean_mask("rainy_valid", rainy_valid, log_target)
    finite_tensor("log_target", log_target)
    if bool((log_target < 0).any()):
        raise ValueError("log_target must be nonnegative log1p(mm/h)")
    threshold_log = torch.log1p(torch.tensor(.1, dtype=torch.float32, device=qlog.device).double())
    if bool((log_target[rainy_valid] <= threshold_log).any()):
        raise ValueError("rainy_valid cannot select a dry or threshold-equal reference target")
    with torch.autocast(qlog.device.type, enabled=False):
        # Only the explicitly declared singleton tau axis is expanded.
        error = log_target - qlog
        return _pinball_from_errors(error, rainy_valid)
