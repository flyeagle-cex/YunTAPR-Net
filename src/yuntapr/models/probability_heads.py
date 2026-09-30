"""Occurrence and 32 conditional quantile heads."""
from dataclasses import dataclass
from contextlib import nullcontext
import torch
from torch import nn
from yuntapr.models.monotonic_quantiles import monotonic_quantiles


@dataclass
class B0Output:
    rain_logit: torch.Tensor
    rain_prob: torch.Tensor
    conditional_quantiles_log: torch.Tensor
    conditional_quantiles_physical: torch.Tensor
    threshold_censored_mean: torch.Tensor
    native_feature_shape: tuple[int, ...]
    target_feature_shape: tuple[int, ...]
    target_support_fraction: torch.Tensor
    b13_invalid_count: torch.Tensor
    b13_valid_fraction: torch.Tensor
    placeholder_policy: str = "ENGINEERING_ONLY_NONPHYSICAL_WITH_MASK_SIDECAR"

    def exceedance_probability(self, rate_mm_h: float) -> dict:
        if rate_mm_h == 0.1:
            return {"status": "ESTABLISHED", "probability": self.rain_prob, "coverage": "occurrence_threshold"}
        return {"status": "NOT_ESTABLISHED", "probability": None, "coverage": "outside_frozen_occurrence_point; no tail model"}


class ProbabilityHeads(nn.Module):
    def __init__(self, target_channels: int, threshold: float, *, epsilon_mono: float = 0.0,
                 accumulation_dtype: torch.dtype = torch.float32):
        super().__init__()
        if target_channels != 48 or threshold != 0.1:
            raise ValueError("B0 probability head differs from frozen contract")
        self.threshold = threshold
        self.epsilon_mono = epsilon_mono
        self.accumulation_dtype = accumulation_dtype
        self.occurrence = nn.Conv2d(48, 1, 1)
        self.quantile = nn.Conv2d(48, 32, 1)

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        if features.ndim != 4 or features.shape[1:] != (48, 100, 100):
            raise ValueError("Head requires [B,48,100,100]")
        logit = self.occurrence(features)
        guard = (torch.autocast(device_type=features.device.type, enabled=False)
                 if features.device.type in ("cpu", "cuda") else nullcontext())
        with guard:
            raw = self.quantile(features.float())
            qlog = monotonic_quantiles(raw, self.threshold, epsilon_mono=self.epsilon_mono,
                                       accumulation_dtype=self.accumulation_dtype)
            qphysical = torch.expm1(qlog)
        if not torch.isfinite(qphysical).all():
            raise FloatingPointError("QUANTILE_PHYSICAL_OVERFLOW: expm1(qlog) nonfinite")
        return logit, torch.sigmoid(logit), qlog, qphysical
