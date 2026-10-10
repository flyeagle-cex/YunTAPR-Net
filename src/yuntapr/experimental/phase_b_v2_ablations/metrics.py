"""Unweighted reporting interface; common core always uses E0 in FP64."""
from __future__ import annotations
from dataclasses import dataclass
import math
import torch
from .config import get_config
from .total import CandidateLossResult, candidate_loss


@dataclass(frozen=True)
class ReportingSums:
    s_occ: float
    s_qr: float
    n_valid: int
    n_rain: int

    def __post_init__(self) -> None:
        if not all(type(x) in (float, int) and math.isfinite(x) and x >= 0 for x in (self.s_occ, self.s_qr)):
            raise ValueError("Finite nonnegative unweighted reporting sums required")
        if type(self.n_valid) is not int or type(self.n_rain) is not int or not 0 <= self.n_rain <= self.n_valid or self.n_valid <= 0:
            raise ValueError("Positive N_valid and integer 0<=N_rain<=N_valid required")

    @classmethod
    def from_candidate(cls, result: CandidateLossResult) -> ReportingSums:
        return cls(float(result.s_occ.detach()), float(result.s_qr.detach()), result.n_valid, result.n_rain)

    @property
    def conditional_pinball(self) -> float | None:
        return self.s_qr / self.n_rain if self.n_rain else None

    def pooled(self, other: ReportingSums) -> ReportingSums:
        # Pool sums/counts rather than averaging unequal-batch metric values.
        return ReportingSums(self.s_occ + other.s_occ, self.s_qr + other.s_qr,
                             self.n_valid + other.n_valid, self.n_rain + other.n_rain)


@torch.no_grad()
def common_validation_sums(logit: torch.Tensor, qlog: torch.Tensor, rate: torch.Tensor,
                           imerg_valid: torch.Tensor, yunnan_mask: torch.Tensor) -> ReportingSums:
    """Fixed gamma2/lambda1 arithmetic, not an arm's weighted train objective.

    Caller-supplied tensors only. This function does not run a model or read data.
    The current tests call it exclusively with explicitly synthetic tensors.
    """
    result = candidate_loss(logit.double(), qlog, rate, imerg_valid, yunnan_mask, config=get_config("E0"))
    return ReportingSums.from_candidate(result)
