"""Researcher-defined normalized positive allocation with an independent span."""
from dataclasses import dataclass
import math
import torch
from torch.nn import functional as F
from .outputs import validate_log_quantiles


@dataclass(frozen=True)
class CandidateNumerics:
    epsilon_w: float
    epsilon_span: float

    def __post_init__(self):
        for value in (self.epsilon_w, self.epsilon_span):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("Explicit finite positive candidate epsilons required; no scientific defaults")


def normalized_monotonic_quantiles(allocation_logits, span_logit, *, numerics: CandidateNumerics):
    if allocation_logits.ndim != 4 or allocation_logits.shape[1] != 32:
        raise ValueError("Allocation logits must be [B,32,H,W]")
    if span_logit.shape != allocation_logits[:, :1].shape:
        raise ValueError("Span logit must be [B,1,H,W]")
    if allocation_logits.device != span_logit.device or not allocation_logits.is_floating_point() or not span_logit.is_floating_point():
        raise ValueError("Floating logits on the same device required")
    if not isinstance(numerics, CandidateNumerics):
        raise ValueError("Explicit candidate numerics required")
    with torch.autocast(allocation_logits.device.type, enabled=False):
        a, s = allocation_logits.double(), span_logit.double()
        if not bool(torch.isfinite(a).all()) or not bool(torch.isfinite(s).all()):
            raise FloatingPointError("V2_RAW_NONFINITE")
        weights = F.softplus(a) + numerics.epsilon_w
        prefix = torch.cumsum(weights, dim=1)
        # Reuse the SAME prefix reduction for W and c32; c32 is exactly 1
        # whenever representable. This is the stated sum, not an output repair.
        total = prefix[:, -1:]
        if not bool(torch.isfinite(total).all()):
            raise FloatingPointError("V2_ALLOCATION_TOTAL_NONFINITE")
        cumulative_fraction = prefix / total
        span = F.softplus(s) + numerics.epsilon_span
        qlog = math.log1p(.1) + span * cumulative_fraction
        validate_log_quantiles(qlog)
    return qlog
