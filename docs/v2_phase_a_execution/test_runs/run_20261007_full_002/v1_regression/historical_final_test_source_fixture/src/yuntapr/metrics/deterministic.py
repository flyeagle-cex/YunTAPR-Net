"""Frozen threshold-censored diagnostic, never called full physical mean."""
import torch
from yuntapr.models.probability_heads import B0Output


def threshold_censored_diagnostic(output: B0Output) -> torch.Tensor:
    return output.rain_prob * output.conditional_quantiles_physical.mean(dim=1, keepdim=True)
