"""Explicit indexed feature reduction; source edge remains convolution context."""
import torch
from torch import nn
from yuntapr.spatial.sp04_mapping import SP04Mapping


class SP04Projection(nn.Module):
    def __init__(self, mapping: SP04Mapping, operator: str):
        super().__init__()
        if operator != "arithmetic_mean":
            raise ValueError(f"Unsupported explicit feature reduction: {operator}")
        self.operator = operator
        self.register_buffer("indices", mapping.indices.clone(), persistent=False)

    def forward(self, native: torch.Tensor) -> torch.Tensor:
        if native.ndim != 4 or tuple(native.shape[-2:]) != (501, 501):
            raise ValueError("Projection requires native [B,C,501,501]")
        b, c = native.shape[:2]
        selected = native.flatten(-2).index_select(-1, self.indices.flatten())
        return selected.reshape(b, c, 100, 100, 25).mean(dim=-1)

    def support_fraction(self, valid_native: torch.Tensor) -> torch.Tensor:
        if valid_native.dtype != torch.bool or valid_native.ndim != 4 or valid_native.shape[1:] != (1, 501, 501):
            raise ValueError("B13 validity mask requires [B,1,501,501] bool")
        return self.forward(valid_native.to(torch.float32))
