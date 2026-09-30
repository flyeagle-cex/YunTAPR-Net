"""Explicit Tensor batch construction preserving validity sidecars."""
from dataclasses import dataclass
import torch


@dataclass
class B0Batch:
    x_b13: torch.Tensor
    b13_valid_mask: torch.Tensor
    y_imerg: torch.Tensor | None
    imerg_valid_mask: torch.Tensor | None
    yunnan_eval_mask: torch.Tensor | None
    execution_scope: str = "ENGINEERING_ONLY"

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
