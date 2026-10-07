"""A-path equivalence fixture, preserving v1 parameters and qlog arithmetic."""
from contextlib import nullcontext
import torch
from yuntapr.models.b0 import B0Model
from yuntapr.models.probability_heads import ProbabilityHeads
from yuntapr.models.monotonic_quantiles import monotonic_quantiles
from .outputs import LogDomainOutput


class LegacyLogDomainHeads(ProbabilityHeads):
    def forward(self, features):
        if features.ndim != 4 or features.shape[1:] != (48, 100, 100):
            raise ValueError("Head requires [B,48,100,100]")
        logit = self.occurrence(features)
        guard = (torch.autocast(device_type=features.device.type, enabled=False)
                 if features.device.type in ("cpu", "cuda") else nullcontext())
        with guard:
            raw = self.quantile(features.float())
            qlog = monotonic_quantiles(raw, self.threshold, epsilon_mono=self.epsilon_mono,
                                       accumulation_dtype=self.accumulation_dtype)
        return LogDomainOutput(logit, torch.sigmoid(logit), qlog)


class LegacyLogDomainFixture(B0Model):
    """Fresh disposable B0 fixture only; never deserializes a trained checkpoint."""
    def __init__(self, *, test_fixture_only):
        if test_fixture_only is not True:
            raise PermissionError("TEST_FIXTURE_ONLY required")
        super().__init__()
        original = self.heads
        replacement = LegacyLogDomainHeads(48, .1, epsilon_mono=original.epsilon_mono,
                                            accumulation_dtype=original.accumulation_dtype)
        replacement.load_state_dict(original.state_dict())
        self.heads = replacement

    def _evaluate(self, x, b13_valid_mask, valid_counts):
        native = self.backbone(x)
        target = self.projection(native)
        output = self.heads(target)
        output.native_feature_shape = tuple(native.shape)
        output.target_feature_shape = tuple(target.shape)
        output.target_support_fraction = self.projection.support_fraction(b13_valid_mask)
        output.b13_invalid_count = 501 * 501 - valid_counts
        output.b13_valid_fraction = valid_counts / (501 * 501)
        return output
