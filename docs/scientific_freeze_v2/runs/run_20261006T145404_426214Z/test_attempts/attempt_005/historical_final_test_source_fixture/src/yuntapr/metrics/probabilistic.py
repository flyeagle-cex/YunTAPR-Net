"""Validity-aware Brier diagnostic and honest exceedance coverage."""
import torch
from yuntapr.models.probability_heads import B0Output


def brier_at_occurrence(output: B0Output, y: torch.Tensor, valid: torch.Tensor, eval_mask: torch.Tensor) -> dict:
    selected = valid & eval_mask
    n = int(selected.sum())
    if n == 0:
        return {"status": "SKIPPED_ZERO_VALID", "count": 0, "value": None}
    if not torch.isfinite(y[selected]).all():
        raise ValueError("Nonfinite valid target")
    label = (y[selected] > 0.1).to(output.rain_prob.dtype)
    return {"status": "ENGINEERING_ONLY", "count": n, "value": ((output.rain_prob[selected] - label) ** 2).mean()}


def exceedance_probability(output: B0Output, threshold: float) -> dict:
    return output.exceedance_probability(threshold)
