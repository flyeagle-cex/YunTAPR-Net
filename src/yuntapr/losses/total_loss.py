"""Core L_occ + L_qr; KD=0 and extension disabled in v1."""
from dataclasses import dataclass
import torch
from yuntapr.losses.focal import focal_bce_sum
from yuntapr.losses.pinball import pinball_sum
from yuntapr.models.probability_heads import B0Output


@dataclass
class LossResult:
    total: torch.Tensor
    occurrence: torch.Tensor
    conditional_quantile: torch.Tensor
    valid_supervised_count: int
    rainy_valid_count: int
    conditional_skipped: bool
    batch_skipped: bool
    skip_reason: str | None
    l_kd: int = 0
    l_ext_enabled: bool = False
    execution_scope: str = "ENGINEERING_ONLY"


def b0_core_loss(output: B0Output, y_imerg: torch.Tensor, imerg_valid_mask: torch.Tensor,
                 yunnan_eval_mask: torch.Tensor, *, focal_alpha: float | None = None,
                 focal_gamma: float | None = None, quantile_axis_reduction: str,
                 formal_mode: bool = False) -> LossResult:
    if focal_alpha is None or focal_gamma is None:
        raise ValueError("Formal B0 focal_alpha/focal_gamma are REQUIRED_DEVELOPMENT_PARAMETER; no defaults")
    expected = output.rain_logit.shape
    if y_imerg.shape != expected or imerg_valid_mask.shape != expected or yunnan_eval_mask.shape != expected:
        raise ValueError("Loss tensors must be [B,1,100,100]")
    if imerg_valid_mask.dtype != torch.bool or yunnan_eval_mask.dtype != torch.bool:
        raise ValueError("Loss requires independent bool validity/evaluation masks")
    valid = imerg_valid_mask & yunnan_eval_mask
    nvalid = int(valid.sum().item())
    if nvalid == 0:
        zero = output.rain_logit.sum() * 0 + output.conditional_quantiles_log.sum() * 0
        return LossResult(zero, zero, zero, 0, 0, True, True, "ZERO_VALID_SUPERVISED_YUNNAN_PIXELS")
    if not torch.isfinite(y_imerg[valid]).all() or (y_imerg[valid] < 0).any():
        raise ValueError("Supervised valid precipitation must be finite nonnegative")
    clean_y = torch.where(valid, y_imerg, torch.zeros_like(y_imerg))  # masked tensor arithmetic only; raw unchanged
    rainy = clean_y > 0.1
    nrainy = int((rainy & valid).sum().item())
    occ = focal_bce_sum(output.rain_logit, rainy, valid, focal_alpha, focal_gamma) / nvalid
    if nrainy:
        qr = pinball_sum(output.conditional_quantiles_log, torch.log1p(clean_y), rainy & valid, quantile_axis_reduction) / nvalid
    else:
        qr = output.conditional_quantiles_log.sum() * 0
    return LossResult(occ + qr, occ, qr, nvalid, nrainy, nrainy == 0, False,
                      "NO_CONDITIONAL_RAINY_PIXEL" if nrainy == 0 else None)
