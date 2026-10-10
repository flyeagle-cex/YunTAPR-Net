"""Candidate training objective and unweighted components, no optimizer."""
from __future__ import annotations
from dataclasses import dataclass
import torch
from .config import AblationConfig, finite_number
from .focal import occurrence_numerator
from .pinball import conditional_pinball_numerator
from .validation import finite_tensor, supervision


def combine_numerators(s_occ: torch.Tensor, s_qr: torch.Tensor, n_valid: int,
                       *, lambda_q: float) -> torch.Tensor:
    weight = finite_number("lambda_q", lambda_q)
    if weight <= 0 or type(n_valid) is not int or n_valid <= 0:
        raise ValueError("Positive lambda_q and positive integer N_valid required")
    for name, value in (("S_occ", s_occ), ("S_qr", s_qr)):
        if not isinstance(value, torch.Tensor) or value.ndim != 0 or value.layout != torch.strided or value.dtype not in (torch.float32, torch.float64):
            raise ValueError(f"{name}: FP32/FP64 scalar Tensor required")
    if s_occ.device != s_qr.device:
        raise ValueError("Numerator device mismatch")
    if s_occ.device.type not in ("cpu", "cuda"):
        raise ValueError("Numerator device must be CPU/CUDA")
    for name, value in (("S_occ", s_occ), ("S_qr", s_qr)):
        finite_tensor(name, value)
        if bool(value < 0):
            raise ValueError(f"{name}: loss numerator must be nonnegative")
    result = (s_occ + weight * s_qr) / n_valid  # weight exactly once
    finite_tensor("weighted training objective", result)
    return result


@dataclass(frozen=True)
class CandidateLossResult:
    experiment_id: str
    s_occ: torch.Tensor
    s_qr: torch.Tensor
    training_objective: torch.Tensor
    weighted_quantile_per_valid: torch.Tensor
    n_valid: int
    n_rain: int
    conditional_skipped: bool
    status: str = "VALID_SYNTHETIC_OR_CANDIDATE_LOSS_CALL"
    execution_authorization: bool = False

    @property
    def scientific_conditional_pinball(self) -> torch.Tensor | None:
        # No lambda here. None explicitly means not estimable, not zero skill.
        return self.s_qr / self.n_rain if self.n_rain else None


def candidate_loss(logit: torch.Tensor, qlog: torch.Tensor, rate: torch.Tensor,
                   imerg_valid: torch.Tensor, yunnan_mask: torch.Tensor,
                   *, config: AblationConfig) -> CandidateLossResult:
    if type(config) is not AblationConfig:
        raise ValueError("Explicit closed AblationConfig required")
    config.__post_init__()  # revalidate even if external code bypassed frozen setattr
    target = supervision(logit, qlog, rate, imerg_valid, yunnan_mask)
    s_occ = occurrence_numerator(logit, target.rainy, target.valid, alpha=config.alpha, gamma=config.gamma)
    with torch.autocast(logit.device.type, enabled=False):
        s_qr = conditional_pinball_numerator(qlog, torch.log1p(target.clean_rate.double()), target.rainy_valid)
        total = combine_numerators(s_occ, s_qr, target.n_valid, lambda_q=config.lambda_q)
        weighted = config.lambda_q * s_qr / target.n_valid
    return CandidateLossResult(config.experiment_id, s_occ, s_qr, total, weighted,
                               target.n_valid, target.n_rain, target.n_rain == 0)
