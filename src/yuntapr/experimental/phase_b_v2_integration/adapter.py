"""Frozen full-grid v2 models to unchanged candidate loss APIs."""
from __future__ import annotations
import torch
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.outputs import LogDomainOutput, validate_log_quantiles
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.total import CandidateLossResult, candidate_loss
from .synthetic import SyntheticBatch


def loss_from_output(output: LogDomainOutput, batch: SyntheticBatch, kind: str,
                     experiment_id: str) -> CandidateLossResult:
    batch.validate(kind)
    config = get_config(experiment_id)
    if type(output) is not LogDomainOutput:
        raise ValueError("Current v2 LogDomainOutput required")
    for name in ("rain_logit", "rain_prob", "conditional_quantiles_log"):
        value = getattr(output, name)
        channels = 32 if name == "conditional_quantiles_log" else 1
        if not isinstance(value, torch.Tensor) or value.shape != (2, channels, 100, 100):
            raise ValueError(name + ": frozen full target grid required")
        if value.device != batch.x.device or not bool(torch.isfinite(value).all()):
            raise ValueError(name + ": device/nonfinite mismatch")
    validate_log_quantiles(output.conditional_quantiles_log)
    if not bool(((output.rain_prob >= 0) & (output.rain_prob <= 1)).all()):
        raise ValueError("Occurrence probability outside support")
    if not torch.equal(output.rain_prob, torch.sigmoid(output.rain_logit)):
        raise ValueError("Probability must be the current head sigmoid output")
    result = candidate_loss(output.rain_logit, output.conditional_quantiles_log, batch.rate,
                            batch.reference_valid, batch.region_mask, config=config)
    if result.n_valid != 6860:
        raise ValueError("Fixed batch supervision count mismatch")
    return result


def forward_synthetic(model: torch.nn.Module, batch: SyntheticBatch, kind: str,
                      experiment_id: str) -> tuple[LogDomainOutput, CandidateLossResult]:
    """One full synthetic forward/loss; no backward, loop, optimizer or file I/O."""
    batch.validate(kind)
    get_config(experiment_id)  # reject invalid arm before model execution
    expected = {"B0_MATCHED_V2": B0MatchedV2, "B1_V2": B1V2}[kind]
    if type(model) is not expected or not model.training:
        raise ValueError("Exact frozen v2 architecture in train mode required")
    if any(p.dtype != torch.float32 or p.device != batch.x.device for p in model.parameters()):
        raise ValueError("Frozen FP32 parameter/device contract required")
    if model.heads.numerics.epsilon_w != 1e-4 or model.heads.numerics.epsilon_span != 1e-4:
        raise ValueError("Frozen v2 epsilon changed")
    with torch.autocast(batch.x.device.type, dtype=torch.bfloat16, enabled=True):
        output = model(batch.x, batch.native_valid)
        result = loss_from_output(output, batch, kind, experiment_id)
    if output.native_feature_shape != (2, 48, 501, 501) or output.target_feature_shape != (2, 48, 100, 100):
        raise ValueError("Native/SP04 feature shape mismatch")
    if output.rain_logit.dtype != torch.bfloat16:
        raise ValueError("Frozen BF16 occurrence path required, no precision fallback")
    if output.target_support_fraction.shape != (2, 1, 100, 100) or not bool((output.target_support_fraction == 1).all()):
        raise ValueError("Full SP04 support required")
    if not bool((output.b13_invalid_count == 0).all()) or not bool((output.b13_valid_fraction == 1).all()):
        raise ValueError("Native complete-support diagnostics mismatch")
    return output, result

