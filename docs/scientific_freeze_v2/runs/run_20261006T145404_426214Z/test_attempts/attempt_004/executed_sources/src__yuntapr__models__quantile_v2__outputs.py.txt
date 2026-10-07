"""Separate differentiable log-domain and explicitly requested physical APIs."""
from dataclasses import dataclass
import math
import torch


@dataclass
class LogDomainOutput:
    rain_logit: torch.Tensor
    rain_prob: torch.Tensor
    conditional_quantiles_log: torch.Tensor
    native_feature_shape: tuple | None = None
    target_feature_shape: tuple | None = None
    target_support_fraction: torch.Tensor | None = None
    b13_invalid_count: torch.Tensor | None = None
    b13_valid_fraction: torch.Tensor | None = None
    placeholder_policy: str = "FULL_VALID_NORMALIZED_NO_PLACEHOLDER"


@dataclass
class PhysicalQuantileOutput:
    conditional_quantiles_physical: torch.Tensor
    threshold_censored_mean: torch.Tensor


def validate_log_quantiles(qlog):
    if qlog.ndim != 4 or qlog.shape[1] != 32 or qlog.dtype != torch.float64:
        raise ValueError("FP64 [B,32,H,W] log quantiles required")
    if not bool(torch.isfinite(qlog).all()):
        raise FloatingPointError("V2_QLOG_NONFINITE")
    if not bool((qlog[:, :1] > math.log1p(.1)).all()):
        raise FloatingPointError("V2_SUPPORT_LOST_AT_TENSOR_PRECISION")
    if not bool((qlog[:, 1:] > qlog[:, :-1]).all()):
        raise FloatingPointError("V2_STRICT_ORDER_LOST_AT_TENSOR_PRECISION")


@torch.no_grad()
def physical_risk(qlog):
    """Read-only comparison, never performs expm1 or participates in loss."""
    validate_log_quantiles(qlog)
    q = qlog.detach()
    boundaries = {str(bits): math.log1p(torch.finfo(dtype).max)
                  for bits, dtype in ((32, torch.float32), (64, torch.float64))}
    return {
        "description": "physical-risk diagnostic（物理转换风险诊断）：仅比较浮点边界，不改变梯度、损失或样本。",
        "max_qlog": float(q.max()),
        "per_tau_qlog_range": [{"min": float(q[:, i].min()), "max": float(q[:, i].max())}
                                for i in range(32)],
        "boundaries": boundaries,
        "FP64_PHYSICAL_OVERFLOW_RISK": bool((q > boundaries['64']).any()),
        "FP32_PHYSICAL_OVERFLOW_RISK": bool((q > boundaries['32']).any()),
        "unit": "log1p(mm/h)",
        "affects_gradient_loss_or_batch_selection": False,
    }


def materialize_physical(output: LogDomainOutput) -> PhysicalQuantileOutput:
    """Explicit FP64 product; actual overflow is reported, never repaired."""
    validate_log_quantiles(output.conditional_quantiles_log)
    q = torch.expm1(output.conditional_quantiles_log)
    if not bool(torch.isfinite(q).all()):
        raise FloatingPointError("V2_PHYSICAL_OVERFLOW: expm1(qlog) nonfinite")
    if not bool((q[:, :1] > .1).all()) or not bool((q[:, 1:] > q[:, :-1]).all()):
        raise FloatingPointError("V2_PHYSICAL_SUPPORT_OR_ORDER_LOST")
    mean = output.rain_prob * q.mean(dim=1, keepdim=True)
    if not bool(torch.isfinite(mean).all()):
        raise FloatingPointError("V2_PHYSICAL_PROXY_NONFINITE")
    return PhysicalQuantileOutput(q, mean)
