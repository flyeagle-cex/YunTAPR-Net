"""Deterministic artificial tensors and identities; no paths or data readers."""
from __future__ import annotations
from dataclasses import dataclass, replace
import re
import torch
from . import SCOPE

MASK_ROLE = "ARTIFICIAL_3430_CELL_LAYOUT_NOT_FROZEN_YUNNAN_GEOGRAPHY"


@dataclass(frozen=True)
class SyntheticBatch:
    x: torch.Tensor
    native_valid: torch.Tensor
    rate: torch.Tensor
    reference_valid: torch.Tensor
    region_mask: torch.Tensor
    sample_ids: tuple[str, ...]
    slot_offsets: tuple[int, ...]
    scope: str = SCOPE
    mask_role: str = MASK_ROLE
    data_years: tuple[int, ...] = ()

    def validate(self, kind: str) -> None:
        frames = {"B0_MATCHED_V2": 1, "B1_V2": 6}.get(kind)
        if frames is None or self.scope != SCOPE or self.mask_role != MASK_ROLE or self.data_years != ():
            raise ValueError("Synthetic provenance only; no observational years or official mask claim")
        if type(self.sample_ids) is not tuple or len(self.sample_ids) != 2 or len(set(self.sample_ids)) != 2:
            raise ValueError("Two distinct synthetic sample IDs required")
        if any(type(s) is not str or re.fullmatch(r"SYNTHETIC_ENGINEERING_ONLY/scene_[0-9]{4}", s) is None
               for s in self.sample_ids):
            raise ValueError("Only explicitly artificial scene IDs accepted")
        expected_offsets = (10,) if frames == 1 else (60, 50, 40, 30, 20, 10)
        if self.slot_offsets != expected_offsets:
            raise ValueError("Frozen oldest-to-latest causal slot order required")
        if not isinstance(self.x, torch.Tensor) or self.x.shape != (2, frames, 501, 501):
            raise ValueError("Fixed synthetic batch=2, native 501x501 input required")
        if self.x.device.type not in ("cpu", "cuda") or self.x.dtype != torch.float32 or self.x.layout != torch.strided:
            raise ValueError("FP32 dense CPU/CUDA normalized synthetic input required")
        if self.x.requires_grad or not bool(torch.isfinite(self.x).all()):
            raise ValueError("Finite non-gradient artificial input required")
        for name, value, shape, dtype in (
            ("native_valid", self.native_valid, self.x.shape, torch.bool),
            ("rate", self.rate, (2, 1, 100, 100), torch.float32),
            ("reference_valid", self.reference_valid, (2, 1, 100, 100), torch.bool),
            ("region_mask", self.region_mask, (2, 1, 100, 100), torch.bool)):
            if not isinstance(value, torch.Tensor) or tuple(value.shape) != tuple(shape):
                raise ValueError(name + ": exact shape required, no broadcasting")
            if value.device != self.x.device or value.dtype != dtype or value.layout != torch.strided or value.requires_grad:
                raise ValueError(name + ": device/dtype/layout/gradient mismatch")
        if not bool(self.native_valid.all()):
            raise ValueError("M1: incomplete native frame rejected, no fallback")
        if not bool(torch.isfinite(self.rate).all()) or bool((self.rate < 0).any()):
            raise ValueError("Synthetic reference must be finite and nonnegative")
        if not bool((self.region_mask.flatten(1).sum(1) == 3430).all()):
            raise ValueError("Artificial region must contain exactly 3430 cells per scene")
        if not bool(((self.reference_valid & self.region_mask).flatten(1).sum(1) == 3430).all()):
            raise ValueError("Q1 complete reference support required")

    def to(self, device: torch.device | str) -> SyntheticBatch:
        return replace(self, **{name: getattr(self, name).to(device) for name in
                               ("x", "native_valid", "rate", "reference_valid", "region_mask")})


def make_synthetic_pair() -> dict[str, SyntheticBatch]:
    """Inputs are already in normalized numeric coordinates, not Kelvin readings.

    The frozen scaler is verified as metadata elsewhere and is never refit/applied
    to observations. The artificial mask only tests counts and indexing.
    """
    cells = torch.arange(501 * 501, dtype=torch.float32).reshape(1, 1, 501, 501)
    slots = torch.arange(6, dtype=torch.float32).reshape(1, 6, 1, 1)
    scenes = torch.arange(2, dtype=torch.float32).reshape(2, 1, 1, 1)
    x = .6 * torch.sin(cells / 173.) + .07 * slots + .11 * scenes
    threshold = torch.tensor(.1, dtype=torch.float32)
    rates = torch.stack((threshold * 0, threshold,
                        torch.nextafter(threshold, torch.tensor(float("inf"))),
                        threshold * 5, threshold * 10, threshold * 50, threshold * 200))
    rate = rates[torch.arange(20000) % 7].reshape(2, 1, 100, 100)
    region = (torch.arange(10000).reshape(1, 1, 100, 100) < 3430).expand(2, 1, 100, 100).clone()
    base = SyntheticBatch(x, torch.ones_like(x, dtype=torch.bool), rate,
                          torch.ones_like(rate, dtype=torch.bool), region,
                          tuple(f"{SCOPE}/scene_{i:04d}" for i in range(2)), (60, 50, 40, 30, 20, 10))
    latest = replace(base, x=x[:, -1:].clone(), native_valid=base.native_valid[:, -1:].clone(), slot_offsets=(10,))
    result = {"B0_MATCHED_V2": latest, "B1_V2": base}
    for kind, batch in result.items():
        batch.validate(kind)
    return result

