"""Explicit Tensor batch construction preserving validity sidecars."""
from dataclasses import dataclass
from datetime import timedelta
import numpy as np
import torch
from yuntapr.data.sample_schema import utc


@dataclass
class B0Batch:
    x_b13: torch.Tensor
    b13_valid_mask: torch.Tensor
    y_imerg: torch.Tensor | None
    imerg_valid_mask: torch.Tensor | None
    yunnan_eval_mask: torch.Tensor | None
    execution_scope: str = "ENGINEERING_ONLY"
    formal_samples: tuple = ()

    @classmethod
    def from_formal_samples(cls, samples):
        if not samples or any(s.x_b13_normalized is None for s in samples):
            raise ValueError("FORMAL_BATCH_REQUIRES_NORMALIZED_SAMPLES")
        def tensor(name):
            return torch.from_numpy(np.stack([getattr(s, name) for s in samples])[:, None].copy())
        batch = cls(tensor("x_b13_normalized"), tensor("b13_valid_mask"), tensor("y_imerg"),
                    tensor("imerg_valid_mask"), tensor("yunnan_eval_mask"), formal_samples=tuple(samples))
        return batch.validate_formal()

    def validate_formal(self):
        self.validate()
        if self.execution_scope != "ENGINEERING_ONLY":
            raise ValueError("FORMAL_TRAINING_NOT_AUTHORIZED")
        if not self.formal_samples or len(self.formal_samples) != self.x_b13.shape[0]:
            raise ValueError("FORMAL_BATCH_REQUIRES_SAMPLE_PROVENANCE")
        if not bool(self.b13_valid_mask.all()) or not bool(torch.isfinite(self.x_b13).all()):
            raise ValueError("FORMAL_BACKBONE_REQUIRES_FULL_VALID_FINITE_FRAME")
        for i, s in enumerate(self.formal_samples):
            if (not s.formal_supervised_qc_pass or not s.supervised_eligible or not s.b13_full_valid
                    or not s.expected_latest_available or s.used_older_causal_frame
                    or s.eligibility_scope != "FORMAL_SUPERVISED_RULES_ENGINEERING_EXECUTION"
                    or s.expected_latest_slot != utc(s.analysis_time)-timedelta(minutes=10)
                    or utc(s.himawari_nominal_time) != s.expected_latest_slot
                    or utc(s.himawari_obs_end) > utc(s.analysis_time)):
                raise ValueError("FORMAL_BATCH_QC_OR_CAUSAL_ELIGIBILITY_FAILED")
            if not s.normalization_version or not s.normalization_artifact_sha256 or s.normalization_sigma is None or s.normalization_sigma <= 0:
                raise ValueError("FORMAL_BATCH_NORMALIZATION_REQUIRED")
            expected = ((s.x_b13.astype(np.float64)-s.normalization_mu)/s.normalization_sigma).astype(np.float32)
            if not np.isfinite(expected).all() or not torch.equal(self.x_b13[i, 0], torch.from_numpy(expected).to(self.x_b13.device)):
                raise ValueError("FORMAL_BACKBONE_INPUT_NOT_VERIFIED_NORMALIZED_KELVIN")
            if self.y_imerg is None or not bool((self.imerg_valid_mask[i] & self.yunnan_eval_mask[i]).any()):
                raise ValueError("FORMAL_BATCH_NO_VALID_YUNNAN_SUPERVISION")
        return self

    def validate(self):
        if self.x_b13.ndim != 4 or self.x_b13.shape[1:] != (1, 501, 501):
            raise ValueError("B0 batch input shape mismatch")
        if self.b13_valid_mask.shape != self.x_b13.shape or self.b13_valid_mask.dtype != torch.bool:
            raise ValueError("B13 mask missing or mismatched")
        if self.y_imerg is not None:
            expected = (self.x_b13.shape[0], 1, 100, 100)
            if self.y_imerg.shape != expected or self.imerg_valid_mask is None or self.imerg_valid_mask.shape != expected or self.yunnan_eval_mask is None or self.yunnan_eval_mask.shape != expected:
                raise ValueError("Supervised target/mask shape mismatch")
        return self
