"""Explicit tensor contracts; no output repair and no physical conversion."""
from __future__ import annotations
from dataclasses import dataclass
import torch
from yuntapr.models.quantile_v2.outputs import validate_log_quantiles


class ZeroValidPixelsError(ValueError):
    """Stop a loss call with zero supervision; never imply a skipped update."""


def image_tensor(name: str, value: torch.Tensor, channels: int) -> None:
    if not isinstance(value, torch.Tensor) or value.layout != torch.strided:
        raise ValueError(f"{name}: dense strided Tensor required")
    if value.ndim != 4 or value.shape[1] != channels or any(n <= 0 for n in value.shape):
        raise ValueError(f"{name}: nonempty [B,{channels},H,W] required")


def same_shape_device(name: str, value: torch.Tensor, reference: torch.Tensor) -> None:
    if not isinstance(value, torch.Tensor) or value.shape != reference.shape:
        raise ValueError(f"{name}: exact shape required; mask broadcasting is forbidden")
    if value.device != reference.device:
        raise ValueError(f"{name}: device mismatch")


def boolean_mask(name: str, value: torch.Tensor, reference: torch.Tensor) -> None:
    same_shape_device(name, value, reference)
    if value.dtype != torch.bool or value.layout != torch.strided:
        raise ValueError(f"{name}: dense bool Tensor required")


def finite_tensor(name: str, value: torch.Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(f"{name}: NaN/Inf forbidden, including masked output pixels")


def occurrence_logits(logit: torch.Tensor) -> None:
    image_tensor("logit", logit, 1)
    if logit.dtype not in (torch.float16, torch.bfloat16, torch.float32, torch.float64):
        raise ValueError("logit: real floating dtype required")
    if logit.device.type not in ("cpu", "cuda"):
        raise ValueError("logit: this candidate supports CPU/CUDA only")
    finite_tensor("logit", logit)


def quantiles(qlog: torch.Tensor) -> None:
    image_tensor("qlog", qlog, 32)
    if qlog.device.type not in ("cpu", "cuda"):
        raise ValueError("qlog: this candidate supports CPU/CUDA only")
    # Reuse the frozen FP64, finite, support and strict-order guards unchanged.
    validate_log_quantiles(qlog)


def graph_zero(value: torch.Tensor, *, dtype: torch.dtype | None = None) -> torch.Tensor:
    """Empty-view sum gives connected zero without overflowing sum(value)*0."""
    return value.reshape(-1)[:0].sum(dtype=dtype)


@dataclass(frozen=True)
class Supervision:
    valid: torch.Tensor
    rainy: torch.Tensor
    rainy_valid: torch.Tensor
    clean_rate: torch.Tensor
    n_valid: int
    n_rain: int


def supervision(logit: torch.Tensor, qlog: torch.Tensor, rate: torch.Tensor,
                imerg_valid: torch.Tensor, yunnan_mask: torch.Tensor) -> Supervision:
    occurrence_logits(logit)
    same_shape_device("qlog spatial slice", qlog[:, :1] if isinstance(qlog, torch.Tensor) and qlog.ndim == 4 else qlog, logit)
    quantiles(qlog)
    same_shape_device("rate", rate, logit)
    if rate.dtype != torch.float32 or rate.layout != torch.strided or rate.requires_grad:
        raise ValueError("rate: nondifferentiable dense float32 IMERG reference required")
    boolean_mask("imerg_valid", imerg_valid, logit)
    boolean_mask("yunnan_mask", yunnan_mask, logit)
    valid = imerg_valid & yunnan_mask
    n_valid = int(valid.sum().item())
    if n_valid == 0:
        raise ZeroValidPixelsError("ZERO_VALID_SUPERVISED_YUNNAN_PIXELS; no silent skip")
    if not bool(torch.isfinite(rate[valid]).all()) or bool((rate[valid] < 0).any()):
        raise ValueError("Supervised valid precipitation must be finite nonnegative")
    # Only an ephemeral arithmetic target is cleaned, exactly as in the old loss.
    clean = torch.where(valid, rate, torch.zeros_like(rate))
    rainy = clean > torch.tensor(.1, dtype=torch.float32, device=rate.device)
    rainy_valid = rainy & valid  # compare BEFORE converting rate to FP64
    return Supervision(valid, rainy, rainy_valid, clean, n_valid, int(rainy_valid.sum().item()))
