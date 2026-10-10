"""Variable batch adapter; reuses unchanged architecture/loss/FP64 evaluator."""
from __future__ import annotations
import torch
from yuntapr.models.quantile_v2.models import B0MatchedV2, B1V2
from yuntapr.models.quantile_v2.outputs import LogDomainOutput, validate_log_quantiles
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from .data import Batch, ROLES


def forward(model, batch: Batch, kind: str, arm: str):
    training = batch.role == ROLES[0]
    size = len(batch.ids)
    allowed = (1, 2) if training else (1, 2, 3, 4, 5, 6, 7, 8)
    expected = {"B0_MATCHED_V2": B0MatchedV2, "B1_V2": B1V2}.get(kind)
    if type(batch) is not Batch or batch.role not in ROLES or size not in allowed or type(model) is not expected:
        raise ValueError("Exact model/artificial batch/role signature required")
    if model.training != training or batch.x.device.type != "cuda":
        raise ValueError("Frozen CUDA train/validation mode; no fallback")
    if any(p.dtype != torch.float32 or p.device != batch.x.device for p in model.parameters()):
        raise ValueError("Frozen parameter dtype/device")
    if model.heads.numerics.epsilon_w != 1e-4 or model.heads.numerics.epsilon_span != 1e-4:
        raise ValueError("Frozen epsilon changed")
    with torch.autocast("cuda", dtype=torch.bfloat16):
        output = model(batch.x, batch.native_valid)
        for name, channels, dtype in (("rain_logit", 1, torch.bfloat16), ("rain_prob", 1, torch.bfloat16),
                                     ("conditional_quantiles_log", 32, torch.float64)):
            value = getattr(output, name)
            if value.shape != (size, channels, 100, 100) or value.dtype != dtype or not bool(torch.isfinite(value).all()):
                raise FloatingPointError("Frozen output precision/shape/finiteness: " + name)
        validate_log_quantiles(output.conditional_quantiles_log)
        if not torch.equal(output.rain_prob, torch.sigmoid(output.rain_logit)):
            raise ValueError("Frozen sigmoid interface")
        loss = candidate_loss(output.rain_logit, output.conditional_quantiles_log, batch.rate,
                              batch.reference_valid, batch.region_mask, config=get_config(arm))
    if (output.native_feature_shape != (size, 48, 501, 501) or output.target_feature_shape != (size, 48, 100, 100)
            or not bool((output.target_support_fraction == 1).all()) or loss.n_valid != size * 3430):
        raise ValueError("Frozen SP04/support/denominator interface mismatch")
    return output, loss

