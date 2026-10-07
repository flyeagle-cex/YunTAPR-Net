"""48 -> 1 occurrence and 48 -> 33 normalized quantile candidate heads."""
import torch
from torch import nn
from .outputs import LogDomainOutput
from .parameterization import CandidateNumerics, normalized_monotonic_quantiles


class ProbabilityHeadsV2(nn.Module):
    def __init__(self, *, numerics: CandidateNumerics):
        super().__init__()
        self.numerics = numerics
        self.occurrence = nn.Conv2d(48, 1, 1)
        self.quantile = nn.Conv2d(48, 33, 1)

    def forward(self, features):
        if features.ndim != 4 or features.shape[1:] != (48, 100, 100):
            raise ValueError("Head requires [B,48,100,100]")
        logit = self.occurrence(features)
        if not bool(torch.isfinite(logit).all()):
            raise FloatingPointError("V2_OCCURRENCE_NONFINITE")
        with torch.autocast(features.device.type, enabled=False):
            raw = self.quantile(features.float())
            qlog = normalized_monotonic_quantiles(raw[:, :32], raw[:, 32:], numerics=self.numerics)
        return LogDomainOutput(logit, torch.sigmoid(logit), qlog)
